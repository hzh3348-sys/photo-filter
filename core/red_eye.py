"""
红眼检测 — 基于 HSV 色彩空间的瞳孔红色像素分析。
v5.0: 利用 MediaPipe 眼部关键点定位瞳孔区域，
检测闪光灯造成的红眼现象。

改进 (v5.1):
- 瞳孔聚焦：以 MediaPipe 虹膜中心（468/473）为中心取小 ROI，
  不再把整个眼睑+眼皮区域算进来（降低红眼皮/红眼影误报）。
- 连通域过滤：红色像素必须形成 ≥3 像素的连通斑块，排除零散噪点。
"""

import numpy as np
import cv2

from utils.constants import LEFT_EYE_IDX, RIGHT_EYE_IDX
from utils.constants import (
    RED_EYE_HUE_MIN, RED_EYE_HUE_MAX,
    RED_EYE_HUE_MIN2, RED_EYE_HUE_MAX2,
    RED_EYE_SATURATION_MIN, RED_EYE_VALUE_MIN,
    RED_EYE_MIN_BLOB_SIZE,
    RED_EYE_PUPIL_W_RATIO, RED_EYE_PUPIL_H_RATIO,
    LEFT_IRIS_CENTER_IDX, RIGHT_IRIS_CENTER_IDX,
)


def _get_pupil_roi(img, landmarks, eye_indices, iris_center_idx):
    """
    提取瞳孔区域 ROI：以虹膜中心为中心的小矩形（宽=眼宽×0.6，高=眼高×0.8）。
    虹膜中心不可用时退回眼部外接矩形中心。

    返回: pupil_roi 或 None
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
        return None

    pts = np.array(pts, dtype=np.int32)
    x_min, y_min = pts[:, 0].min(), pts[:, 1].min()
    x_max, y_max = pts[:, 0].max(), pts[:, 1].max()
    bw, bh = x_max - x_min, y_max - y_min
    if bw < 4 or bh < 2:
        return None

    # 虹膜中心（关键点 468/473）
    if iris_center_idx < len(landmarks):
        cx = int(landmarks[iris_center_idx].x * w)
        cy = int(landmarks[iris_center_idx].y * h)
    else:
        cx, cy = (x_min + x_max) // 2, (y_min + y_max) // 2

    # 瞳孔 ROI
    pw = max(4, int(bw * RED_EYE_PUPIL_W_RATIO))
    ph = max(3, int(bh * RED_EYE_PUPIL_H_RATIO))
    x1 = max(0, cx - pw // 2)
    y1 = max(0, cy - ph // 2)
    x2 = min(w, x1 + pw)
    y2 = min(h, y1 + ph)

    roi = img[y1:y2, x1:x2]
    return roi if roi.size > 0 else None


def _count_red_pixels(eye_roi) -> float:
    """
    计算瞳孔 ROI 中红色/橙色像素的占比（含连通域过滤）。

    HSV 中的红色分两段：0°~10° 和 170°~180°
    同时要求一定饱和度和明度，排除纯黑瞳孔和灰白像素；
    红色像素必须形成 ≥MIN_BLOB_SIZE 的连通斑块，排除零散噪点
    （眼影亮片、反光、压缩伪影等）。
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

    red_mask = ((red1 | red2) & sat_ok & val_ok).astype(np.uint8) * 255

    # 连通域过滤：只统计面积 >= MIN_BLOB_SIZE 的红色斑块
    num, _, stats, _ = cv2.connectedComponentsWithStats(red_mask, connectivity=8)
    blob_pixels = 0
    for i in range(1, num):
        if stats[i, cv2.CC_STAT_AREA] >= RED_EYE_MIN_BLOB_SIZE:
            blob_pixels += int(stats[i, cv2.CC_STAT_AREA])

    return float(blob_pixels / total) if total > 0 else 0.0


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
    # 检测左右眼（瞳孔聚焦 ROI）
    left_roi = _get_pupil_roi(img, landmarks, LEFT_EYE_IDX, LEFT_IRIS_CENTER_IDX)
    right_roi = _get_pupil_roi(img, landmarks, RIGHT_EYE_IDX, RIGHT_IRIS_CENTER_IDX)

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
