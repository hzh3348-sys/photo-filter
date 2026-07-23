"""
曝光检测 — 极简实现 (v5.0)。

只做一件事：统计灰度直方图中极端像素的比例。
过曝阈值默认 0.50（50%），欠曝默认 0.50。
照片可以后期处理，只拦截真正全毁的极端情况。
"""

import cv2
import numpy as np


def check_exposure(img: np.ndarray, over_th: float, under_th: float) -> tuple:
    """
    检测曝光是否正常。

    参数:
        img: BGR 图像
        over_th: 过曝容忍度（默认 0.50）
        under_th: 欠曝容忍度（默认 0.50）

    返回:
        (是否合格: bool, 得分: float 0~1)
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    total = int(gray.size)
    over_count = int((gray > 250).sum())
    under_count = int((gray < 15).sum())

    over_ratio = over_count / total
    under_ratio = under_count / total

    over_ok = over_ratio < over_th
    under_ok = under_ratio < under_th
    ok = bool(over_ok and under_ok)

    # 得分
    if over_th > 0:
        over_score = max(0.0, 1.0 - over_ratio / over_th)
    else:
        over_score = 1.0
    if under_th > 0:
        under_score = max(0.0, 1.0 - under_ratio / under_th)
    else:
        under_score = 1.0

    score = float(min(over_score, under_score))
    return ok, score
