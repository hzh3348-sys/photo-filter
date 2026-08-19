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
from .expression import check_expression_multi  # v5.0
from .red_eye import check_red_eye_multi         # v5.0
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
            output_face_blendshapes=True,   # v5.0: 开启表情检测
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


# ── 人脸检测（三轮 + YuNet 双引擎，极致检出）─────────────

def _detect_faces(img, mp_manager, yunet_manager=None):
    """
    人脸检测：
    1) MediaPipe 三轮（原图 → 1200px → 1800px + 中心裁剪），大幅提升小脸/侧脸/暗光检出率；
    2) YuNet 双引擎补充（v5.3.1）：MediaPipe 漏检的人脸框 → 裁剪 → MediaPipe 关键点，
       合并进结果。模型缺失时自动降级为纯 MediaPipe。
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

    face_result = None

    # 第1轮：原图
    face_result = _try_detect(img)

    if not (face_result and face_result.face_landmarks):
        # 第2轮：放大到短边1200px
        if min(h, w) < 1200:
            scale = 1200 / min(h, w)
            up = cv2.resize(img, (int(w * scale), int(h * scale)),
                            interpolation=cv2.INTER_LANCZOS4)
            face_result = _try_detect(up)
            del up

    if not (face_result and face_result.face_landmarks):
        # 第3轮：放大到短边1800px
        if min(h, w) < 1800:
            scale = 1800 / min(h, w)
            up2 = cv2.resize(img, (int(w * scale), int(h * scale)),
                             interpolation=cv2.INTER_LANCZOS4)
            face_result = _try_detect(up2)
            del up2

    if not (face_result and face_result.face_landmarks):
        # 第3轮备选：中心50%区域放大（人脸通常在中间）
        cy, cx = h // 2, w // 2
        crop = img[cy//2:cy+cy//2, cx//2:cx+cx//2]
        if crop.size > 0 and min(crop.shape[:2]) > 100:
            scale = 1200 / min(crop.shape[:2])
            crop_up = cv2.resize(crop, (int(crop.shape[1] * scale), int(crop.shape[0] * scale)),
                                 interpolation=cv2.INTER_LANCZOS4)
            face_result = _try_detect(crop_up)
            del crop_up

    # ── YuNet 双引擎补充（v5.3.1）──
    if yunet_manager is not None:
        face_result = _supplement_with_yunet(face_result, img, mp_manager, yunet_manager)

    return face_result


def _supplement_with_yunet(face_result, img, mp_manager, yunet_manager):
    """
    用 YuNet 检测 MediaPipe 漏掉的人脸：
    1) 计算已有 MediaPipe 人脸的包围盒；
    2) YuNet 检出框中与已有框 IoU 过高的跳过；
    3) 对新框裁剪（外扩 30%）→ MediaPipe landmarker 补检关键点 → 映射回原图坐标；
    4) 合并进结果（face_landmarks 与 face_blendshapes 保持对齐）。

    模型不可用 / 无新框 / 补检失败时返回原 face_result，不影响现有流程。
    """
    from types import SimpleNamespace
    from .yunet import (detect_faces_yunet, merge_boxes, bbox_from_landmarks,
                        expand_bbox, map_crop_to_orig)

    existing_lms = []
    existing_bs = []
    if face_result is not None:
        existing_lms = list(face_result.face_landmarks or [])
        existing_bs = list(face_result.face_blendshapes or [])

    existing_bboxes = [bbox_from_landmarks(lms, img.shape) for lms in existing_lms]
    candidates = detect_faces_yunet(img, yunet_manager)
    new_boxes = merge_boxes(existing_bboxes, candidates)
    if not new_boxes:
        return face_result

    MPImage, ImageFormat = MediaPipeManager.get_mp_classes()
    landmarker = mp_manager.get_landmarker()
    added_lms = []
    added_bs = []

    for cand in new_boxes:
        x, y, bw, bh = expand_bbox(cand["bbox"], img.shape)
        crop = img[y:y + bh, x:x + bw]
        if crop.size == 0:
            continue
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        mp_img = MPImage(image_format=ImageFormat.SRGB, data=rgb)
        try:
            res = landmarker.detect(mp_img)
        except Exception:
            res = None
        del rgb, mp_img
        if res is None or not res.face_landmarks:
            continue
        for lms in res.face_landmarks:
            mapped = map_crop_to_orig(lms, (x, y, bw, bh), img.shape)
            if mapped:
                added_lms.append(mapped)
        if res.face_blendshapes:
            added_bs.extend(res.face_blendshapes)

    if not added_lms:
        return face_result

    merged = SimpleNamespace(
        face_landmarks=existing_lms + added_lms,
        face_blendshapes=existing_bs + added_bs,
    )
    return merged


# ── 单张照片检测 ──────────────────────────────────────────

def detect_single_photo(
    path: Path,
    config: DetectionConfig,
    mp_manager: MediaPipeManager,
    yunet_manager=None,
) -> PhotoResult:
    """
    对单张照片运行完整的检测流程。
    此函数可在任意线程中调用（前提是 mp_manager 支持线程局部实例）。
    """
    result = PhotoResult(path=path)
    # v5.3.1: 人脸子检测可独立开关——关闭时对应字段默认通过
    if not config.enable_eyes:
        result.eyes_open = True
        result.eye_score = 1.0
    if not config.enable_skin:
        result.skin_ok = True
        result.skin_score = 1.0
    result.level_enabled = config.enable_level
    result.blur_enabled = config.enable_blur
    result.clarity_enabled = config.enable_clarity
    result.duplicate_enabled = config.enable_duplicate
    result.expression_enabled = config.enable_expression
    result.red_eye_enabled = config.enable_red_eye
    result.face_mode = config.face_mode

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

    # 2. 曝光检测（始终运行，纯中心加权，与人脸完全独立）
    try:
        result.exposure_ok, result.exposure_score = check_exposure(
            img, config.over_threshold, config.under_threshold)
    except Exception as e:
        result.error = f"曝光检测异常: {e}"
        return result

    # 3. 构图水平检测（可选）
    # v5.2: 异常隔离——单张照片构图检测出错只记提示，不影响曝光等其他检测
    if config.enable_level:
        try:
            result.level_ok, result.level_score = check_level(
                img,
                method=config.level_method,
                angle_tolerance=config.level_angle_tolerance,
            )
        except Exception as e:
            result.note = f"构图检测异常: {e}"

    # 4. 模糊检测（可选）
    if config.enable_blur:
        try:
            result.blur_ok, result.blur_score = check_blur(img, config.blur_threshold)
        except Exception as e:
            result.note = f"模糊检测异常: {e}"

    # 5. 人脸检测（可选开关）— 与曝光完全独立，互不依赖
    face_result = None
    if config.enable_face_detection:
        yu = yunet_manager if config.enable_yunet else None   # v5.3.1: YuNet 可开关
        face_result = _detect_faces(img_face, mp_manager, yu)

    # 6. 人脸相关检测（睁眼、肤色、表情、红眼等）
    if config.enable_face_detection and face_result and face_result.face_landmarks:
        result.face_detected = True
        result.face_count = len(face_result.face_landmarks)
        result.face_count_total = len(face_result.face_landmarks)

        # ── LAB 全图只转换一次，多人脸复用（性能：避免每张脸重复全图转换）──
        lab = cv2.cvtColor(img_face, cv2.COLOR_BGR2LAB)

        # ── 按 face_mode 策略评估睁眼 + 肤色 + 清晰度 ──
        if config.face_mode == "all":
            _evaluate_all_faces(result, face_result, img_face, config, lab)
        else:
            _evaluate_best_face(result, face_result, img_face, config, lab)

        # ── v5.0: 表情检测（可选）──
        # v5.2: 加异常隔离——单张照片的表情数据异常不再让整张照片检测失败
        if config.enable_expression and face_result.face_blendshapes:
            try:
                exp_ok, exp_score, exp_detail, _, _ = check_expression_multi(
                    face_result.face_blendshapes,
                    smile_threshold=config.expression_smile_threshold,
                    face_mode=config.face_mode,
                )
                result.expression_ok = exp_ok
                result.expression_score = exp_score
                result.expression_detail = exp_detail
            except Exception as e:
                result.note = f"表情检测异常: {e}"

        # ── v5.0: 红眼检测（可选）──
        if config.enable_red_eye:
            try:
                re_ok, re_score, re_count = check_red_eye_multi(
                    img_face, face_result.face_landmarks,
                    threshold=config.red_eye_threshold,
                    face_mode=config.face_mode,
                )
                result.red_eye_ok = re_ok
                result.red_eye_score = re_score
                result.red_eye_count = re_count
            except Exception as e:
                result.note = f"红眼检测异常: {e}"
    elif config.enable_face_detection:
        # 人脸检测开启但未检测到人脸 —— 提示而非错误（照片仍可能通过）
        result.note = "未检测到人脸"
    else:
        # 人脸检测关闭 — 仅检测曝光等，人脸相关项默认通过
        result.note = "人脸检测已关闭"

    # 释放临时图片
    del img_face, img

    return result


def _evaluate_best_face(
    result: PhotoResult, face_result, img_face, config: DetectionConfig, lab: np.ndarray,
):
    """
    最优人脸策略：在所有人脸中取评分最高的一张进行评估。
    适用于生活照场景（单人照或小合照），只需有人拍得好就行。
    """
    best_eye_open = False
    best_eye_score = 0.0
    best_skin_ok = False
    best_skin_score = 0.0
    best_clarity_ok = True
    best_clarity_score = 1.0
    best_total = -1.0
    fail_count = 0
    eye_fail = 0
    skin_fail = 0

    for landmarks in face_result.face_landmarks:
        # v5.3.1: 睁眼/肤色可独立关闭（关闭时按通过处理，不参与 fail 统计）
        if config.enable_eyes:
            try:
                eyes_open, eye_score = check_eyes_open(landmarks, img_face.shape, config.ear_threshold)
            except Exception:
                eyes_open, eye_score = True, 0.5
        else:
            eyes_open, eye_score = True, 1.0
        if config.enable_skin:
            try:
                skin_ok, skin_score = check_skin_tone(img_face, landmarks, lab=lab)
            except Exception:
                skin_ok, skin_score = True, 0.5
        else:
            skin_ok, skin_score = True, 1.0
        total = eye_score + skin_score

        if not eyes_open:
            eye_fail += 1
        if not skin_ok:
            skin_fail += 1
        if not eyes_open or not skin_ok:
            fail_count += 1

        if total > best_total:
            best_total = total
            best_eye_open = eyes_open
            best_eye_score = eye_score
            best_skin_ok = skin_ok
            best_skin_score = skin_score

        if config.enable_clarity:
            try:
                clarity_ok, clarity_score = check_face_clarity(
                    img_face, landmarks, config.clarity_threshold)
            except Exception:
                clarity_ok, clarity_score = True, 0.5
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

    # 记录统计信息（即使 best 模式也记录，方便用户了解）
    result.face_count_fail = fail_count
    detail_parts = []
    if eye_fail > 0:
        detail_parts.append(f"{eye_fail}人闭眼")
    if skin_fail > 0:
        detail_parts.append(f"{skin_fail}人肤色异常")
    result.face_detail = ", ".join(detail_parts)


def _evaluate_all_faces(
    result: PhotoResult, face_result, img_face, config: DetectionConfig, lab: np.ndarray,
):
    """
    所有人脸策略：每张人脸都必须通过睁眼 + 肤色检测。
    适用于会议/活动合照场景，任何一个人出问题就淘汰照片。
    """
    all_eyes_open = True
    all_skin_ok = True
    all_clarity_ok = True
    worst_eye_score = 1.0
    worst_skin_score = 1.0
    worst_clarity_score = 1.0
    eye_fail = 0
    skin_fail = 0
    clarity_fail = 0

    for landmarks in face_result.face_landmarks:
        # v5.3.1: 睁眼/肤色可独立关闭
        if config.enable_eyes:
            try:
                eyes_open, eye_score = check_eyes_open(landmarks, img_face.shape, config.ear_threshold)
            except Exception:
                eyes_open, eye_score = True, 0.5
        else:
            eyes_open, eye_score = True, 1.0
        if config.enable_skin:
            try:
                skin_ok, skin_score = check_skin_tone(img_face, landmarks, lab=lab)
            except Exception:
                skin_ok, skin_score = True, 0.5
        else:
            skin_ok, skin_score = True, 1.0

        if not eyes_open:
            all_eyes_open = False
            eye_fail += 1
        if not skin_ok:
            all_skin_ok = False
            skin_fail += 1

        worst_eye_score = min(worst_eye_score, eye_score)
        worst_skin_score = min(worst_skin_score, skin_score)

        if config.enable_clarity:
            try:
                clarity_ok, clarity_score = check_face_clarity(
                    img_face, landmarks, config.clarity_threshold)
            except Exception:
                clarity_ok, clarity_score = True, 0.5
            if not clarity_ok:
                all_clarity_ok = False
                clarity_fail += 1
            worst_clarity_score = min(worst_clarity_score, clarity_score)

    result.eyes_open = all_eyes_open
    result.eye_score = worst_eye_score
    result.skin_ok = all_skin_ok
    result.skin_score = worst_skin_score
    if config.enable_clarity:
        result.clarity_ok = all_clarity_ok
        result.clarity_score = worst_clarity_score

    # 统计信息
    total_fail = eye_fail + skin_fail + clarity_fail
    result.face_count_fail = total_fail
    detail_parts = []
    if eye_fail > 0:
        detail_parts.append(f"{eye_fail}人闭眼")
    if skin_fail > 0:
        detail_parts.append(f"{skin_fail}人肤色异常")
    if clarity_fail > 0:
        detail_parts.append(f"{clarity_fail}人模糊")
    result.face_detail = ", ".join(detail_parts)
