"""
构图水平检测单元测试 — 地平线检测法（v3.0+）。
用合成水平/倾斜线条图像验证判定。
"""

import sys
sys.path.insert(0, '.')

import numpy as np
import cv2
import pytest
from core.level import check_level, check_level_horizon


def _make_line_image(size=(400, 400), x1=0, y1=100, x2=399, y2=100,
                     bg=200, line=0, thickness=3) -> np.ndarray:
    """背景灰 + 一条线段。"""
    img = np.full((*size, 3), bg, dtype=np.uint8)
    cv2.line(img, (x1, y1), (x2, y2), line, thickness)
    return img


class TestLevelHorizon:
    """地平线检测法。"""

    def test_level_horizon_passes(self):
        """水平地平线（0°）应通过。"""
        img = _make_line_image()  # 0° 线
        ok, score = check_level_horizon(img, angle_tolerance=5.0)
        assert ok is True
        assert score == 1.0

    def test_tilted_horizon_fails(self):
        """明显倾斜的地平线（~7°）应判定倾斜。"""
        img = _make_line_image(x1=0, y1=80, x2=399, y2=130)  # atan2(50,399)≈7.1°
        ok, score = check_level_horizon(img, angle_tolerance=5.0)
        assert ok is False
        assert score < 1.0

    def test_single_horizon_line_detected(self):
        """
        单条贯穿画面的地平线也应触发检测（v5.1 修复：不再要求≥3条线成簇）。
        海平面照片就是单条长地平线。
        """
        img = _make_line_image(x1=0, y1=80, x2=399, y2=130)
        ok, _ = check_level_horizon(img, angle_tolerance=5.0)
        assert ok is False  # 单条倾斜长线也要拦

    def test_no_lines_passes(self):
        """无水平线的纯色图应通过（无法判断）。"""
        img = np.full((400, 400, 3), 128, dtype=np.uint8)
        ok, score = check_level_horizon(img, angle_tolerance=5.0)
        assert ok is True
        assert score == 1.0

    def test_tolerance_controls_strictness(self):
        """宽容度越大越容易通过。"""
        img = _make_line_image(x1=0, y1=80, x2=399, y2=130)  # ~7.1°
        ok_strict, _ = check_level_horizon(img, angle_tolerance=4.0)
        ok_lenient, _ = check_level_horizon(img, angle_tolerance=10.0)
        assert ok_strict is False
        assert ok_lenient is True

    def test_vertical_line_ignored(self):
        """竖直线（门框/灯柱）不应参与地平线判定。"""
        img = _make_line_image(x1=200, y1=0, x2=200, y2=399)  # 90° 竖线
        ok, _ = check_level_horizon(img, angle_tolerance=5.0)
        assert ok is True  # 竖线被过滤，无地平线 → 通过


class TestLevelEntry:
    """统一入口。"""

    def test_horizon_method_default(self):
        img = _make_line_image(x1=0, y1=80, x2=399, y2=130)
        ok, _ = check_level(img, method="horizon", angle_tolerance=5.0)
        assert ok is False

    def test_general_method_returns_tuple(self):
        img = _make_line_image()
        ok, score = check_level(img, method="general", angle_tolerance=9.0)
        assert isinstance(ok, bool)
        assert 0.0 <= score <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
