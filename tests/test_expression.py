"""
表情检测单元测试 — MediaPipe Blendshapes (v5.0)。
用合成 blendshape categories 验证笑容/张嘴/僵硬判定与得分区分度。
"""

import sys
sys.path.insert(0, '.')

import pytest
from core.expression import check_expression_single, check_expression_multi


class _Cat:
    """模拟 MediaPipe Category（category_name + score）。"""

    def __init__(self, name: str, score: float):
        self.category_name = name
        self.score = score


def _make_categories(smile: float = 0.0, jaw: float = 0.0,
                     neutral: float = 0.0) -> list:
    """构造 52 项 blendshape 的简化列表（只含用到的项）。"""
    cats = []
    for name in ("mouthSmileLeft", "mouthSmileRight"):
        cats.append(_Cat(name, smile))
    cats.append(_Cat("jawOpen", jaw))
    cats.append(_Cat("_neutral", neutral))
    # 填充少量无关项，模拟真实列表
    cats.append(_Cat("eyeBlinkLeft", 0.0))
    cats.append(_Cat("browDownLeft", 0.0))
    return cats


class _Blendshapes:
    """模拟 MediaPipe Classifications（含 .categories）。"""

    def __init__(self, cats: list):
        self.categories = cats


def _face(cats: list) -> _Blendshapes:
    return _Blendshapes(cats)


class TestExpressionSingle:
    """单张人脸表情检测。"""

    def test_smiling_passes(self):
        """明显笑容应通过。"""
        cats = _make_categories(smile=0.5)
        ok, score, detail = check_expression_single(cats, smile_threshold=0.25)
        assert ok is True
        assert score >= 0.5
        assert detail["is_smiling"] is True

    def test_not_smiling_fails(self):
        """不笑应失败。"""
        cats = _make_categories(smile=0.05)
        ok, _, detail = check_expression_single(cats, smile_threshold=0.25)
        assert ok is False
        assert detail["is_smiling"] is False

    def test_smile_borderline(self):
        """笑容刚好达到阈值应通过。"""
        cats = _make_categories(smile=0.25)
        ok, score, _ = check_expression_single(cats, smile_threshold=0.25)
        assert ok is True
        assert score == pytest.approx(0.5, abs=0.01)

    def test_mouth_open_fails(self):
        """张嘴过大（说话/打哈欠）即使笑也应失败。"""
        cats = _make_categories(smile=0.6, jaw=0.8)
        ok, _, detail = check_expression_single(cats, smile_threshold=0.25)
        assert ok is False
        assert detail["is_mouth_open"] is True

    def test_slightly_open_mouth_ok(self):
        """轻微张嘴（<0.3）不影响通过。"""
        cats = _make_categories(smile=0.5, jaw=0.1)
        ok, _, detail = check_expression_single(cats, smile_threshold=0.25)
        assert ok is True
        assert detail["is_mouth_open"] is False

    def test_too_neutral_fails(self):
        """表情僵硬（中立度过高且不笑）应失败。"""
        cats = _make_categories(smile=0.05, neutral=0.95)
        ok, _, _ = check_expression_single(cats, smile_threshold=0.25)
        assert ok is False

    def test_score_discrimination(self):
        """得分应有区分度：笑得越多分越高（v5.1 修复：不再恒为高分）。"""
        _, s_small, _ = check_expression_single(
            _make_categories(smile=0.3), smile_threshold=0.25)
        _, s_big, _ = check_expression_single(
            _make_categories(smile=0.9), smile_threshold=0.25)
        assert s_small < s_big
        # 0.3 笑容得分应明显低于 0.9 笑容（旧实现两者都≈1.0）
        assert s_small < 0.9
        assert s_big >= 0.9

    def test_score_range(self):
        """得分在 0~1 之间。"""
        for smile in (0.0, 0.1, 0.4, 0.8):
            _, score, _ = check_expression_single(
                _make_categories(smile=smile), smile_threshold=0.25)
            assert 0.0 <= score <= 1.0

    def test_empty_categories(self):
        """空/无笑容项时不应崩溃。"""
        cats = [_Cat("eyeBlinkLeft", 0.1)]
        ok, score, detail = check_expression_single(cats, smile_threshold=0.25)
        assert ok is False
        assert 0.0 <= score <= 1.0
        assert detail["smile"] == 0.0


class TestExpressionMulti:
    """多人脸表情检测（best / all 模式）。"""

    def test_best_mode_picks_best_face(self):
        """best 模式：只要有一张脸合格即通过。"""
        faces = [
            _face(_make_categories(smile=0.05)),  # 不笑
            _face(_make_categories(smile=0.6)),   # 笑
        ]
        ok, score, detail, fail_count, total = check_expression_multi(
            faces, smile_threshold=0.25, face_mode="best")
        assert ok is True
        assert total == 2
        assert fail_count == 1
        assert "1人不笑" in detail

    def test_all_mode_requires_everyone(self):
        """all 模式：任一人不合格则整体失败。"""
        faces = [
            _face(_make_categories(smile=0.05)),
            _face(_make_categories(smile=0.6)),
        ]
        ok, _, detail, fail_count, total = check_expression_multi(
            faces, smile_threshold=0.25, face_mode="all")
        assert ok is False
        assert fail_count == 1

    def test_all_mode_all_good(self):
        """all 模式：全部合格则通过。"""
        faces = [
            _face(_make_categories(smile=0.5)),
            _face(_make_categories(smile=0.4)),
        ]
        ok, score, _, fail_count, total = check_expression_multi(
            faces, smile_threshold=0.25, face_mode="all")
        assert ok is True
        assert fail_count == 0

    def test_empty_list(self):
        """无人脸时不检测，默认通过。"""
        ok, score, detail, fail_count, total = check_expression_multi(
            [], smile_threshold=0.25, face_mode="best")
        assert ok is True
        assert score == 1.0
        assert total == 0

    def test_new_mediapipe_list_structure(self):
        """
        v5.2 修复：新版 MediaPipe (0.10.35+) 的 face_blendshapes 是
        List[List[Category]]——元素直接是 categories 列表，没有 .categories 属性。
        """
        faces = [
            _make_categories(smile=0.6),   # 直接传 categories 列表（新版结构）
            _make_categories(smile=0.05),
        ]
        ok, score, detail, fail_count, total = check_expression_multi(
            faces, smile_threshold=0.25, face_mode="best")
        assert ok is True
        assert total == 2
        assert fail_count == 1

    def test_mixed_structures(self):
        """新旧两种结构混用也能正常工作（v5.2 兼容）。"""
        faces = [
            _face(_make_categories(smile=0.5)),   # 旧版：Classifications 包装
            _make_categories(smile=0.5),          # 新版：直接 list
        ]
        ok, score, _, fail_count, total = check_expression_multi(
            faces, smile_threshold=0.25, face_mode="all")
        assert ok is True
        assert total == 2
        assert fail_count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
