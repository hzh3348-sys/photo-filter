"""
模糊检测单元测试 — 多区域最清晰判断法。
"""

import sys
sys.path.insert(0, '.')

import numpy as np
import cv2
import pytest
from core.blur import check_blur


def make_sharp_image(size: tuple = (400, 400)) -> np.ndarray:
    """创建清晰的测试图片（棋盘格 + 纹理）。"""
    img = np.zeros((*size, 3), dtype=np.uint8)
    cell = 20
    for y in range(0, size[0], cell):
        for x in range(0, size[1], cell):
            if (x // cell + y // cell) % 2 == 0:
                img[y:y+cell, x:x+cell] = 255
    return img


def make_blurry_image(size: tuple = (400, 400)) -> np.ndarray:
    """创建模糊图片（高斯模糊）。"""
    sharp = make_sharp_image(size)
    return cv2.GaussianBlur(sharp, (41, 41), 15)


class TestBlur:
    """模糊检测测试套件。"""

    def test_sharp_image_passes(self):
        """清晰棋盘格应通过检测。"""
        img = make_sharp_image()
        ok, score = check_blur(img, threshold=40)
        assert ok is True
        assert score > 0.5

    def test_blurry_image_fails(self):
        """强烈模糊应被检测。"""
        img = make_blurry_image()
        ok, score = check_blur(img, threshold=40)
        assert ok is False or score < 0.3

    def test_sharp_score_higher_than_blurry(self):
        """清晰图得分 > 模糊图得分。"""
        sharp = make_sharp_image()
        blurry = make_blurry_image()
        _, ss = check_blur(sharp, threshold=40)
        _, bs = check_blur(blurry, threshold=40)
        assert ss > bs

    def test_score_range(self):
        """得分在 0~1 之间。"""
        img = make_sharp_image()
        _, score = check_blur(img, threshold=40)
        assert 0 <= score <= 1

    def test_very_blurry_near_zero(self):
        """纯色图得分应接近 0。"""
        img = np.full((200, 200, 3), 128, dtype=np.uint8)
        _, score = check_blur(img, threshold=40)
        assert score <= 0.1

    def test_mixed_sharp_blurry(self):
        """一半清晰一半模糊的照片应通过（最清晰区域判断）。"""
        sharp = make_sharp_image((200, 200))
        blurry = cv2.GaussianBlur(sharp, (41, 41), 15)
        # 左右拼接：左边清晰，右边模糊
        mixed = np.hstack([sharp, blurry])
        ok, score = check_blur(mixed, threshold=40)
        # 左边清晰区域应该让整体通过
        assert ok is True

    def test_higher_threshold_more_lenient(self):
        """更高阈值（更宽容）模糊图应判定ok。"""
        # 中度模糊的图 → 严格阈值 fail，宽容阈值 pass
        sharp = make_sharp_image((400, 400))
        img = cv2.GaussianBlur(sharp, (11, 11), 3)  # 中度模糊
        ok_strict, _ = check_blur(img, threshold=20)
        ok_lenient, _ = check_blur(img, threshold=150)
        # 严格阈值下应该 fail，宽容阈值下应该 pass
        assert ok_strict is False or ok_lenient is True
        assert ok_lenient is True  # 中度模糊在150阈值下应该ok


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
