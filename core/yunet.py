"""
OpenCV YuNet 人脸检测 — MediaPipe 双引擎互补 (v5.3)。

YuNet (cv2.FaceDetectorYN) 由 OpenCV 内置，模型 face_detection_yunet_2023mar.onnx
需放在项目根目录（与 face_landmarker.task 同级）。模型缺失或 OpenCV 版本过旧时
自动降级：detect 返回空列表，不影响现有 MediaPipe 流程。

中文路径处理：OpenCV 4.10 的 FaceDetectorYN_create 只接受文件路径（不支持
buffer），Windows 下非 ASCII 路径可能失败 → 自动写入临时 ASCII 路径重试。

纯函数（bbox_from_landmarks / iou / merge_boxes / map_crop_to_orig）可独立单测。
"""

import os
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional, Tuple

import cv2
import numpy as np

# ── 模型路径（与 face_landmarker.task 相同的解析逻辑）──

def _get_model_path() -> Path:
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS') and sys._MEIPASS:
            return Path(sys._MEIPASS) / "face_detection_yunet_2023mar.onnx"
        return Path(sys.executable).parent / "face_detection_yunet_2023mar.onnx"
    return Path(__file__).resolve().parent.parent / "face_detection_yunet_2023mar.onnx"


MODEL_PATH = _get_model_path()

# YuNet 输入分析尺寸（长边上限；坐标按比例映射回原图）
_YUNET_MAX_DIM = 1280
# 补检场景的置信度阈值（比默认 0.9 宽松，配合 MediaPipe 兜底）
_YUNET_SCORE_THRESHOLD = 0.6


class YuNetManager:
    """YuNet 检测器管理器：懒加载 + 线程局部实例 + 中文路径回退。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._model_bytes: Optional[bytes] = None
        self._thread_local = threading.local()
        self._available: Optional[bool] = None

    @property
    def available(self) -> bool:
        """模型存在 + OpenCV 支持 FaceDetectorYN。"""
        if self._available is None:
            self._available = (
                hasattr(cv2, "FaceDetectorYN")
                and MODEL_PATH.exists()
                and MODEL_PATH.stat().st_size > 1000
            )
        return self._available

    @property
    def model_bytes(self) -> bytes:
        if self._model_bytes is None:
            with self._lock:
                if self._model_bytes is None:
                    with open(MODEL_PATH, "rb") as f:
                        self._model_bytes = f.read()
        return self._model_bytes

    def _create_detector(self, input_size: Tuple[int, int]):
        """创建 FaceDetectorYN。优先直读路径，中文路径失败则临时 ASCII 文件。"""
        args = (str(MODEL_PATH), "", input_size,
                _YUNET_SCORE_THRESHOLD, 0.3, 5000)
        try:
            return cv2.FaceDetectorYN_create(*args)
        except Exception:
            tmp = None
            try:
                fd, tmp = tempfile.mkstemp(suffix=".onnx")
                os.close(fd)
                with open(tmp, "wb") as f:
                    f.write(self.model_bytes)
                return cv2.FaceDetectorYN_create(tmp, "", input_size,
                                                 _YUNET_SCORE_THRESHOLD, 0.3, 5000)
            except Exception:
                raise
            finally:
                if tmp:
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass

    def get_detector(self, input_size: Tuple[int, int]):
        """当前线程的检测器（懒创建 + 更新输入尺寸）。不可用时返回 None。"""
        if not self.available:
            return None
        det = getattr(self._thread_local, "detector", None)
        if det is None:
            det = self._create_detector(input_size)
            self._thread_local.detector = det
        try:
            det.setInputSize(input_size)
        except Exception:
            pass
        return det


# ── 检测入口 ──────────────────────────────────────────────

def detect_faces_yunet(img: np.ndarray, manager: Optional[YuNetManager]) -> List[dict]:
    """
    在原图上用 YuNet 检测人脸（自动缩放到 _YUNET_MAX_DIM 分析，坐标映射回原图）。

    返回 list[dict]，每项：
        {"bbox": (x, y, w, h), "score": float, "landmarks": (5, 2) ndarray}
    模型不可用 / 检测失败时返回 []。
    """
    if manager is None or not manager.available:
        return []
    h, w = img.shape[:2]
    if h < 20 or w < 20:
        return []

    scale = min(1.0, _YUNET_MAX_DIM / max(h, w))
    iw, ih = max(8, int(w * scale)), max(8, int(h * scale))
    small = cv2.resize(img, (iw, ih)) if scale < 1.0 else img

    det = manager.get_detector((iw, ih))
    if det is None:
        return []
    try:
        _, faces = det.detect(small)
    except Exception:
        return []
    if faces is None or len(faces) == 0:
        return []

    inv = 1.0 / scale
    results = []
    for f in faces:
        x, y, fw, fh = float(f[0]), float(f[1]), float(f[2]), float(f[3])
        score = float(f[14]) if len(f) > 14 else 0.0
        lm = np.asarray(f[4:14], dtype=np.float64).reshape(5, 2) * inv
        results.append({
            "bbox": (int(x * inv), int(y * inv), int(fw * inv), int(fh * inv)),
            "score": score,
            "landmarks": lm,
        })
    return results


# ── 纯函数：坐标映射 / 去重 / 裁剪（可单测）──────────────

def bbox_from_landmarks(landmarks, img_shape: Tuple[int, int]) -> Tuple[int, int, int, int]:
    """由 MediaPipe 关键点估算人脸包围盒 (x, y, w, h)。"""
    h, w = img_shape[:2]
    xs, ys = [], []
    for lm in landmarks:
        xs.append(lm.x * w)
        ys.append(lm.y * h)
    if not xs:
        return (0, 0, w, h)
    x1, y1 = int(min(xs)), int(min(ys))
    x2, y2 = int(max(xs)), int(max(ys))
    return x1, y1, max(1, x2 - x1), max(1, y2 - y1)


def iou(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> float:
    """两个 (x,y,w,h) 框的 IoU。"""
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def merge_boxes(existing: List[Tuple[int, int, int, int]],
                candidates: List[dict],
                iou_threshold: float = 0.3) -> List[dict]:
    """
    过滤与已有框 IoU 过高的 YuNet 候选，返回"需要补检"的新框。
    candidates: detect_faces_yunet 返回的列表。
    """
    kept = []
    for cand in candidates:
        dup = any(iou(cand["bbox"], b) >= iou_threshold for b in existing)
        if not dup:
            kept.append(cand)
    return kept


def map_crop_to_orig(landmarks, crop_rect: Tuple[int, int, int, int],
                     orig_shape: Tuple[int, int]) -> List[SimpleNamespace]:
    """
    把"裁剪图上的检测结果"（landmarks 坐标为裁剪图归一化 0~1）映射回原图归一化坐标。
    crop_rect: (x, y, w, h)；orig_shape: (H, W)。
    返回与原图坐标系兼容的关键点对象列表（.x/.y/.z）。
    """
    cx, cy, cw, ch = crop_rect
    oh, ow = orig_shape[:2]
    out = []
    for lm in landmarks:
        x_orig = lm.x * cw + cx
        y_orig = lm.y * ch + cy
        out.append(SimpleNamespace(
            x=float(min(1.0, max(0.0, x_orig / ow))),
            y=float(min(1.0, max(0.0, y_orig / oh))),
            z=float(getattr(lm, "z", 0.0)),
        ))
    return out


def expand_bbox(bbox: Tuple[int, int, int, int], img_shape: Tuple[int, int],
                margin: float = 0.3) -> Tuple[int, int, int, int]:
    """按比例外扩包围盒（并夹到图像边界），供裁剪补检使用。"""
    h, w = img_shape[:2]
    x, y, bw, bh = bbox
    pad_w = int(bw * margin)
    pad_h = int(bh * margin)
    x1 = max(0, x - pad_w)
    y1 = max(0, y - pad_h)
    x2 = min(w, x + bw + pad_w)
    y2 = min(h, y + bh + pad_h)
    return x1, y1, max(1, x2 - x1), max(1, y2 - y1)
