"""
数据模型单元测试 — PhotoResult.all_pass / fail_reason / DetectionConfig 默认值。
"""

import sys
sys.path.insert(0, '.')

from pathlib import Path

import pytest
from core.models import PhotoResult, DetectionConfig
from utils.constants import (
    DEFAULT_OVEREXPOSURE_RATIO, DEFAULT_UNDEREXPOSURE_RATIO,
    DEFAULT_EAR_THRESHOLD, DEFAULT_BLUR_THRESHOLD,
)


def _photo(**kw) -> PhotoResult:
    base = dict(path=Path("test.jpg"), exposure_ok=True,
                eyes_open=True, skin_ok=True, face_detected=True)
    base.update(kw)
    return PhotoResult(**base)


class TestAllPass:
    """综合通过判定。"""

    def test_all_good_passes(self):
        assert _photo().all_pass is True

    def test_exposure_fail(self):
        assert _photo(exposure_ok=False).all_pass is False

    def test_eyes_closed_fail(self):
        assert _photo(eyes_open=False).all_pass is False

    def test_skin_fail(self):
        assert _photo(skin_ok=False).all_pass is False

    def test_duplicate_fail(self):
        assert _photo(is_duplicate_of=Path("orig.jpg")).all_pass is False

    def test_error_fail(self):
        assert _photo(error="曝光检测异常: x").all_pass is False

    def test_note_not_fail(self):
        """note（未检测到人脸等提示）不影响通过判定。"""
        p = _photo(face_detected=False, note="未检测到人脸",
                   eyes_open=False, skin_ok=False)  # 无人脸时睁眼/肤色不参与
        assert p.all_pass is True

    def test_no_face_only_exposure(self):
        """无人脸照片只按曝光+可选检测判定。"""
        assert _photo(face_detected=False).all_pass is True
        assert _photo(face_detected=False, exposure_ok=False).all_pass is False

    def test_optional_checks_respected(self):
        p = _photo(clarity_enabled=True, clarity_ok=False)
        assert p.all_pass is False
        p2 = _photo(clarity_enabled=False, clarity_ok=False)
        assert p2.all_pass is True

    def test_expression_red_eye_respected(self):
        assert _photo(expression_enabled=True, expression_ok=False).all_pass is False
        assert _photo(red_eye_enabled=True, red_eye_ok=False).all_pass is False
        assert _photo(expression_enabled=False, expression_ok=False).all_pass is True


class TestFailReason:
    """失败原因展示。"""

    def test_reason_exposure(self):
        assert "曝光异常" in _photo(exposure_ok=False).fail_reason

    def test_reason_eyes(self):
        assert "闭眼" in _photo(eyes_open=False).fail_reason

    def test_reason_duplicate(self):
        r = _photo(is_duplicate_of=Path("a.jpg")).fail_reason
        assert "重复" in r and "a.jpg" in r

    def test_note_not_shown_as_reason(self):
        """v5.1 修复：note 不应作为失败原因显示。"""
        p = _photo(face_detected=False, note="未检测到人脸")
        assert "未检测到人脸" not in p.fail_reason
        assert p.all_pass is True

    def test_pass_shows_pass(self):
        assert _photo().fail_reason == "通过"

    def test_no_face_pass_note(self):
        """无人脸且无其他问题：显示说明性提示而不是空。"""
        r = _photo(face_detected=False).fail_reason
        assert "无人脸" in r

    def test_error_only_reason(self):
        """v5.2 修复：检测异常时只显示错误，不再叠加"曝光异常"等默认字段。"""
        p = _photo(error="异常: xxx", exposure_ok=False, eyes_open=False)
        assert p.fail_reason == "异常: xxx"
        assert "曝光异常" not in p.fail_reason
        assert "闭眼" not in p.fail_reason


class TestDetectionConfigDefaults:
    """DetectionConfig 默认值应与 constants 单一数据源一致（v5.1 修复）。"""

    def test_exposure_defaults_match_v5(self):
        """v5.0 哲学：默认只拦极端曝光（50%），不是旧的 5%/15%。"""
        cfg = DetectionConfig()
        assert cfg.over_threshold == DEFAULT_OVEREXPOSURE_RATIO == 0.50
        assert cfg.under_threshold == DEFAULT_UNDEREXPOSURE_RATIO == 0.50

    def test_other_defaults_match_constants(self):
        cfg = DetectionConfig()
        assert cfg.ear_threshold == DEFAULT_EAR_THRESHOLD == 0.20
        assert cfg.blur_threshold == DEFAULT_BLUR_THRESHOLD == 40.0
        assert cfg.face_mode == "best"

    def test_defaults_construct_ok(self):
        cfg = DetectionConfig()
        assert cfg.duplicate_hamming >= 0
        assert 0.0 <= cfg.clarity_threshold <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
