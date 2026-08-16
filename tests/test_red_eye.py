"""
红眼检测单元测试 — 瞳孔聚焦 ROI + 连通域噪点过滤 (v5.1)。
用合成眼部图像 + 模拟 MediaPipe 关键点验证判定。
"""

import sys
sys.path.insert(0, '.')

import numpy as np
import cv2
import pytest
from core.red_eye import check_red_eye_single, check_red_eye_multi
from utils.constants import LEFT_EYE_IDX, RIGHT_EYE_IDX, LEFT_IRIS_CENTER_IDX, RIGHT_IRIS_CENTER_IDX


class _LM:
    """模拟 MediaPipe NormalizedLandmark（x/y 归一化坐标）。"""

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y


def _make_landmarks(img_w: int, img_h: int,
                    left_eye=(70, 100), right_eye=(130, 100),
                    eye_rw=12, eye_rh=6) -> list:
    """
    构造 480 个关键点：左右眼 8 个关键点按椭圆分布，虹膜中心在眼睛中心。
    """
    lms = [_LM(0.5, 0.5)] * 480  # 默认点（有效坐标）

    def place(indices, cx, cy):
        for i, idx in enumerate(indices):
            ang = 2 * np.pi * i / len(indices)
            x = (cx + eye_rw * np.cos(ang)) / img_w
            y = (cy + eye_rh * np.sin(ang)) / img_h
            lms[idx] = _LM(x, y)

    place(LEFT_EYE_IDX, *left_eye)
    place(RIGHT_EYE_IDX, *right_eye)
    lms[LEFT_IRIS_CENTER_IDX] = _LM(left_eye[0] / img_w, left_eye[1] / img_h)
    lms[RIGHT_IRIS_CENTER_IDX] = _LM(right_eye[0] / img_w, right_eye[1] / img_h)
    return lms


def _make_eye_image(size=(200, 200), pupil_color=(0, 0, 0), pupil_radius=4,
                    eye_centers=((70, 100), (130, 100))) -> np.ndarray:
    """背景肤色 + 黑色/红色瞳孔的眼睛图像。"""
    img = np.full((*size, 3), (180, 150, 130), dtype=np.uint8)  # 肤色背景 BGR
    for cx, cy in eye_centers:
        cv2.circle(img, (cx, cy), pupil_radius, pupil_color, -1)
    return img


class TestRedEyeSingle:
    """单张人脸红眼检测。"""

    def test_normal_eye_passes(self):
        """正常（黑色瞳孔）眼睛应通过。"""
        img = _make_eye_image(pupil_color=(10, 10, 10))
        lms = _make_landmarks(*img.shape[:2])
        ok, score = check_red_eye_single(img, lms, threshold=0.08)
        assert ok is True
        assert score >= 0.9

    def test_red_eye_fails(self):
        """闪光灯红眼（红色瞳孔）应被检测。"""
        img = _make_eye_image(pupil_color=(0, 0, 255))  # BGR 纯红 → HSV H=0
        lms = _make_landmarks(*img.shape[:2])
        ok, score = check_red_eye_single(img, lms, threshold=0.08)
        assert ok is False
        assert score < 0.5

    def test_orange_red_fails(self):
        """偏橙红色（H≈9°）瞳孔也应被检测。"""
        img = _make_eye_image(pupil_color=(0, 40, 255))  # 红偏橙，H≈9°
        lms = _make_landmarks(*img.shape[:2])
        ok, _ = check_red_eye_single(img, lms, threshold=0.08)
        assert ok is False

    def test_red_eyelid_no_false_positive(self):
        """
        红眼皮/红眼影不误报：红色像素在瞳孔 ROI 之外（眼睑边缘）。
        v5.1: 瞳孔聚焦 ROI 只统计虹膜中心附近，眼睑红色不计入。
        """
        img = np.full((200, 200, 3), (180, 150, 130), dtype=np.uint8)
        # 在眼睛上方（眼睑位置）画红色条带，远离虹膜中心
        cv2.rectangle(img, (58, 86), (82, 94), (0, 0, 255), -1)
        lms = _make_landmarks(*img.shape[:2])
        ok, _ = check_red_eye_single(img, lms, threshold=0.08)
        assert ok is True

    def test_isolated_noise_pixels_filtered(self):
        """
        零散红色噪点被连通域过滤：单像素红点（不成斑块）不计入。
        """
        img = np.full((200, 200, 3), (180, 150, 130), dtype=np.uint8)
        rng = np.random.RandomState(1)
        # 在瞳孔 ROI 内撒 15 个互不相邻的单像素红点
        for _ in range(15):
            x = 70 + int(rng.randint(-6, 7))
            y = 100 + int(rng.randint(-4, 5))
            img[y, x] = (0, 0, 255)
        lms = _make_landmarks(*img.shape[:2])
        ok, _ = check_red_eye_single(img, lms, threshold=0.08)
        assert ok is True  # 噪点被连通域过滤，不应判红眼

    def test_threshold_sensitivity(self):
        """阈值越小越严格：小面积红眼在高阈值下通过、低阈值下失败。"""
        img = _make_eye_image(pupil_color=(0, 0, 255), pupil_radius=3)
        lms = _make_landmarks(*img.shape[:2])
        ok_low, _ = check_red_eye_single(img, lms, threshold=0.03)
        ok_high, _ = check_red_eye_single(img, lms, threshold=0.30)
        assert ok_low is False
        assert ok_high is True


class TestRedEyeMulti:
    """多人脸红眼检测。"""

    def test_best_mode_any_red_eye_fails(self):
        """
        best 模式：红眼是闪光灯问题，任一明显人脸有红眼即整张照片不合格。
        """
        img = _make_eye_image()
        lms = _make_landmarks(*img.shape[:2])
        # 给右眼画红色瞳孔
        cv2.circle(img, (130, 100), 4, (0, 0, 255), -1)
        ok, _, count = check_red_eye_multi(img, [lms], threshold=0.08, face_mode="best")
        assert ok is False
        assert count >= 1

    def test_no_red_eye_all_pass(self):
        """无红眼时 all/best 模式都通过。"""
        img = _make_eye_image()
        lms = _make_landmarks(*img.shape[:2])
        ok, score, count = check_red_eye_multi(img, [lms], threshold=0.08, face_mode="all")
        assert ok is True
        assert score == 1.0
        assert count == 0

    def test_empty_list(self):
        """无人脸时默认通过。"""
        img = np.full((200, 200, 3), 128, dtype=np.uint8)
        ok, score, count = check_red_eye_multi(img, None, threshold=0.08, face_mode="best")
        assert ok is True
        assert score == 1.0
        assert count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
