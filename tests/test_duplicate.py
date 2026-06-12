"""
重复检测单元测试 — dHash 和汉明距离。
"""

import sys
sys.path.insert(0, '.')

import numpy as np
import cv2
import pytest
from core.duplicate import compute_dhash, hamming_distance


def make_test_image(seed: int = 0, size: tuple = (64, 64)) -> np.ndarray:
    """创建确定性的测试图片。"""
    rng = np.random.RandomState(seed)
    return rng.randint(0, 255, (*size, 3), dtype=np.uint8)


class TestDHash:
    """dHash 算法测试套件。"""

    def test_hash_is_16_chars(self):
        """dHash 应返回 16 个十六进制字符。"""
        img = make_test_image(42)
        h = compute_dhash(img)
        assert len(h) == 16
        assert all(c in '0123456789abcdef' for c in h)

    def test_same_image_same_hash(self):
        """相同图片应产生相同哈希。"""
        img = make_test_image(42)
        h1 = compute_dhash(img)
        h2 = compute_dhash(img)
        assert h1 == h2

    def test_similar_images_small_distance(self):
        """相似图片的汉明距离应该很小。"""
        img1 = make_test_image(42)
        img2 = img1.copy().astype(np.int32)
        # 仅修改少量像素
        img2[0, 0] = (img2[0, 0] + 128) % 256
        img2 = img2.astype(np.uint8)
        h1 = compute_dhash(img1)
        h2 = compute_dhash(img2)
        dist = hamming_distance(h1, h2)
        # 微小变化应该距离很小
        assert dist < 10

    def test_very_different_images_large_distance(self):
        """完全不同的图片应有较大的汉明距离。"""
        img1 = make_test_image(0)
        img2 = make_test_image(99)
        h1 = compute_dhash(img1)
        h2 = compute_dhash(img2)
        dist = hamming_distance(h1, h2)
        assert dist > 10

    def test_hamming_self_zero(self):
        """相同哈希的汉明距离应为0。"""
        img = make_test_image(42)
        h = compute_dhash(img)
        assert hamming_distance(h, h) == 0

    def test_hamming_max_value(self):
        """汉明距离最大值不超过64（8×8位）。"""
        img1 = make_test_image(0)
        img2 = make_test_image(99)
        h1 = compute_dhash(img1)
        h2 = compute_dhash(img2)
        dist = hamming_distance(h1, h2)
        assert 0 <= dist <= 64

    def test_flipped_image(self):
        """翻转图片应产生不同的哈希。"""
        img = make_test_image(42)
        flipped = cv2.flip(img, 1)  # 水平翻转
        h1 = compute_dhash(img)
        h2 = compute_dhash(flipped)
        assert h1 != h2

    def test_grayscale_input(self):
        """灰度图输入也应正常工作。"""
        img = make_test_image(42)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h = compute_dhash(gray)
        assert len(h) == 16


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
