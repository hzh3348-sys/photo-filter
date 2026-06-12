"""
人脸清晰度评分 — 检测人脸的清晰度。
仅在检测到人脸时运行，综合人脸区域的局部锐度和对比度。
"""

import cv2
import numpy as np

from utils.constants import DEFAULT_CLARITY_THRESHOLD
from utils.constants import LEFT_EYE_IDX, RIGHT_EYE_IDX


def _get_face_bbox(landmarks, img_shape):
    """从关键点估算人脸边界框。"""
    h, w = img_shape[:2]
    xs, ys = [], []
    for lm in landmarks:
        xs.append(int(lm.x * w))
        ys.append(int(lm.y * h))

    if not xs:
        return 0, 0, w, h

    # 扩展 20% 边距
    x1, y1 = min(xs), min(ys)
    x2, y2 = max(xs), max(ys)
    pad_w = int((x2 - x1) * 0.2)
    pad_h = int((y2 - y1) * 0.2)

    x1 = max(0, x1 - pad_w)
    y1 = max(0, y1 - pad_h)
    x2 = min(w, x2 + pad_w)
    y2 = min(h, y2 + pad_h)

    return x1, y1, x2, y2


def check_face_clarity(img: np.ndarray, face_landmarks,
                       threshold: float = DEFAULT_CLARITY_THRESHOLD) -> tuple:
    """
    评估人脸区域的清晰度。
    face_landmarks: MediaPipe 单张人脸的关键点列表。
    返回 (是否合格: bool, 得分: float 0~1)。
    """
    h, w = img.shape[:2]
    x1, y1, x2, y2 = _get_face_bbox(face_landmarks, (h, w))

    if x2 - x1 < 20 or y2 - y1 < 20:
        # 人脸太小，无法评估
        return True, 1.0

    # 裁剪人脸区域
    face_region = img[y1:y2, x1:x2]
    if face_region.size == 0:
        return True, 1.0

    gray = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY)

    # 1. Laplacian 方差（锐度）
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

    # 2. 局部对比度（RMS contrast）
    contrast = float(np.std(gray.astype(np.float64)) / 128.0)
    contrast = min(contrast, 1.0)

    # 3. 综合评分
    # 人脸区域 Laplacian 方差通常比整图小，阈值约 50
    lap_score = min(laplacian_var / 100.0, 1.0)
    clarity_score = float(lap_score * 0.6 + contrast * 0.4)

    ok = clarity_score >= threshold

    return bool(ok), clarity_score
