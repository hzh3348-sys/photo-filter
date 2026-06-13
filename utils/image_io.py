"""
图片加载工具 — 支持 Unicode 路径 + RAW 格式 (v3.5)。
cv2.imread 在 Windows 上不支持中文路径，改用 imdecode。
RAW 格式通过 rawpy (LibRaw) 解码。
"""

from pathlib import Path
from typing import Optional

import numpy as np
import cv2

from .constants import MAX_IMAGE_DIM, RAW_EXTENSIONS


def _is_raw(path: Path) -> bool:
    """判断是否为 RAW 格式。"""
    return path.suffix.lower() in RAW_EXTENSIONS


def load_raw_image(path: Path, max_dim: int = MAX_IMAGE_DIM) -> Optional[np.ndarray]:
    """
    用 rawpy 解码 RAW 照片，返回 BGR 格式 numpy 数组。
    使用 half_size 快速解码，大图自动等比缩放。
    """
    try:
        import rawpy
    except ImportError:
        return None

    try:
        with rawpy.imread(str(path)) as raw:
            rgb = raw.postprocess(
                half_size=True,
                use_camera_wb=True,
                no_auto_bright=True,
                output_color=rawpy.ColorSpace.sRGB,
            )
    except Exception:
        return None

    if rgb is None or rgb.size == 0:
        return None

    h, w = rgb.shape[:2]
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        rgb = cv2.resize(rgb, (int(w * scale), int(h * scale)))

    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def load_raw_thumbnail(path: Path, size: int = 128) -> Optional[np.ndarray]:
    """
    从 RAW 文件提取内嵌 JPEG 缩略图（比完整解码快 10x+）。
    返回 RGB 格式 numpy 数组。
    """
    try:
        import rawpy
    except ImportError:
        return None

    try:
        with rawpy.imread(str(path)) as raw:
            thumb = raw.extract_thumb()
    except Exception:
        return None

    if thumb is None:
        return None

    # thumb.format 可能是 'jpeg' 或 'ppm'
    if hasattr(thumb, 'data') and thumb.data:
        img = cv2.imdecode(np.frombuffer(thumb.data, np.uint8), cv2.IMREAD_COLOR)
        if img is not None:
            h, w = img.shape[:2]
            if max(h, w) > size:
                scale = size / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)))
            return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return None


def load_image(path: Path, max_dim: int = MAX_IMAGE_DIM) -> Optional[np.ndarray]:
    """
    从路径加载图片，支持中文路径 + RAW 格式。
    返回 BGR 格式的 numpy 数组，大图自动等比缩放。
    失败返回 None。
    """
    # RAW 格式 → rawpy 解码
    if _is_raw(path):
        return load_raw_image(path, max_dim)

    # 标准格式 → cv2.imdecode
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
    """加载缩略图（RGB 格式），用于 UI 预览。RAW 用内嵌预览提速。"""
    # RAW 缩略图用嵌入 JPEG（快）
    if _is_raw(path):
        thumb = load_raw_thumbnail(path, size)
        if thumb is not None:
            return thumb
        # 回退到完整解码
        img = load_raw_image(path, max_dim=size * 2)
    else:
        img = load_image(path, max_dim=size * 2)

    if img is None:
        return None
    h, w = img.shape[:2]
    if max(h, w) > size:
        scale = size / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
