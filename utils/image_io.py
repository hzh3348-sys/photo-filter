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


def _is_raw(path) -> bool:
    """判断是否为 RAW 格式（兼容 str 与 Path 入参）。"""
    return Path(path).suffix.lower() in RAW_EXTENSIONS


def _extract_jpeg_from_raw_bytes(data: bytes) -> Optional[np.ndarray]:
    """
    从 RAW 文件二进制数据中扫描提取最大的 JPEG 图像。
    用于回退：当 rawpy 完全不支持该相机时（LibRaw 太老）。
    返回 BGR 格式 numpy 数组，失败返回 None。
    """
    import struct
    jpeg_start = b'\xff\xd8\xff'
    best_img = None
    best_area = 0
    pos = 0
    while True:
        idx = data.find(jpeg_start, pos)
        if idx < 0:
            break
        # 搜索 JPEG 结束标记 FF D9
        end_idx = data.find(b'\xff\xd9', idx + 3)
        if end_idx < 0:
            break
        jpeg_data = data[idx:end_idx + 2]
        if len(jpeg_data) > 10000:  # 忽略太小的缩略图（<10KB）
            img = cv2.imdecode(np.frombuffer(jpeg_data, np.uint8), cv2.IMREAD_COLOR)
            if img is not None:
                area = img.shape[0] * img.shape[1]
                if area > best_area:
                    best_img = img
                    best_area = area
        pos = end_idx + 2
    return best_img


def load_raw_image(path: Path, max_dim: int = MAX_IMAGE_DIM) -> Optional[np.ndarray]:
    """
    解码 RAW 照片，三层回退策略：
    1. rawpy 完整解码 (half_size, 快)
    2. rawpy 提取内嵌 JPEG 预览
    3. 二进制扫描提取最大 JPEG（兼容 LibRaw 不支持的新相机）

    返回 BGR 格式 numpy 数组。
    """
    try:
        import rawpy
    except ImportError:
        return None

    rgb = None

    # ── 第1层：rawpy 完整解码 ──
    try:
        with rawpy.imread(str(path)) as raw:
            rgb = raw.postprocess(
                half_size=True,
                use_camera_wb=True,
                no_auto_bright=True,
                output_color=rawpy.ColorSpace.sRGB,
            )
    except Exception:
        pass

    # ── 第2层：rawpy 内嵌缩略图 ──
    if rgb is None:
        try:
            with rawpy.imread(str(path)) as raw:
                thumb = raw.extract_thumb()
                if thumb is not None and hasattr(thumb, 'data') and thumb.data:
                    img = cv2.imdecode(np.frombuffer(thumb.data, np.uint8), cv2.IMREAD_COLOR)
                    if img is not None:
                        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        except Exception:
            pass

    # ── 第3层：二进制扫描 RAW 文件中的 JPEG ──
    if rgb is None:
        try:
            with open(path, 'rb') as f:
                raw_bytes = f.read()
            img = _extract_jpeg_from_raw_bytes(raw_bytes)
            if img is not None:
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        except Exception:
            pass

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


def load_image(path: Path, max_dim: int = MAX_IMAGE_DIM,
                 reduced: Optional[int] = None) -> Optional[np.ndarray]:
    """
    从路径加载图片，支持中文路径 + RAW 格式。
    返回 BGR 格式的 numpy 数组，大图自动等比缩放。
    失败返回 None。

    reduced: 仅对 JPEG 有效，用 IMREAD_REDUCED_COLOR_x 做 DCT 降采样解码
             （2=1/2, 4=1/4, 8=1/8 尺寸），缩略图场景提速数倍（v5.3.1）。
    """
    # RAW 格式 → rawpy 解码
    if _is_raw(path):
        return load_raw_image(path, max_dim)

    # 标准格式 → cv2.imdecode（JPEG 支持降采样标志）
    try:
        with open(path, 'rb') as f:
            img_bytes = f.read()
    except (OSError, IOError):
        return None

    flags = cv2.IMREAD_COLOR
    if reduced == 2:
        flags = cv2.IMREAD_REDUCED_COLOR_2
    elif reduced == 4:
        flags = cv2.IMREAD_REDUCED_COLOR_4
    elif reduced == 8:
        flags = cv2.IMREAD_REDUCED_COLOR_8

    img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), flags)
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
        # v5.3.1: JPEG 缩略图用 DCT 降采样解码（1/8 或 1/4 尺寸），提速 4~8 倍
        reduced = None
        if Path(path).suffix.lower() in ('.jpg', '.jpeg'):
            reduced = 8 if size <= 96 else (4 if size <= 192 else 2)
        img = load_image(path, max_dim=size * 2, reduced=reduced)

    if img is None:
        return None
    h, w = img.shape[:2]
    if max(h, w) > size:
        scale = size / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
