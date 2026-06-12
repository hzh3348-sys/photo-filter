"""
睁眼检测 — EAR 算法单元测试。
"""

import sys
sys.path.insert(0, '.')

import numpy as np
import pytest
from core.eyes import eye_aspect_ratio


def make_eye_points(openness: float = 1.0) -> np.ndarray:
    """
    创建模拟的眼睛关键点。
    openness=1.0 表示正常睁眼，0.0 表示完全闭合。
    返回 shape (8, 2) 的数组。
    """
    # 模拟 MediaPipe 眼睛关键点布局
    # 0──1──2──3──4  水平方向
    #    7     5
    #      6        垂直方向
    w = 40.0  # 眼宽
    h = 10.0 * openness  # 眼高（可调）

    pts = np.array([
        [0, 0],        # 0: 左眼角
        [10, -h],      # 1: 上眼睑左
        [20, -h * 0.5],# 2: 上眼睑中
        [30, -h],      # 3: 上眼睑右
        [40, 0],       # 4: 右眼角
        [30, h],       # 5: 下眼睑右
        [20, h * 0.5], # 6: 下眼睑中
        [10, h],       # 7: 下眼睑左
    ], dtype=np.float64)
    return pts


class TestEyeAspectRatio:
    """EAR 算法测试套件。"""

    def test_open_eye_high_ear(self):
        """睁眼时 EAR 值应该较高。"""
        pts = make_eye_points(openness=1.0)
        ear = eye_aspect_ratio(pts)
        assert ear > 0.15

    def test_closed_eye_low_ear(self):
        """闭眼时 EAR 值应该很低。"""
        pts = make_eye_points(openness=0.1)
        ear = eye_aspect_ratio(pts)
        assert ear < 0.15

    def test_ear_monotonic_with_openness(self):
        """EAR 值应随眼睛开合度单调递减。"""
        ears = []
        for openness in [1.0, 0.5, 0.2, 0.1]:
            pts = make_eye_points(openness)
            ears.append(eye_aspect_ratio(pts))
        # 应严格递减
        for i in range(len(ears) - 1):
            assert ears[i] > ears[i + 1]

    def test_fully_closed_near_zero(self):
        """完全闭合时 EAR 接近0。"""
        pts = make_eye_points(openness=0.01)
        ear = eye_aspect_ratio(pts)
        assert ear < 0.05

    def test_ear_non_negative(self):
        """EAR 值不应为负。"""
        pts = make_eye_points(openness=0.5)
        ear = eye_aspect_ratio(pts)
        assert ear >= 0.0

    def test_default_threshold_classification(self):
        """默认阈值 0.20 应正确分类睁眼和闭眼。"""
        open_pts = make_eye_points(openness=1.0)
        closed_pts = make_eye_points(openness=0.1)
        assert eye_aspect_ratio(open_pts) >= 0.20
        assert eye_aspect_ratio(closed_pts) < 0.20


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
