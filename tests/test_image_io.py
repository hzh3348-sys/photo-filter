"""utils/image_io 测试 — JPEG 降采样解码与缩略图尺寸约束 (v5.3)。"""

import cv2
import numpy as np
import pytest

from utils.image_io import load_image, load_thumbnail


@pytest.fixture
def jpeg_file(tmp_path):
    img = np.full((1200, 1600, 3), 200, dtype=np.uint8)
    img[100:1100, 200:1400] = (60, 120, 180)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    assert ok
    p = tmp_path / "photo.jpg"
    p.write_bytes(buf.tobytes())
    return p


def test_load_thumbnail_jpeg_size(jpeg_file):
    """缩略图长边必须 ≤ 目标尺寸，且返回 RGB uint8。"""
    rgb = load_thumbnail(jpeg_file, size=96)
    assert rgb is not None
    assert rgb.dtype == np.uint8
    assert rgb.shape[2] == 3
    h, w = rgb.shape[:2]
    assert max(h, w) <= 96


def test_load_image_reduced_jpeg(jpeg_file):
    """IMREAD_REDUCED_COLOR_8 应显著缩小 JPEG 解码尺寸。"""
    img = load_image(jpeg_file, max_dim=2048, reduced=8)
    assert img is not None
    h, w = img.shape[:2]
    assert w < 800, f"1/8 降采样后宽度仍为 {w}"
    assert h < 600


def test_load_image_reduced_png(tmp_path):
    """OpenCV 对 PNG 同样支持降采样解码（不减慢、不报错）。"""
    img = np.full((400, 500, 3), 100, dtype=np.uint8)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    p = tmp_path / "photo.png"
    p.write_bytes(buf.tobytes())
    out = load_image(p, max_dim=2048, reduced=8)
    assert out is not None
    assert out.shape[2] == 3
    h, w = out.shape[:2]
    assert w < 300 and h < 300, f"PNG 1/8 降采样后尺寸仍为 {w}x{h}"