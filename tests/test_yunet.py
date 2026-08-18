"""core/yunet 测试 — 纯函数与降级逻辑（无需模型文件）。"""

from types import SimpleNamespace

import numpy as np
import pytest

from core import yunet


def _lm(x, y):
    return SimpleNamespace(x=x, y=y, z=0.0)


def test_bbox_from_landmarks():
    lms = [_lm(0.1, 0.2), _lm(0.9, 0.8)]
    x, y, w, h = yunet.bbox_from_landmarks(lms, (100, 200))
    assert (x, y, w, h) == (20, 20, 160, 60)


def test_iou():
    assert yunet.iou((0, 0, 10, 10), (0, 0, 10, 10)) == pytest.approx(1.0)
    assert yunet.iou((0, 0, 10, 10), (100, 100, 10, 10)) == 0.0
    assert yunet.iou((0, 0, 10, 10), (5, 5, 10, 10)) == pytest.approx(25 / 175)


def test_merge_boxes_filters_overlap():
    existing = [(0, 0, 100, 100)]
    cand = [
        {"bbox": (10, 10, 80, 80), "score": 0.9, "landmarks": None},   # IoU≈0.43 → 过滤
        {"bbox": (300, 300, 50, 50), "score": 0.8, "landmarks": None}, # 无重叠 → 保留
    ]
    kept = yunet.merge_boxes(existing, cand, iou_threshold=0.3)
    assert len(kept) == 1
    assert kept[0]["bbox"] == (300, 300, 50, 50)


def test_map_crop_to_orig():
    lms = [_lm(0.0, 0.0), _lm(0.5, 0.5), _lm(1.0, 1.0)]
    mapped = yunet.map_crop_to_orig(lms, (100, 50, 200, 100), (400, 800))
    assert mapped[0].x == pytest.approx(100 / 800)
    assert mapped[0].y == pytest.approx(50 / 400)
    assert mapped[2].x == pytest.approx(300 / 800)
    assert mapped[2].y == pytest.approx(150 / 400)
    # 越界夹取
    assert mapped[0].x >= 0 and mapped[2].x <= 1


def test_expand_bbox_clamps():
    x, y, w, h = yunet.expand_bbox((5, 5, 10, 10), (30, 30), margin=0.5)
    assert x == 0 and y == 0
    assert x + w <= 30 and y + h <= 30


def test_detect_returns_empty_when_model_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(yunet, "MODEL_PATH", tmp_path / "missing.onnx")
    mgr = yunet.YuNetManager()
    assert mgr.available is False
    assert yunet.detect_faces_yunet(np.zeros((100, 100, 3), np.uint8), mgr) == []


def test_detect_returns_empty_for_none_manager():
    assert yunet.detect_faces_yunet(np.zeros((100, 100, 3), np.uint8), None) == []
