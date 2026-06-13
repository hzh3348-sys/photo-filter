"""
检测编排器 — 整合所有检测器，管理 MediaPipe 生命周期。
"""

import sys
import threading
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from .models import PhotoResult, DetectionConfig
from .exposure import check_exposure
from .level import check_level
from .eyes import check_eyes_open
from .skin_tone import check_skin_tone
from .blur import check_blur  # v3.0: 多区域最清晰判断法
from .clarity import check_face_clarity
from utils.constants import (
    MIN_FACE_DETECTION_CONFIDENCE,
    MIN_FACE_PRESENCE_CONFIDENCE,
    MIN_TRACKING_CONFIDENCE,
    MAX_IMAGE_DIM,
    FACE_DETECT_DIM,
)
from utils.image_io import load_image


# ── 模型路径 ──────────────────────────────────────────────

def _get_model_path() -> Path:
    """获取模型文件路径，兼容 PyInstaller 打包和直接运行。"""
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS') and sys._MEIPASS:
            return Path(sys._MEIPASS) / "face_landmarker.task"
        else:
            return Path(sys.executable).parent / "face_landmarker.task"
    return Path(__file__).parent.parent / "face_landmarker.task"


MODEL_PATH = _get_model_path()


# ── MediaPipe 管理器 ──────────────────────────────────────

class MediaPipeManager:
    """
    MediaPipe FaceLandmarker 管理器。
    支持延迟加载和线程局部实例（用于多线程并行处理）。
    """

    def __init__(self):
        self._model_bytes: Optional[bytes] = None
        self._lock = threading.Lock()
        # 线程局部存储：每个线程拥有独立的 FaceLandmarker 实例
        self._thread_local = threading.local()

    @property
    def model_bytes(self) -> bytes:
        """懒加载模型文件到内存（避免中文路径问题）。"""
        if self._model_bytes is None:
            with self._lock:
                if self._model_bytes is None:
                    with open(MODEL_PATH, 'rb') as f:
                        self._model_bytes = f.read()
        return self._model_bytes

    def _create_landmarker(self):
        """创建新的 FaceLandmarker 实例。"""
        from mediapipe.tasks.python import BaseOptions
        from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions
        from mediapipe.tasks.python.vision.core.vision_task_running_mode import VisionTaskRunningMode

        options = FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_buffer=self.model_bytes),
            running_mode=VisionTaskRunningMode.IMAGE,
            num_faces=30,             # v3.5: 合照支持最多30张脸
            min_face_detection_confidence=MIN_FACE_DETECTION_CONFIDENCE,
            min_face_presence_confidence=MIN_FACE_PRESENCE_CONFIDENCE,
            min_tracking_confidence=MIN_TRACKING_CONFIDENCE,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        return FaceLandmarker.create_from_options(options)

    def get_landmarker(self):
        """
        获取当前线程的 FaceLandmarker 实例。
        每个线程首次调用时创建独立实例（线程安全）。
        """
        if not hasattr(self._thread_local, 'landmarker') or self._thread_local.landmarker is None:
            self._thread_local.landmarker = self._create_landmarker()
        return self._thread_local.landmarker

    def close(self):
        """关闭所有线程的 landmarker 实例。"""
        if hasattr(self._thread_local, 'landmarker') and self._thread_local.landmarker:
            try:
                self._thread_local.landmarker.close()
            except Exception:
                pass
            self._thread_local.landmarker = None

    def close_all(self):
        """关闭当前线程的 landmarker（兼容接口）。"""
        self.close()

    @staticmethod
    def get_mp_classes():
        """获取 MediaPipe Image 和 ImageFormat 类（延迟导入）。"""
        from mediapipe.tasks.python.vision.core.image import Image as MPImage, ImageFormat
        return MPImage, ImageFormat


# ── 人脸检测（三轮，极致检出）───────────────────────────

def _detect_faces(img, mp_manager):
    """
    三轮人脸检测，大幅提升小脸/侧脸/暗光检出率：
    第1轮：原图检测
    第2轮：放大到短边1200px
    第3轮：放大到短边1800px + 中心裁剪
    """
    h, w = img.shape[:2]
    MPImage, ImageFormat = MediaPipeManager.get_mp_classes()
    landmarker = mp_manager.get_landmarker()

    def _try_detect(image):
        """尝试检测单张图像的人脸。"""
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_img = MPImage(image_format=ImageFormat.SRGB, data=rgb)
        try:
            result = landmarker.detect(mp_img)
        except Exception:
            result = None
        del rgb, mp_img
        return result

    # 第1轮：原图
    face_result = _try_detect(img)
    if face_result and face_result.face_landmarks:
        return face_result

    # 第2轮：放大到短边1200px
    if min(h, w) < 1200:
        scale = 1200 / min(h, w)
        up = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LANCZOS4)
        face_result = _try_detect(up)
        del up
        if face_result and face_result.face_landmarks:
            return face_result

    # 第3轮：放大到短边1800px
    if min(h, w) < 1800:
        scale = 1800 / min(h, w)
        up2 = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LANCZOS4)
        face_result = _try_detect(up2)
        del up2
        if face_result and face_result.face_landmarks:
            return face_result

    # 第3轮备选：中心50%区域放大（人脸通常在中间）
    cy, cx = h // 2, w // 2
    crop = img[cy//2:cy+cy//2, cx//2:cx+cx//2]
    if crop.size > 0 and min(crop.shape[:2]) > 100:
        scale = 1200 / min(crop.shape[:2])
        crop_up = cv2.resize(crop, (int(crop.shape[1] * scale), int(crop.shape[0] * scale)),
                             interpolation=cv2.INTER_LANCZOS4)
        face_result = _try_detect(crop_up)
        del crop_up

    return face_result


# ── 单张照片检测 ──────────────────────────────────────────

def detect_single_photo(
    path: Path,
    config: DetectionConfig,
    mp_manager: MediaPipeManager,
) -> PhotoResult:
    """
    对单张照片运行完整的检测流程。
    此函数可在任意线程中调用（前提是 mp_manager 支持线程局部实例）。
    """
    result = PhotoResult(path=path)
    result.level_enabled = config.enable_level
    result.blur_enabled = config.enable_blur
    result.clarity_enabled = config.enable_clarity
    result.duplicate_enabled = config.enable_duplicate

    # 1. 加载图片（人脸检测用高分辨率，分析用常规分辨率）
    img_face = load_image(path, max_dim=FACE_DETECT_DIM)   # 高分辨率：人脸检测
    if img_face is None:
        result.error = "无法读取图片"
        return result

    # 分析用图像（缩小到标准尺寸，节省后续计算）
    hf, wf = img_face.shape[:2]
    if max(hf, wf) > MAX_IMAGE_DIM:
        scale = MAX_IMAGE_DIM / max(hf, wf)
        img = cv2.resize(img_face, (int(wf * scale), int(hf * scale)))
    else:
        img = img_face

    # 2. 曝光检测（始终运行）
    result.exposure_ok, result.exposure_score = check_exposure(
        img, config.over_threshold, config.under_threshold)

    # 3. 构图水平检测（可选）
    if config.enable_level:
        result.level_ok, result.level_score = check_level(
            img,
            method=config.level_method,
            angle_tolerance=config.level_angle_tolerance,
        )

    # 4. 模糊检测（可选）— v3.1: 多区域最清晰判断法
    if config.enable_blur:
        result.blur_ok, result.blur_score = check_blur(img, config.blur_threshold)

    # 5. 人脸检测（可选开关）
    if config.enable_face_detection:
        face_result = _detect_faces(img_face, mp_manager)  # 用高分辨率图像检测人脸

        if face_result and face_result.face_landmarks:
            result.face_detected = True
            result.face_count = len(face_result.face_landmarks)

            # 多人脸：每张脸独立评估，取最高总分（简单高效）
            best_eye_open = False
            best_eye_score = 0.0
            best_skin_ok = False
            best_skin_score = 0.0
            best_clarity_ok = True
            best_clarity_score = 1.0
            best_total = -1.0

            for landmarks in face_result.face_landmarks:
                eyes_open, eye_score = check_eyes_open(landmarks, img_face.shape, config.ear_threshold)
                skin_ok, skin_score = check_skin_tone(img_face, landmarks)
                total = eye_score + skin_score

                if total > best_total:
                    best_total = total
                    best_eye_open = eyes_open
                    best_eye_score = eye_score
                    best_skin_ok = skin_ok
                    best_skin_score = skin_score

                if config.enable_clarity:
                    clarity_ok, clarity_score = check_face_clarity(
                        img_face, landmarks, config.clarity_threshold)
                    if clarity_score > best_clarity_score:
                        best_clarity_ok = clarity_ok
                        best_clarity_score = clarity_score

            result.eyes_open = best_eye_open
            result.eye_score = best_eye_score
            result.skin_ok = best_skin_ok
            result.skin_score = best_skin_score
            if config.enable_clarity:
                result.clarity_ok = best_clarity_ok
                result.clarity_score = best_clarity_score
        else:
            result.error = "未检测到人脸"
    else:
        # 人脸检测关闭 — 仅检测曝光等，人脸相关项默认通过
        result.error = "人脸检测已关闭"

    # 释放临时图片
    del img_face, img

    return result
