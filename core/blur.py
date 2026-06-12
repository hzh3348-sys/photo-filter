"""
模糊检测 — 多区域 Laplacian 方差 + 最清晰区域判断法。

原理：将图像分为4×4网格，计算每格Laplacian方差，
      取前25%最清晰区域的均值作为图像锐度。
      如果最清晰的几个区域都不够锐 → 确实模糊。
      如果至少有几个区域锐利 → 可能是浅景深/背景虚化 → 合格。

优势：
- 浅景深人像（人脸清晰、背景虚化）→ 面部区域锐利 → 通过
- 风光照中有纹理区域（树叶、建筑）→ 通过
- 真正模糊的照片 → 所有区域都模糊 → 检测
"""

import cv2
import numpy as np

from utils.constants import DEFAULT_BLUR_THRESHOLD

# 标准化分析尺寸（长边），保证不同分辨率照片阈值一致
_BLUR_ANALYSIS_SIZE = 800


def _lap_var(gray_patch: np.ndarray) -> float:
    """计算灰度块的 Laplacian 方差，保护除零。"""
    var = cv2.Laplacian(gray_patch, cv2.CV_64F).var()
    return float(var)


def check_blur(img: np.ndarray, threshold: float = DEFAULT_BLUR_THRESHOLD) -> tuple:
    """
    多区域最清晰判断法。
    返回 (是否合格: bool, 得分: float 0~1)。
    得分 1 = 非常清晰，得分 0 = 极其模糊。
    """
    h, w = img.shape[:2]

    # ── 缩放到标准尺寸，保证阈值在不同分辨率照片间可比 ──
    scale = _BLUR_ANALYSIS_SIZE / max(h, w) if max(h, w) > _BLUR_ANALYSIS_SIZE else 1.0
    if scale < 1.0:
        work_img = cv2.resize(img, (int(w * scale), int(h * scale)))
    else:
        work_img = img
    gray = cv2.cvtColor(work_img, cv2.COLOR_BGR2GRAY)
    wh, ww = gray.shape

    # ── 4×4 网格，计算每格 Laplacian 方差 ──
    grid_rows, grid_cols = 4, 4
    cell_h, cell_w = wh // grid_rows, ww // grid_cols
    variances = []
    for r in range(grid_rows):
        for c in range(grid_cols):
            y1, y2 = r * cell_h, (r + 1) * cell_h
            x1, x2 = c * cell_w, (c + 1) * cell_w
            if y2 <= y1 or x2 <= x1:
                continue
            patch = gray[y1:y2, x1:x2]
            variances.append(_lap_var(patch))

    if not variances:
        return True, 1.0

    variances = np.array(variances)

    # ── 取前 25% 最清晰区域的均值 ──
    top_k = max(1, len(variances) // 4)
    top_indices = np.argpartition(variances, -top_k)[-top_k:]
    sharpness = float(np.mean(variances[top_indices]))

    # ── 判断 ──
    ok = sharpness >= threshold

    # 得分：threshold 处 ≈ 0.5，2*threshold 处 ≈ 1.0
    if sharpness <= 0:
        score = 0.0
    else:
        score = float(min(sharpness / (threshold * 2), 1.0))

    return bool(ok), score
