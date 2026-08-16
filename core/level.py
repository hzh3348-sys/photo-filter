"""
构图水平检测 — 两种方法可选：
1. 地平线检测 (horizon)：寻找长水平线，判断地平线是否倾斜（推荐，减少误判）
2. 通用检测 (general)：Canny + 霍夫变换 + MAD 角度一致性
"""

import cv2
import numpy as np

from utils.constants import (
    LEVEL_ANGLE_TOLERANCE,
    LEVEL_MIN_LINES,
    LEVEL_CONSISTENCY_THRESHOLD,
    DEFAULT_HORIZON_ANGLE_TOLERANCE,
    HORIZON_MIN_LINE_RATIO,
    HORIZON_CLUSTER_ANGLE_RANGE,
    HORIZON_MIN_CLUSTER_SIZE,
)


def _normalize_angle_deviation(angle_deg: float) -> float:
    """将线条角度转为距离最近轴线的偏离量 (0-45°)，0=完美对齐水平/垂直。"""
    a = abs(angle_deg) % 90
    if a > 45:
        a = 90 - a
    return a


# ═══════════════════════════════════════════════════════════════
# 方法一：地平线检测（推荐）
# ═══════════════════════════════════════════════════════════════

def check_level_horizon(
    img: np.ndarray,
    angle_tolerance: float = DEFAULT_HORIZON_ANGLE_TOLERANCE,
) -> tuple:
    """
    地平线检测法 — 专门寻找画面中的地平线/水平线。

    原理：
    1. 找出所有长且接近水平的线段（地平线候选）
    2. 按角度聚类，找最主要的水平线组
    3. 如果该组的倾斜角超过阈值 → 判定为倾斜
    4. 如果没有找到明显的地平线 → 不判定（通过）

    优势：复杂建筑线条、树木、自然场景不会误判，
         只有真正存在明显地平线且倾斜时才报警。

    返回 (是否合格: bool, 得分: float 0~1)。
    """
    h, w = img.shape[:2]

    # ── 第一步：边缘检测 ──
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 1.5)

    # 使用较低阈值获取更多边缘
    edges = cv2.Canny(blurred, 30, 100, apertureSize=3)

    # ── 第二步：霍夫变换检测线段 ──
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=50,
        minLineLength=int(w * HORIZON_MIN_LINE_RATIO),  # 只关心长线
        maxLineGap=int(w * 0.1),
    )

    if lines is None or len(lines) < 2:
        return True, 1.0  # 没有足够的长线段 → 无法判断 → 通过

    # ── 第三步：筛选近水平线段 ──
    # 计算每条线的角度，只保留接近水平的
    horizon_candidates = []
    for line in lines:
        # v5.2 修复：兼容 OpenCV 不同版本——
        # 旧版 HoughLinesP 返回 (N,1,4)，新版（4.12+）返回 (N,4)
        pts = line.reshape(-1)
        x1, y1, x2, y2 = int(pts[0]), int(pts[1]), int(pts[2]), int(pts[3])
        dx = x2 - x1
        dy = y2 - y1
        length = np.sqrt(dx*dx + dy*dy)

        if length < w * HORIZON_MIN_LINE_RATIO:
            continue  # 太短，不是地平线

        angle = np.arctan2(dy, dx) * 180.0 / np.pi  # -180° ~ 180°

        # 只保留接近水平（±30°以内）
        if abs(angle) > 30:
            continue

        horizon_candidates.append({
            'angle': angle,
            'length': length,
            'y_center': (y1 + y2) / 2,
        })

    if not horizon_candidates:
        return True, 1.0  # 没有近水平长线 → 无明确地平线 → 通过

    # ── 第四步：角度聚类找主导水平线组 ──
    angles = np.array([c['angle'] for c in horizon_candidates])
    lengths = np.array([c['length'] for c in horizon_candidates])

    # 使用加权中位数（长线权重更高）
    sorted_idx = np.argsort(angles)
    sorted_angles = angles[sorted_idx]
    sorted_lengths = lengths[sorted_idx]
    cumsum = np.cumsum(sorted_lengths)
    total = cumsum[-1]
    median_idx = np.searchsorted(cumsum, total / 2)
    dominant_angle = float(sorted_angles[min(median_idx, len(sorted_angles) - 1)])

    # 找出与主导角度接近的线（聚类）
    close_mask = np.abs(angles - dominant_angle) < HORIZON_CLUSTER_ANGLE_RANGE
    cluster_angles = angles[close_mask]
    cluster_lengths = lengths[close_mask]

    # 聚类总长度校验：地平线类线条总长应至少占图宽的60%
    # （长度是本质信号——单条贯穿画面的地平线（如海平面）也应触发检测，
    #   因此不再要求"至少3条线"，避免漏检清晰但单一的倾斜地平线）
    total_cluster_length = float(np.sum(cluster_lengths))
    if total_cluster_length < w * 0.6:
        return True, 1.0  # 聚类线条不够长 → 非明确地平线 → 通过

    # 聚类加权平均角度
    cluster_angle = float(np.average(cluster_angles, weights=cluster_lengths))

    # ── 第五步：判断倾斜 ──
    deviation = abs(cluster_angle)  # 偏离水平的角度

    if deviation <= angle_tolerance:
        # 合格：地平线接近水平
        score = 1.0
        ok = True
    else:
        # 倾斜：地平线明显歪了
        # 得分：tolerance 处得 0.5，2*tolerance 处得 0
        score = float(max(0, 1 - (deviation - angle_tolerance) / angle_tolerance))
        ok = False

    return bool(ok), score


# ═══════════════════════════════════════════════════════════════
# 方法二：通用检测（保留，放宽标准）
# ═══════════════════════════════════════════════════════════════

def check_level_general(
    img: np.ndarray,
    angle_tolerance: float = LEVEL_ANGLE_TOLERANCE,
    consistency_threshold: float = LEVEL_CONSISTENCY_THRESHOLD,
) -> tuple:
    """
    通用构图水平检测 — Canny + 霍夫变换 + MAD 角度一致性。
    如果线条角度集中且整体偏离轴线 → 判定倾斜；
    如果线条角度分散（复杂场景）→ 不判定。

    返回 (是否合格: bool, 得分: float 0~1)。
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 1.5)
    edges = cv2.Canny(blurred, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=80,
        minLineLength=60, maxLineGap=15,
    )

    if lines is None or len(lines) < LEVEL_MIN_LINES:
        return True, 1.0

    deviations = []
    for line in lines:
        # v5.2 修复：兼容 OpenCV 不同版本返回结构 (N,1,4) / (N,4)
        pts = line.reshape(-1)
        x1, y1, x2, y2 = int(pts[0]), int(pts[1]), int(pts[2]), int(pts[3])
        angle = np.arctan2(y2 - y1, x2 - x1) * 180.0 / np.pi
        deviations.append(_normalize_angle_deviation(angle))

    deviations = np.array(deviations)
    median_dev = float(np.median(deviations))
    mad = float(np.median(np.abs(deviations - median_dev)))

    is_consistent = mad < consistency_threshold
    is_deviated = median_dev > angle_tolerance

    ok = not (is_consistent and is_deviated)
    score = 1.0 if ok else float(max(0, 1 - median_dev / 25.0))

    return bool(ok), score


# ═══════════════════════════════════════════════════════════════
# 统一入口
# ═══════════════════════════════════════════════════════════════

def check_level(
    img: np.ndarray,
    method: str = "horizon",
    angle_tolerance: float = DEFAULT_HORIZON_ANGLE_TOLERANCE,
    consistency_threshold: float = LEVEL_CONSISTENCY_THRESHOLD,
) -> tuple:
    """
    构图水平检测统一入口。

    参数：
        method: "horizon" (地平线检测) 或 "general" (通用检测)
        angle_tolerance: 允许的倾斜角度 (地平线默认5°，通用默认9°)
        consistency_threshold: 仅通用方法使用，角度一致性阈值

    返回 (是否合格: bool, 得分: float 0~1)。
    """
    if method == "general":
        return check_level_general(img, angle_tolerance, consistency_threshold)
    else:
        return check_level_horizon(img, angle_tolerance)
