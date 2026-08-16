"""
肤色检测 — 面部区域采样 + LAB 色彩空间分析 (v5.0)。

改进：不再依赖单个关键点采样（极易受定位误差影响），
      改用全部 468 个面部关键点构建凸包 → 内缩 → 区域采样。
      即使部分关键点偏移，整体面部区域仍然准确。
"""

import numpy as np
import cv2

from utils.constants import (
    SKIN_L_MIN, SKIN_L_MAX,
    SKIN_A_MIN, SKIN_A_MAX,
    SKIN_B_MIN, SKIN_B_MAX,
)


def _build_face_region_mask(face_landmarks, img_shape):
    """
    用全部面部关键点构建凸包 → 向内腐蚀 15% → 得到纯净面部区域 mask。
    返回 None 如果关键点不足。
    """
    h, w = img_shape[:2]

    # 收集所有有效的面部关键点
    points = []
    for lm in face_landmarks:
        x, y = int(lm.x * w), int(lm.y * h)
        if 0 <= x < w and 0 <= y < h:
            points.append([x, y])

    if len(points) < 30:
        return None

    points = np.array(points, dtype=np.int32)

    # 构建凸包
    hull = cv2.convexHull(points)
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillConvexPoly(mask, hull, 255)

    # 向内腐蚀：去除边缘（可能包含头发、背景、帽子等）
    # 腐蚀量 = 凸包短边的 12%
    rect = cv2.boundingRect(hull)
    if not isinstance(rect, (tuple, list)) or len(rect) < 4:
        return mask  # 回退：不腐蚀直接返回
    x, y, bw, bh = rect
    erosion_radius = int(min(bw, bh) * 0.12)
    if erosion_radius > 3:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                           (erosion_radius * 2 + 1, erosion_radius * 2 + 1))
        mask = cv2.erode(mask, kernel, iterations=1)

    return mask


def check_skin_tone(img: np.ndarray, face_landmarks, lab: np.ndarray = None) -> tuple:
    """
    检测面部区域肤色是否自然。

    参数:
        img: BGR 格式图像
        face_landmarks: MediaPipe FaceLandmarkerResult.face_landmarks[0]
        lab: 可选，预计算的 LAB 图像（BGR2LAB 结果）。
             多人脸场景由调用方只转换一次并复用，避免每张人脸重复全图转换（性能优化）。

    返回:
        (是否合格: bool, 得分: float 0~1)
    """
    # ── 1. 构建面部区域 mask ──
    mask = _build_face_region_mask(face_landmarks, img.shape)
    if mask is None or cv2.countNonZero(mask) < 200:
        return False, 0.0

    # ── 2. 区域采样（复用调用方传入的 LAB，避免重复转换）──
    if lab is None:
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    face_pixels = lab[mask > 0]

    if face_pixels.size < 200:
        return False, 0.0

    # ── 3. 8 位 LAB → 标准 L*a*b* 单位 ──
    # OpenCV 8 位 LAB：L8 = L*×255/100，A8 = a*+128，B8 = b*+128
    # 常量 SKIN_* 使用标准 L*a*b* 单位（L* 0~100，a*/b* -128~127），
    # 必须先转换再比较，否则 8 位 A(≈128) 远超 a* 上限(50) → 自然肤色全被误杀（v5.1 修复）
    lab_f = face_pixels.astype(np.float32)
    L_vals = lab_f[:, 0] * (100.0 / 255.0)
    A_vals = lab_f[:, 1] - 128.0
    B_vals = lab_f[:, 2] - 128.0

    # ── 4. 鲁棒统计 ──
    # 用 10% 和 90% 百分位数去除极端值，然后取中位数
    # 极端值可能来自：高光反射、阴影、头发混入等
    L_lo, L_hi = np.percentile(L_vals, [10, 90])
    A_lo, A_hi = np.percentile(A_vals, [10, 90])
    B_lo, B_hi = np.percentile(B_vals, [10, 90])

    # 用 [10%, 90%] 范围内的均值作为肤色表征
    in_range = (
        (L_vals >= L_lo) & (L_vals <= L_hi) &
        (A_vals >= A_lo) & (A_vals <= A_hi) &
        (B_vals >= B_lo) & (B_vals <= B_hi)
    )
    core_pixels_l = L_vals[in_range]
    core_pixels_a = A_vals[in_range]
    core_pixels_b = B_vals[in_range]

    if core_pixels_l.size < 100:
        # 回退到中位数
        L_m = float(np.percentile(L_vals, 50))
        A_m = float(np.percentile(A_vals, 50))
        B_m = float(np.percentile(B_vals, 50))
    else:
        L_m = float(np.mean(core_pixels_l))
        A_m = float(np.mean(core_pixels_a))
        B_m = float(np.mean(core_pixels_b))

    # ── 5. 宽松判断 ──
    ok = (SKIN_L_MIN <= L_m <= SKIN_L_MAX and
          SKIN_A_MIN <= A_m <= SKIN_A_MAX and
          SKIN_B_MIN <= B_m <= SKIN_B_MAX)

    # 归一化得分（到 LAB 范围中心越近越高）
    lc = (SKIN_L_MIN + SKIN_L_MAX) / 2
    ac = (SKIN_A_MIN + SKIN_A_MAX) / 2
    bc = (SKIN_B_MIN + SKIN_B_MAX) / 2
    ls = max(0, 1 - abs(L_m - lc) / ((SKIN_L_MAX - SKIN_L_MIN) / 2))
    a_s = max(0, 1 - abs(A_m - ac) / ((SKIN_A_MAX - SKIN_A_MIN) / 2))
    bs = max(0, 1 - abs(B_m - bc) / ((SKIN_B_MAX - SKIN_B_MIN) / 2))
    score = float((ls + a_s + bs) / 3)

    return bool(ok), score
