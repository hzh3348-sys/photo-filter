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
            num_faces=5,              # v3.0: 支持多人脸（原来为1）
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


# ── 人脸检测（两轮，提升小脸检出率）─────────────────────

def _detect_faces(img, mp_manager, retry_with_upsample=True):
    """
    检测人脸，支持两轮检测提升小脸检出率。
    第一轮：原图检测
    第二轮（如果第一轮未检出）：放大图像后重试
    """
    h, w = img.shape[:2]
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    MPImage, ImageFormat = MediaPipeManager.get_mp_classes()
    mp_img = MPImage(image_format=ImageFormat.SRGB, data=rgb)

    try:
        landmarker = mp_manager.get_landmarker()
        face_result = landmarker.detect(mp_img)
    except Exception:
        return None

    # 第一轮成功 → 直接返回
    if face_result.face_landmarks:
        del rgb, mp_img
        return face_result

    # 第二轮：放大图像（适用于小脸照片）
    if retry_with_upsample and min(h, w) < 1200:
        scale = 1200 / min(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        upsampled = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        up_rgb = cv2.cvtColor(upsampled, cv2.COLOR_BGR2RGB)
        up_mp_img = MPImage(image_format=ImageFormat.SRGB, data=up_rgb)

        try:
            face_result2 = landmarker.detect(up_mp_img)
            del upsampled, up_rgb, up_mp_img
            if face_result2.face_landmarks:
                return face_result2
        except Exception:
            pass

    del rgb, mp_img
    return face_result  # 返回第一轮结果（空）


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

    # 1. 加载图片
    img = load_image(path)
    if img is None:
        result.error = "无法读取图片"
        return result

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
        face_result = _detect_faces(img, mp_manager)

        if face_result and face_result.face_landmarks:
            result.face_detected = True
            result.face_count = len(face_result.face_landmarks)

            # 多人脸：对每张脸评估，取最优
            best_eye_open = False
            best_eye_score = 0.0
            best_skin_ok = False
            best_skin_score = 0.0
            best_clarity_ok = True
            best_clarity_score = 1.0

            for i, landmarks in enumerate(face_result.face_landmarks):
                eyes_open, eye_score = check_eyes_open(landmarks, img.shape, config.ear_threshold)
                skin_ok, skin_score = check_skin_tone(img, landmarks)

                if i == 0 or (eyes_open and not best_eye_open) or (skin_ok and not best_skin_ok):
                    if eye_score + skin_score > best_eye_score + best_skin_score:
                        best_eye_open = eyes_open
                        best_eye_score = eye_score
                        best_skin_ok = skin_ok
                        best_skin_score = skin_score

                if config.enable_clarity:
                    clarity_ok, clarity_score = check_face_clarity(
                        img, landmarks, config.clarity_threshold)
                    if i == 0 or clarity_score > best_clarity_score:
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
    del img

    return result
