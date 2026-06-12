"""
图片加载工具 — 支持 Unicode 路径。
cv2.imread 在 Windows 上不支持中文路径，改用 imdecode。
"""

from pathlib import Path
from typing import Optional

import numpy as np
import cv2

from .constants import MAX_IMAGE_DIM


def load_image(path: Path, max_dim: int = MAX_IMAGE_DIM) -> Optional[np.ndarray]:
    """
    从路径加载图片，支持中文路径。
    返回 BGR 格式的 numpy 数组，大图自动等比缩放。
    失败返回 None。
    """
    try:
        with open(path, 'rb') as f:
            img_bytes = f.read()
    except (OSError, IOError):
        return None

    img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None

    h, w = img.shape[:2]
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)))

    return img


def load_thumbnail(path: Path, size: int = 128) -> Optional[np.ndarray]:
    """加载缩略图（RGB 格式），用于 UI 预览。"""
    img = load_image(path, max_dim=size * 2)
    if img is None:
        return None
    h, w = img.shape[:2]
    if max(h, w) > size:
        scale = size / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
