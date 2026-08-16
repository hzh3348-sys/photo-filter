"""
重复检测单元测试 — dHash 和汉明距离。
v5.1: 新增 find_duplicates / compute_all_hashes 并行路径测试。
"""

import sys
sys.path.insert(0, '.')

import os
import shutil
import tempfile
import uuid

import numpy as np
import cv2
import pytest
from pathlib import Path
from core.duplicate import compute_dhash, hamming_distance, find_duplicates, compute_all_hashes


def make_test_image(seed: int = 0, size: tuple = (64, 64)) -> np.ndarray:
    """创建确定性的测试图片。"""
    rng = np.random.RandomState(seed)
    return rng.randint(0, 255, (*size, 3), dtype=np.uint8)


@pytest.fixture
def workdir():
    """
    自管理临时目录，不依赖 pytest tmp_path（其 \\\\?\\ 长路径清理在部分受限
    沙箱下会失败）。
    注意：用 Path.mkdir 建目录（默认权限），不用 tempfile.mkdtemp——
    后者创建 0o700 目录，在部分受限环境下不可写入。
    """
    def _make(root: Path) -> Path:
        d = root / f"pf_dup_{uuid.uuid4().hex[:8]}"
        d.mkdir(parents=True, exist_ok=True)
        probe = d / ".probe"
        probe.write_text("ok")
        probe.unlink()
        return d

    d = None
    try:
        d = _make(Path(tempfile.gettempdir()))
    except OSError:
        base = Path(__file__).resolve().parent.parent / ".test_tmp"
        d = _make(base)
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


class TestDHash:
    """dHash 算法测试套件。"""

    def test_hash_is_16_chars(self):
        """dHash 应返回 16 个十六进制字符。"""
        img = make_test_image(42)
        h = compute_dhash(img)
        assert len(h) == 16
        assert all(c in '0123456789abcdef' for c in h)

    def test_same_image_same_hash(self):
        """相同图片应产生相同哈希。"""
        img = make_test_image(42)
        h1 = compute_dhash(img)
        h2 = compute_dhash(img)
        assert h1 == h2

    def test_similar_images_small_distance(self):
        """相似图片的汉明距离应该很小。"""
        img1 = make_test_image(42)
        img2 = img1.copy().astype(np.int32)
        # 仅修改少量像素
        img2[0, 0] = (img2[0, 0] + 128) % 256
        img2 = img2.astype(np.uint8)
        h1 = compute_dhash(img1)
        h2 = compute_dhash(img2)
        dist = hamming_distance(h1, h2)
        # 微小变化应该距离很小
        assert dist < 10

    def test_very_different_images_large_distance(self):
        """完全不同的图片应有较大的汉明距离。"""
        img1 = make_test_image(0)
        img2 = make_test_image(99)
        h1 = compute_dhash(img1)
        h2 = compute_dhash(img2)
        dist = hamming_distance(h1, h2)
        assert dist > 10

    def test_hamming_self_zero(self):
        """相同哈希的汉明距离应为0。"""
        img = make_test_image(42)
        h = compute_dhash(img)
        assert hamming_distance(h, h) == 0

    def test_hamming_max_value(self):
        """汉明距离最大值不超过64（8×8位）。"""
        img1 = make_test_image(0)
        img2 = make_test_image(99)
        h1 = compute_dhash(img1)
        h2 = compute_dhash(img2)
        dist = hamming_distance(h1, h2)
        assert 0 <= dist <= 64

    def test_flipped_image(self):
        """翻转图片应产生不同的哈希。"""
        img = make_test_image(42)
        flipped = cv2.flip(img, 1)  # 水平翻转
        h1 = compute_dhash(img)
        h2 = compute_dhash(flipped)
        assert h1 != h2

    def test_grayscale_input(self):
        """灰度图输入也应正常工作。"""
        img = make_test_image(42)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h = compute_dhash(gray)
        assert len(h) == 16


class TestFindDuplicates:
    """find_duplicates 并行检测（v5.1 性能优化路径）。"""

    def _write(self, workdir: Path, name: str, seed: int) -> Path:
        p = workdir / name
        # 用 imencode + write_bytes（cv2.imwrite 在部分受限环境/中文路径下会静默失败）
        ok, buf = cv2.imencode('.jpg', make_test_image(seed))
        assert ok
        p.write_bytes(buf.tobytes())
        return p

    def test_no_duplicates(self, workdir):
        a = self._write(workdir, "a.jpg", 1)
        b = self._write(workdir, "b.jpg", 2)
        c = self._write(workdir, "c.jpg", 3)
        dups = find_duplicates([a, b, c], threshold=5)
        assert dups == {}

    def test_exact_duplicate_detected(self, workdir):
        a = self._write(workdir, "a.jpg", 42)
        b = self._write(workdir, "b.jpg", 42)  # 相同图片
        dups = find_duplicates([a, b], threshold=5)
        assert 1 in dups and dups[1] == 0  # 第二张标记为重复

    def test_keeps_first_of_group(self, workdir):
        """每组保留第一张：第三张重复照片指向组内第一张代表。"""
        a = self._write(workdir, "a.jpg", 42)
        b = self._write(workdir, "b.jpg", 42)
        c = self._write(workdir, "c.jpg", 42)
        dups = find_duplicates([a, b, c], threshold=5)
        assert dups == {1: 0, 2: 0}

    def test_parallel_path_matches_sequential(self, workdir):
        """并行路径（>4 文件）结果应与串行一致。"""
        paths = [self._write(workdir, f"p{i}.jpg", i) for i in range(8)]
        # 前两张用相同图片制造一组重复
        paths[3] = self._write(workdir, "p3_dup.jpg", 1)
        dups = find_duplicates(paths, threshold=5)
        assert 3 in dups and dups[3] == 1

    def test_missing_file_skipped(self, workdir):
        a = self._write(workdir, "a.jpg", 1)
        missing = workdir / "missing.jpg"
        dups = find_duplicates([a, missing], threshold=5)
        assert dups == {}

    def test_compute_all_hashes(self, workdir):
        a = self._write(workdir, "a.jpg", 1)
        b = self._write(workdir, "b.jpg", 2)
        hashes = compute_all_hashes([a, b])
        assert set(hashes.keys()) == {0, 1}
        assert all(len(h) == 16 for h in hashes.values())

    def test_hamming_int_equivalence(self):
        """字符串汉明距离与整数 bit_count 结果一致（重写正确性）。"""
        img1 = make_test_image(0)
        img2 = make_test_image(99)
        h1 = compute_dhash(img1)
        h2 = compute_dhash(img2)
        from core.duplicate import _hash_to_int, _hamming_int
        assert hamming_distance(h1, h2) == _hamming_int(_hash_to_int(h1), _hash_to_int(h2))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
