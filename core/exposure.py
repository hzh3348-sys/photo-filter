"""
曝光检测 — 灰度直方图分析。
"""

import cv2
import numpy as np


def check_exposure(img: np.ndarray, over_th: float, under_th: float) -> tuple:
    """
    检测曝光是否正常。
    返回 (是否合格: bool, 得分: float 0~1)。
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    total = gray.size
    over_ratio = float(np.sum(gray > 250) / total)
    under_ratio = float(np.sum(gray < 15) / total)

    ok = over_ratio < over_th and under_ratio < under_th

    over_penalty = max(0, 1 - over_ratio / over_th) if over_th > 0 else 1
    under_penalty = max(0, 1 - under_ratio / under_th) if under_th > 0 else 1
    score = float(min(over_penalty, under_penalty))

    return bool(ok), score
