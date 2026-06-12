"""
重复照片检测 — dHash (差值哈希) + 汉明距离。
纯 NumPy + OpenCV 实现，无需额外依赖。
"""

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


def hamming_distance(hash1: str, hash2: str) -> int:
    """计算两个十六进制哈希字符串的汉明距离。"""
    if len(hash1) != len(hash2):
        raise ValueError("哈希长度不一致")

    dist = 0
    for c1, c2 in zip(hash1, hash2):
        # 将十六进制字符转为整数，异或后计算置位比特数
        xor = int(c1, 16) ^ int(c2, 16)
        dist += bin(xor).count('1')
    return dist


def find_duplicates(photo_paths, threshold: int = DEFAULT_DUPLICATE_HAMMING):
    """
    在照片列表中查找重复/相似照片。
    返回 dict: {path_index: duplicate_of_index}
    仅标记第二张及之后的重复照片。
    """
    from utils.image_io import load_image

    hashes = {}
    duplicates = {}

    for idx, path in enumerate(photo_paths):
        try:
            img = load_image(path, max_dim=512)  # 小图即可计算哈希
            if img is None:
                continue
            dh = compute_dhash(img, hash_size=8)
            del img

            # 与已计算的哈希比较
            is_dup = False
            for prev_idx, prev_hash in hashes.items():
                if hamming_distance(dh, prev_hash) <= threshold:
                    duplicates[idx] = prev_idx
                    is_dup = True
                    break

            if not is_dup:
                hashes[idx] = dh

        except Exception:
            continue

    return duplicates


def compute_all_hashes(photo_paths):
    """计算所有照片的 dHash，用于后处理。返回 dict: {path_index: hash_str}。"""
    from utils.image_io import load_image

    hashes = {}
    for idx, path in enumerate(photo_paths):
        try:
            img = load_image(path, max_dim=512)
            if img is None:
                continue
            hashes[idx] = compute_dhash(img, hash_size=8)
            del img
        except Exception:
            continue
    return hashes
