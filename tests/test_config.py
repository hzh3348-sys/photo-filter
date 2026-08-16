"""
配置工具单元测试 — _as_bool 安全布尔解析 (v5.1)。
QSettings 在 ini 下会把 bool 存成字符串，bool("false")==True 是经典陷阱。
"""

import sys
sys.path.insert(0, '.')

import pytest
from utils.config import _as_bool


class TestAsBool:
    """布尔解析鲁棒性。"""

    def test_real_bool(self):
        assert _as_bool(True) is True
        assert _as_bool(False) is False

    def test_int(self):
        assert _as_bool(1) is True
        assert _as_bool(0) is False

    def test_string_true_variants(self):
        for s in ("true", "True", "TRUE", "1", "yes", "on"):
            assert _as_bool(s) is True, s

    def test_string_false_variants(self):
        # 关键：bool("false") 是 True，必须正确解析为 False
        for s in ("false", "False", "FALSE", "0", "no", "off", ""):
            assert _as_bool(s) is False, s

    def test_whitespace(self):
        assert _as_bool(" true ") is True
        assert _as_bool(" false ") is False

    def test_none(self):
        assert _as_bool(None) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
