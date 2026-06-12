"""
肤色检测 — MediaPipe 关键点采样 + LAB 色彩空间中位数分析。
v2.0: 使用中位数 + 扩大肤色范围，兼容深色皮肤。
"""

import numpy as np
import cv2

from utils.constants import (
    SKIN_L_MIN, SKIN_L_MAX,
    SKIN_A_MIN, SKIN_A_MAX,
    SKIN_B_MIN, SKIN_B_MAX,
    FACE_SKIN_IDX,
)


def check_skin_tone(img: np.ndarray, face_landmarks) -> tuple:
    """
    检测肤色是否自然。
    face_landmarks: MediaPipe FaceLandmarkerResult.face_landmarks[0] (list of NormalizedLandmark)
    返回 (是否合格: bool, 得分: float 0~1)。
    """
    h, w = img.shape[:2]
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)

    pixels = []
    for idx in FACE_SKIN_IDX:
        if idx < len(face_landmarks):
            lm = face_landmarks[idx]
            x, y = int(lm.x * w), int(lm.y * h)
            if 0 <= x < w and 0 <= y < h:
                pixels.append(lab[y, x])

    if len(pixels) < 5:
        return False, 0.0

    skin = np.array(pixels)
    # v2.0: 使用中位数 + 百分位数去噪
    L_m = float(np.percentile(skin[:, 0], 50))
    A_m = float(np.percentile(skin[:, 1], 50))
    B_m = float(np.percentile(skin[:, 2], 50))

    ok = (SKIN_L_MIN <= L_m <= SKIN_L_MAX and
          SKIN_A_MIN <= A_m <= SKIN_A_MAX and
          SKIN_B_MIN <= B_m <= SKIN_B_MAX)

    # 归一化得分
    lc = (SKIN_L_MIN + SKIN_L_MAX) / 2
    ac = (SKIN_A_MIN + SKIN_A_MAX) / 2
    bc = (SKIN_B_MIN + SKIN_B_MAX) / 2
    ls = max(0, 1 - abs(L_m - lc) / ((SKIN_L_MAX - SKIN_L_MIN) / 2))
    a_s = max(0, 1 - abs(A_m - ac) / ((SKIN_A_MAX - SKIN_A_MIN) / 2))
    bs = max(0, 1 - abs(B_m - bc) / ((SKIN_B_MAX - SKIN_B_MIN) / 2))
    score = float((ls + a_s + bs) / 3)

    return bool(ok), score
