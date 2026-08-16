"""
肤色检测单元测试 — 凸包区域采样 + LAB (v5.0)。
用合成人脸关键点（椭圆分布）+ 不同底色验证判定。
"""

import sys
sys.path.insert(0, '.')

import numpy as np
import cv2
import pytest
from core.skin_tone import check_skin_tone, _build_face_region_mask


class _LM:
    """模拟 MediaPipe NormalizedLandmark。"""

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y


def _make_face_landmarks(img_h: int, img_w: int,
                         cx: float = 0.5, cy: float = 0.5,
                         rx: float = 0.3, ry: float = 0.4,
                         n: int = 468) -> list:
    """在椭圆上均匀分布 n 个关键点，模拟人脸轮廓。"""
    lms = []
    for i in range(n):
        ang = 2 * np.pi * i / n
        x = cx + rx * np.cos(ang)
        y = cy + ry * np.sin(ang)
        lms.append(_LM(x, y))
    return lms


def _make_face_image(size=(200, 200), color=(180, 150, 130)) -> np.ndarray:
    """纯色背景 + 关键点，构建人脸区域图像。"""
    img = np.full((*size, 3), color, dtype=np.uint8)
    return img


# 自然肤色 BGR（B<G<R，暖色）—— 经 L*a*b* 验证在放宽范围内
SKIN_COLOR = (115, 140, 180)
# 极端蓝色（应被拒绝）
BLUE_COLOR = (255, 0, 0)
# 极端绿色
GREEN_COLOR = (0, 255, 0)


class TestSkinTone:
    """肤色检测测试套件。"""

    def test_natural_skin_passes(self):
        """自然肤色应通过。"""
        img = _make_face_image(color=SKIN_COLOR)
        lms = _make_face_landmarks(*img.shape[:2])
        ok, score = check_skin_tone(img, lms)
        assert ok is True
        assert score > 0.5

    def test_blue_cast_fails(self):
        """极端蓝色色偏（非肤色）应被拒绝。"""
        img = _make_face_image(color=BLUE_COLOR)
        lms = _make_face_landmarks(*img.shape[:2])
        ok, _ = check_skin_tone(img, lms)
        assert ok is False

    def test_green_cast_fails(self):
        """极端绿色色偏应被拒绝。"""
        img = _make_face_image(color=GREEN_COLOR)
        lms = _make_face_landmarks(*img.shape[:2])
        ok, _ = check_skin_tone(img, lms)
        assert ok is False

    def test_dark_skin_passes(self):
        """深色皮肤（v3.0 起大幅放宽）应通过，不再误判。"""
        img = _make_face_image(color=(45, 60, 90))  # 深肤色 BGR(B<G<R)
        lms = _make_face_landmarks(*img.shape[:2])
        ok, _ = check_skin_tone(img, lms)
        assert ok is True

    def test_light_skin_passes(self):
        """浅肤色应通过。"""
        img = _make_face_image(color=(195, 205, 235))  # 浅肤色 BGR(B<G<R)
        lms = _make_face_landmarks(*img.shape[:2])
        ok, _ = check_skin_tone(img, lms)
        assert ok is True

    def test_precomputed_lab_reused(self):
        """传入预计算 LAB 与内部转换结果一致（性能优化正确性）。"""
        img = _make_face_image(color=SKIN_COLOR)
        lms = _make_face_landmarks(*img.shape[:2])
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        ok1, s1 = check_skin_tone(img, lms)
        ok2, s2 = check_skin_tone(img, lms, lab=lab)
        assert ok1 == ok2
        assert s1 == pytest.approx(s2, abs=1e-6)

    def test_insufficient_landmarks_returns_fail(self):
        """关键点不足（<30）时返回不合格而非崩溃。"""
        img = _make_face_image()
        lms = [_LM(0.5, 0.5) for _ in range(10)]
        ok, score = check_skin_tone(img, lms)
        assert ok is False
        assert score == 0.0

    def test_mask_building(self):
        """凸包 mask 应覆盖主要面部区域。"""
        img = np.zeros((200, 200, 3), dtype=np.uint8)
        lms = _make_face_landmarks(200, 200)
        mask = _build_face_region_mask(lms, (200, 200))
        assert mask is not None
        assert cv2.countNonZero(mask) > 5000  # 椭圆面积 ≈ π*60*80 ≈ 15000，腐蚀后仍很大


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
