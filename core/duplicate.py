"""
重复照片检测 — dHash (差值哈希) + 汉明距离。
纯 NumPy + OpenCV 实现，无需额外依赖。

v5.1 性能优化：
- 并行读图：用 ThreadPoolExecutor 并行加载/解码图片（I/O 与解码是主要瓶颈）
- 整数汉明距离：哈希转为 64 位整数后用 (a ^ b).bit_count()，
  比逐字符解析十六进制字符串快一个数量级
"""

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional

import cv2
import numpy as np

from utils.constants import DEFAULT_DUPLICATE_HAMMING


def compute_dhash(img: np.ndarray, hash_size: int = 8) -> str:
    """
    计算图片的 dHash (差值哈希)。
    hash_size=8 生成 64-bit 哈希（16 十六进制字符）。
    """
    # 缩放到 hash_size+1 × hash_size
    resized = cv2.resize(img, (hash_size + 1, hash_size))
    # 转灰度
    if len(resized.shape) == 3:
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    else:
        gray = resized

    # 逐行差值：相邻像素比较
    diff = gray[:, 1:] > gray[:, :-1]

    # 转为十六进制字符串
    hash_bytes = diff.flatten()
    # 每 4 位编码为一个十六进制字符
    hash_str = ''.join(
        format(int(''.join(str(int(b)) for b in hash_bytes[i:i+4]), 2), 'x')
        for i in range(0, len(hash_bytes), 4)
    )
    return hash_str


def _hash_to_int(hash_str: str) -> int:
    """十六进制哈希字符串 → 64 位整数。"""
    return int(hash_str, 16)


def _hamming_int(a: int, b: int) -> int:
    """两个 64 位整数的汉明距离（bit_count 极快）。"""
    return (a ^ b).bit_count()


def hamming_distance(hash1: str, hash2: str) -> int:
    """计算两个十六进制哈希字符串的汉明距离。"""
    if len(hash1) != len(hash2):
        raise ValueError("哈希长度不一致")
    return _hamming_int(_hash_to_int(hash1), _hash_to_int(hash2))


def _default_workers() -> int:
    """默认并行度：最多 8 线程。"""
    return min(8, os.cpu_count() or 4)


def _compute_one(path_idx):
    """单个文件的哈希计算（供线程池调用）。返回 (idx, hash_str or None)。"""
    from utils.image_io import load_image

    idx, path = path_idx
    try:
        img = load_image(path, max_dim=512)  # 小图即可计算哈希
        if img is None:
            return idx, None
        h = compute_dhash(img, hash_size=8)
        del img
        return idx, h
    except Exception:
        return idx, None


def find_duplicates(photo_paths, threshold: int = DEFAULT_DUPLICATE_HAMMING,
                    max_workers: Optional[int] = None) -> Dict[int, int]:
    """
    在照片列表中查找重复/相似照片（并行读图 + 整数汉明距离）。
    返回 dict: {path_index: duplicate_of_index}
    仅标记第二张及之后的重复照片（保留每组第一张）。
    """
    workers = max_workers or _default_workers()
    n = len(photo_paths)
    if n <= 1:
        return {}

    # ── 阶段1：并行计算所有哈希 ──
    hashes: Dict[int, int] = {}      # idx -> 64位整数哈希（仅保留非重复代表）
    duplicates: Dict[int, int] = {}

    if workers > 1 and n > 4:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(_compute_one, enumerate(photo_paths)))
    else:
        results = [_compute_one(p) for p in enumerate(photo_paths)]

    # ── 阶段2：顺序比较（保持"保留每组第一张"的语义）──
    for idx, h_str in results:
        if h_str is None:
            continue
        h_int = _hash_to_int(h_str)

        is_dup = False
        for prev_idx, prev_int in hashes.items():
            if _hamming_int(h_int, prev_int) <= threshold:
                duplicates[idx] = prev_idx
                is_dup = True
                break

        if not is_dup:
            hashes[idx] = h_int

    return duplicates


def compute_all_hashes(photo_paths, max_workers: Optional[int] = None) -> Dict[int, str]:
    """计算所有照片的 dHash（并行），用于后处理。返回 dict: {path_index: hash_str}。"""
    workers = max_workers or _default_workers()
    n = len(photo_paths)
    if n == 0:
        return {}

    if workers > 1 and n > 4:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(_compute_one, enumerate(photo_paths)))
    else:
        results = [_compute_one(p) for p in enumerate(photo_paths)]

    return {idx: h for idx, h in results if h is not None}
