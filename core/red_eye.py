"""
红眼检测 — 基于 HSV 色彩空间的瞳孔红色像素分析。
v5.0: 利用 MediaPipe 眼部关键点定位瞳孔区域，
检测闪光灯造成的红眼现象。
"""

import numpy as np
import cv2

from utils.constants import LEFT_EYE_IDX, RIGHT_EYE_IDX
from utils.constants import (
    RED_EYE_HUE_MIN, RED_EYE_HUE_MAX,
    RED_EYE_HUE_MIN2, RED_EYE_HUE_MAX2,
    RED_EYE_SATURATION_MIN, RED_EYE_VALUE_MIN,
)


def _get_eye_roi(img, landmarks, eye_indices):
    """
    从图像中提取眼部区域（基于关键点外接矩形，向外扩展20%）。

    返回: (eye_roi, eye_bbox) 或 (None, None)
    """
    h, w = img.shape[:2]
    pts = []
    for idx in eye_indices:
        if idx < len(landmarks):
            lm = landmarks[idx]
            x, y = int(lm.x * w), int(lm.y * h)
            if 0 <= x < w and 0 <= y < h:
                pts.append([x, y])

    if len(pts) < 6:
        return None, None

    pts = np.array(pts, dtype=np.int32)

    # 计算外接矩形
    x_min, y_min = pts[:, 0].min(), pts[:, 1].min()
    x_max, y_max = pts[:, 0].max(), pts[:, 1].max()
    bw, bh = x_max - x_min, y_max - y_min

    # 向内外各扩展20%（捕获虹膜周边红色像素）
    pad_x = int(bw * 0.2)
    pad_y = int(bh * 0.2)
    x1 = max(0, x_min - pad_x)
    y1 = max(0, y_min - pad_y)
    x2 = min(w, x_max + pad_x)
    y2 = min(h, y_max + pad_y)

    roi = img[y1:y2, x1:x2]
    if roi.size == 0:
        return None, None

    return roi, (x1, y1, x2, y2)


def _count_red_pixels(eye_roi) -> float:
    """
    计算眼部 ROI 中红色/橙色像素的占比。

    HSV 中的红色分两段：0°~10° 和 170°~180°
    同时要求一定饱和度和明度，排除纯黑瞳孔和灰白像素。
    """
    if eye_roi is None or eye_roi.size == 0:
        return 0.0

    hsv = cv2.cvtColor(eye_roi, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]

    total = h.size

    # 红色 hue 段 1: 0°~10°
    red1 = (h >= RED_EYE_HUE_MIN) & (h <= RED_EYE_HUE_MAX)
    # 红色 hue 段 2: 170°~180°
    red2 = (h >= RED_EYE_HUE_MIN2) & (h <= RED_EYE_HUE_MAX2)

    # 满足饱和度 + 明度要求
    sat_ok = (s >= RED_EYE_SATURATION_MIN)
    val_ok = (v >= RED_EYE_VALUE_MIN)

    red_pixels = ((red1 | red2) & sat_ok & val_ok).sum()

    return float(red_pixels / total) if total > 0 else 0.0


def check_red_eye_single(img, landmarks, threshold: float = 0.08) -> tuple[bool, float]:
    """
    检测单张人脸是否有红眼。

    参数:
        img: BGR 格式图像
        landmarks: MediaPipe FaceLandmark 列表
        threshold: 红色像素占比阈值（默认 8%）

    返回:
        (是否合格, 红眼分数 0=严重红眼 1=无红眼)
    """
    # 检测左右眼
    left_roi, _ = _get_eye_roi(img, landmarks, LEFT_EYE_IDX)
    right_roi, _ = _get_eye_roi(img, landmarks, RIGHT_EYE_IDX)

    left_ratio = _count_red_pixels(left_roi)
    right_ratio = _count_red_pixels(right_roi)

    max_ratio = max(left_ratio, right_ratio)

    # 任一眼睛红色像素超过阈值即判定为红眼
    has_red_eye = left_ratio > threshold or right_ratio > threshold

    # 分数：1 - 红色像素占比归一化
    score = float(max(0.0, 1.0 - max_ratio / (threshold * 3)))

    return not has_red_eye, score


def check_red_eye_multi(img, face_landmarks_list, threshold: float = 0.08,
                        face_mode: str = "best") -> tuple[bool, float, int]:
    """
    检测多张人脸的紅眼情况。

    参数:
        img: BGR 格式图像
        face_landmarks_list: MediaPipe FaceLandmarkerResult.face_landmarks 列表
        threshold: 红色像素占比阈值
        face_mode: "best" 最优人脸 / "all" 所有人脸通过

    返回:
        (是否合格, 综合分数, 红眼人脸数)
    """
    if not face_landmarks_list:
        return True, 1.0, 0

    all_ok = True
    best_score = 1.0
    worst_score = 1.0
    red_eye_count = 0

    for landmarks in face_landmarks_list:
        ok, score = check_red_eye_single(img, landmarks, threshold)
        if not ok:
            red_eye_count += 1
            worst_score = min(worst_score, score)
        best_score = max(best_score, score)

        if face_mode == "all" and not ok:
            all_ok = False

    if face_mode == "best":
        # 最优模式：只要最优的那张脸没有红眼就算通过
        # (实际上红眼是闪光灯拍的问题，一张脸上有就整张照片不好，
        #  但用 best 模式时更多关注主要人物的脸)
        all_ok = red_eye_count == 0

    return all_ok, worst_score if red_eye_count > 0 else 1.0, red_eye_count
