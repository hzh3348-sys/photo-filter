"""
曝光检测单元测试。
"""

import sys
sys.path.insert(0, '.')

import numpy as np
import cv2
import pytest
from core.exposure import check_exposure


def make_image(mean_brightness: int = 128, size: tuple = (100, 100)) -> np.ndarray:
    """创建指定平均亮度的 BGR 测试图片。"""
    img = np.full((*size, 3), mean_brightness, dtype=np.uint8)
    return img


def make_overexposed_image(ratio: float = 0.1, size: tuple = (100, 100)) -> np.ndarray:
    """创建包含过曝像素的图片。"""
    img = np.full((*size, 3), 128, dtype=np.uint8)
    over_pixels = int(size[0] * size[1] * ratio)
    img.reshape(-1, 3)[:over_pixels] = 255
    return img


def make_underexposed_image(ratio: float = 0.2, size: tuple = (100, 100)) -> np.ndarray:
    """创建包含欠曝像素的图片。"""
    img = np.full((*size, 3), 128, dtype=np.uint8)
    under_pixels = int(size[0] * size[1] * ratio)
    img.reshape(-1, 3)[:under_pixels] = 0
    return img


class TestExposure:
    """曝光检测测试套件。"""

    def test_normal_exposure_passes(self):
        """正常曝光的照片应通过检测。"""
        img = make_image(128)
        ok, score = check_exposure(img, over_th=0.05, under_th=0.15)
        assert ok is True
        assert score > 0.9

    def test_overexposed_fails(self):
        """过曝照片应被检测出来。"""
        img = make_overexposed_image(ratio=0.10)
        ok, score = check_exposure(img, over_th=0.05, under_th=0.15)
        assert ok is False
        assert score < 0.6

    def test_underexposed_fails(self):
        """欠曝照片应被检测出来。"""
        img = make_underexposed_image(ratio=0.20)
        ok, score = check_exposure(img, under_th=0.15, over_th=0.05)
        assert ok is False
        assert score < 0.6

    def test_borderline_over_threshold(self):
        """刚好超过阈值的过曝应失败。"""
        img = make_overexposed_image(ratio=0.051)
        ok, _ = check_exposure(img, over_th=0.05, under_th=0.15)
        assert ok is False

    def test_just_under_threshold_passes(self):
        """刚好在阈值内应通过。"""
        img = make_overexposed_image(ratio=0.049)
        ok, _ = check_exposure(img, over_th=0.05, under_th=0.15)
        assert ok is True

    def test_all_white_image(self):
        """全白图片应检测为过曝。"""
        img = np.full((100, 100, 3), 255, dtype=np.uint8)
        ok, score = check_exposure(img, over_th=0.05, under_th=0.15)
        assert ok is False
        assert score == 0.0

    def test_all_black_image(self):
        """全黑图片应检测为欠曝。"""
        img = np.full((100, 100, 3), 0, dtype=np.uint8)
        ok, score = check_exposure(img, over_th=0.05, under_th=0.15)
        assert ok is False
        assert score == 0.0

    def test_score_range(self):
        """得分应在 0~1 之间。"""
        img = make_image(128)
        _, score = check_exposure(img, over_th=0.05, under_th=0.15)
        assert 0 <= score <= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
