#!/usr/bin/env python3
"""
照片自动筛选工具 v2.0 - 图形化界面
新增：构图水平检测、人脸检测优化、肤色检测优化
"""

import sys
import os as _os
import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

# ── Windows 打包后需要手动指定 Qt 插件路径（macOS 无需）──
if getattr(sys, 'frozen', False) and sys.platform == 'win32':
    _os.environ['QT_PLUGIN_PATH'] = _os.path.join(
        _os.path.dirname(sys.executable), '_internal', 'PySide6', 'plugins')

import numpy as np

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QSlider, QProgressBar,
    QTableWidget, QTableWidgetItem, QFileDialog, QGroupBox,
    QCheckBox, QHeaderView, QMessageBox, QSplashScreen,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QColor, QPixmap, QPainter, QPen, QBrush

import cv2

# ── MediaPipe 延迟加载 ──
_mediapipe_imports = None

def _get_mediapipe():
    global _mediapipe_imports
    if _mediapipe_imports is None:
        from mediapipe.tasks.python import BaseOptions
        from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions
        from mediapipe.tasks.python.vision.core.vision_task_running_mode import VisionTaskRunningMode
        from mediapipe.tasks.python.vision.core.image import Image as MPImage, ImageFormat
        _mediapipe_imports = (BaseOptions, FaceLandmarker, FaceLandmarkerOptions,
                              VisionTaskRunningMode, MPImage, ImageFormat)
    return _mediapipe_imports

# ── 模型路径 ──
def _get_model_path() -> Path:
    if getattr(sys, 'frozen', False):
        # onefile: _MEIPASS 是临时解压目录
        # onedir: _MEIPASS 为 None，用 exe 所在目录
        if hasattr(sys, '_MEIPASS') and sys._MEIPASS:
            return Path(sys._MEIPASS) / "face_landmarker.task"
        else:
            return Path(sys.executable).parent / "face_landmarker.task"
    return Path(__file__).parent / "face_landmarker.task"

MODEL_PATH = _get_model_path()

# ── 配置常量 ──────────────────────────────────────────────
DEFAULT_EAR, DEFAULT_OVER, DEFAULT_UNDER = 0.20, 0.05, 0.15

# v2.0: 扩大肤色范围，兼容深色皮肤
SKIN_L_MIN, SKIN_L_MAX = 25, 230    # 原来 50-220 → 扩展到 25-230
SKIN_A_MIN, SKIN_A_MAX = 3, 35      # 原来 5-30
SKIN_B_MIN, SKIN_B_MAX = 3, 45      # 原来 5-40

# 构图水平检测阈值
LEVEL_ANGLE_TOLERANCE = 9.0         # 偏离轴线中位数 < 9° 算合格
LEVEL_MIN_LINES = 5                 # 至少检测到 N 条线才做判断
LEVEL_CONSISTENCY_THRESHOLD = 15.0  # 线条角度 MAD < 15° 说明角度集中（一致性高）

LEFT_EYE_IDX  = [33, 133, 157, 158, 159, 160, 161, 173]
RIGHT_EYE_IDX = [362, 263, 384, 385, 386, 387, 388, 398]
FACE_SKIN_IDX = [
    10, 67, 69, 108, 109, 151, 299, 337, 338,
    50, 101, 117, 118, 119, 123, 126, 142, 187, 203, 205, 206, 207,
    280, 329, 330, 346, 347, 348, 355, 371, 411, 423, 425, 426, 427,
    152, 169, 170, 199, 200, 201, 208, 210, 211,
]

# ── 数据结构 ──────────────────────────────────────────────
@dataclass
class PhotoResult:
    path: Path
    exposure_ok: bool = False
    exposure_score: float = 0.0
    skin_ok: bool = False
    skin_score: float = 0.0
    eyes_open: bool = False
    eye_score: float = 0.0
    face_detected: bool = False
    level_ok: bool = True           # 构图水平（默认通过）
    level_score: float = 1.0
    level_enabled: bool = False     # 是否启用了构图检测
    error: Optional[str] = None

    @property
    def all_pass(self) -> bool:
        if self.face_detected:
            ok = self.exposure_ok and self.skin_ok and self.eyes_open
            if self.level_enabled:
                ok = ok and self.level_ok
            return ok
        # 无人脸：曝光 + 可选构图
        if self.level_enabled:
            return self.exposure_ok and self.level_ok
        return self.exposure_ok

    @property
    def fail_reason(self) -> str:
        reasons = []
        if not self.face_detected:
            if not self.exposure_ok:
                reasons.append("曝光异常")
            if self.level_enabled and not self.level_ok:
                reasons.append("构图倾斜")
            if not reasons:
                reasons.append("无人脸(曝光通过)")
        else:
            if not self.eyes_open:
                reasons.append("闭眼")
            if not self.skin_ok:
                reasons.append("肤色异常")
            if not self.exposure_ok:
                reasons.append("曝光异常")
            if self.level_enabled and not self.level_ok:
                reasons.append("构图倾斜")
        return ", ".join(reasons) if reasons else "通过"


# ── 检测逻辑 ──────────────────────────────────────────────

def check_exposure(img, over_th, under_th):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    total = gray.size
    over_ratio = float(np.sum(gray > 250) / total)
    under_ratio = float(np.sum(gray < 15) / total)
    ok = over_ratio < over_th and under_ratio < under_th
    over_penalty = max(0, 1 - over_ratio / over_th) if over_th > 0 else 1
    under_penalty = max(0, 1 - under_ratio / under_th) if under_th > 0 else 1
    return bool(ok), float(min(over_penalty, under_penalty))


def check_skin_tone(img, face_landmarks):
    """v2.0: 扩大肤色范围，兼容深色皮肤。使用 LAB 中值而非均值来减少噪声影响。"""
    h, w = img.shape[:2]
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    pixels = []
    for idx in FACE_SKIN_IDX:
        if idx < len(face_landmarks):
            lm = face_landmarks[idx]
            x, y = int(lm.x * w), int(lm.y * h)
            if 0 <= x < w and 0 <= y < h:
                pixels.append(lab[y, x])
    if len(pixels) < 5:
        return False, 0.0

    skin = np.array(pixels)
    # v2.0: 使用中位数 + 去除 10% 极端值，抵抗高光和阴影干扰
    L_m = float(np.percentile(skin[:, 0], 50))
    A_m = float(np.percentile(skin[:, 1], 50))
    B_m = float(np.percentile(skin[:, 2], 50))

    ok = SKIN_L_MIN <= L_m <= SKIN_L_MAX and SKIN_A_MIN <= A_m <= SKIN_A_MAX and SKIN_B_MIN <= B_m <= SKIN_B_MAX

    lc, ac, bc = (SKIN_L_MIN+SKIN_L_MAX)/2, (SKIN_A_MIN+SKIN_A_MAX)/2, (SKIN_B_MIN+SKIN_B_MAX)/2
    ls = max(0, 1 - abs(L_m - lc) / ((SKIN_L_MAX - SKIN_L_MIN) / 2))
    a_s = max(0, 1 - abs(A_m - ac) / ((SKIN_A_MAX - SKIN_A_MIN) / 2))
    bs = max(0, 1 - abs(B_m - bc) / ((SKIN_B_MAX - SKIN_B_MIN) / 2))
    return bool(ok), float((ls + a_s + bs) / 3)


def eye_aspect_ratio(pts):
    v1 = np.linalg.norm(pts[1] - pts[7])
    v2 = np.linalg.norm(pts[2] - pts[6])
    v3 = np.linalg.norm(pts[3] - pts[5])
    h_val = np.linalg.norm(pts[0] - pts[4])
    return float((v1 + v2 + v3) / (3.0 * h_val)) if h_val > 1e-7 else 0.0


def check_eyes_open(face_landmarks, img_shape, ear_th):
    h, w = img_shape[:2]
    def get_pts(indices):
        return np.array([[face_landmarks[i].x * w, face_landmarks[i].y * h] for i in indices])
    left_ear = eye_aspect_ratio(get_pts(LEFT_EYE_IDX))
    right_ear = eye_aspect_ratio(get_pts(RIGHT_EYE_IDX))
    eyes_open = bool(left_ear >= ear_th and right_ear >= ear_th)
    return eyes_open, float((left_ear + right_ear) / 2)


# ── v2.0 新增：构图水平检测 ───────────────────────────────

def _normalize_angle_deviation(angle_deg):
    """将线条角度转为距离最近轴线的偏离量 (0-45°)，0=完美对齐。"""
    a = abs(angle_deg) % 90
    if a > 45:
        a = 90 - a
    return a


def check_level(img) -> tuple[bool, float]:
    """
    智能检测照片是否倾斜。
    原理：先判断线条角度是否"集中"（一致性高），
    如果集中且整体偏离轴线 → 真倾斜；
    如果不集中（透视构图、自然场景）→ 不误判。
    返回 (是否合格, 得分 0-1)
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 1.5)
    edges = cv2.Canny(blurred, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80,
                            minLineLength=60, maxLineGap=15)

    if lines is None or len(lines) < LEVEL_MIN_LINES:
        return True, 1.0  # 线条太少，无法判断，默认通过

    # 计算每条线偏离最近轴线的角度
    deviations = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = np.arctan2(y2 - y1, x2 - x1) * 180.0 / np.pi
        deviations.append(_normalize_angle_deviation(angle))

    deviations = np.array(deviations)

    # 中位数：整体偏离程度（小 = 整体对齐轴线的程度高）
    median_dev = float(np.median(deviations))

    # MAD (Median Absolute Deviation)：角度离散度（小 = 角度集中，大 = 角度分散/透视构图）
    mad = float(np.median(np.abs(deviations - median_dev)))

    # 判断逻辑：
    # 1. 角度集中的照片（mad 小）→ 具有明确的倾斜特征
    # 2. 角度分散的照片（mad 大）→ 透视/自然场景，不做倾斜判断
    # 3. 当角度集中且偏离轴线超过阈值 → 真倾斜
    is_consistent = mad < LEVEL_CONSISTENCY_THRESHOLD   # 线条角度一致
    is_deviated = median_dev > LEVEL_ANGLE_TOLERANCE    # 整体偏离轴线

    ok = not (is_consistent and is_deviated)  # 集中且偏离 = 倾斜
    score = 1.0 if ok else float(max(0, 1 - median_dev / 25.0))

    return ok, score


# ── 处理线程 ──────────────────────────────────────────────

class ProcessWorker(QThread):
    progress = Signal(int, str, bool, str)
    finished_signal = Signal(list)
    error_signal = Signal(str)
    status_update = Signal(str)

    def __init__(self, photo_paths, ear_th, over_th, under_th,
                 output_dir, copy_mode, enable_level=False):
        super().__init__()
        self.photo_paths = photo_paths
        self.ear_th = ear_th
        self.over_th = over_th
        self.under_th = under_th
        self.output_dir = output_dir
        self.copy_mode = copy_mode
        self.enable_level = enable_level

    def run(self):
        try:
            self.status_update.emit("正在加载 AI 模型...")
            BaseOptions, FaceLandmarker, FaceLandmarkerOptions, \
                VisionTaskRunningMode, MPImage, ImageFormat = _get_mediapipe()

            # v2.0: 降低检测阈值 + 使用 model_asset_buffer 避免中文路径问题
            with open(MODEL_PATH, 'rb') as _mf:
                _model_bytes = _mf.read()
            options = FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_buffer=_model_bytes),
                running_mode=VisionTaskRunningMode.IMAGE,
                num_faces=1,
                min_face_detection_confidence=0.4,
                min_face_presence_confidence=0.3,
                min_tracking_confidence=0.5,
                output_face_blendshapes=False,
                output_facial_transformation_matrixes=False,
            )
            landmarker = FaceLandmarker.create_from_options(options)
            self.status_update.emit("正在分析照片...")

            results = []
            for i, p in enumerate(self.photo_paths):
                try:
                    result = PhotoResult(path=p)
                    result.level_enabled = self.enable_level

                    with open(p, 'rb') as f:
                        img_bytes = f.read()
                    img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
                    if img is None:
                        result.error = "无法读取图片"
                        results.append(result)
                        self.progress.emit(i + 1, p.name, result.all_pass, result.fail_reason)
                        continue

                    h, w = img.shape[:2]
                    # v2.0: 长边保留到 2400px（原 1920），帮助检测小脸
                    max_dim = 2400
                    if max(h, w) > max_dim:
                        scale = max_dim / max(h, w)
                        img = cv2.resize(img, (int(w * scale), int(h * scale)))

                    # 1. 曝光
                    result.exposure_ok, result.exposure_score = check_exposure(
                        img, self.over_th, self.under_th)

                    # 2. 构图水平检测（可选）
                    if self.enable_level:
                        result.level_ok, result.level_score = check_level(img)

                    # 3. 人脸检测
                    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    mp_img = MPImage(image_format=ImageFormat.SRGB, data=rgb)
                    face_result = landmarker.detect(mp_img)

                    if face_result.face_landmarks:
                        result.face_detected = True
                        landmarks = face_result.face_landmarks[0]
                        result.eyes_open, result.eye_score = check_eyes_open(
                            landmarks, img.shape, self.ear_th)
                        result.skin_ok, result.skin_score = check_skin_tone(
                            img, landmarks)
                    else:
                        # v2.0: 第一轮未检测到，不做重试（避免误检）
                        result.error = "未检测到人脸"

                    results.append(result)
                except Exception as e:
                    result = PhotoResult(path=p, error=f"异常: {e}")
                    result.level_enabled = self.enable_level
                    results.append(result)

                self.progress.emit(i + 1, p.name, result.all_pass, result.fail_reason)

            landmarker.close()

            passed = [r for r in results if r.all_pass]
            if self.output_dir and passed:
                self.status_update.emit(f"正在输出 {len(passed)} 张合格照片...")
                out_dir = Path(self.output_dir)
                out_dir.mkdir(parents=True, exist_ok=True)
                transfer = shutil.copy2 if self.copy_mode else shutil.move
                for r in passed:
                    dest = out_dir / r.path.name
                    if dest.exists():
                        dest = out_dir / f"{r.path.stem}_filtered{r.path.suffix}"
                    transfer(str(r.path), str(dest))

            self.finished_signal.emit(results)

        except Exception as e:
            import traceback
            self.error_signal.emit(f"{e}\n\n{traceback.format_exc()}")


# ── 闪屏 ──────────────────────────────────────────────────

def create_splash():
    pixmap = QPixmap(400, 200)
    pixmap.fill(QColor("#fafafa"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor("#ddd"), 1))
    painter.setBrush(QBrush(QColor("#fafafa")))
    painter.drawRoundedRect(2, 2, 396, 196, 10, 10)
    painter.setPen(QColor("#333"))
    font = painter.font()
    font.setPointSize(16); font.setBold(True); painter.setFont(font)
    painter.drawText(0, 60, 400, 30, Qt.AlignCenter, "照片自动筛选工具 by HZH")
    font.setPointSize(10); font.setBold(False); painter.setFont(font)
    painter.setPen(QColor("#888"))
    painter.drawText(0, 90, 400, 25, Qt.AlignCenter, "正在启动，请稍候...")
    font.setPointSize(8); painter.setFont(font)
    painter.drawText(0, 170, 400, 20, Qt.AlignCenter, "by HZH  |  v2.0")
    painter.end()
    return QSplashScreen(pixmap)


# ── 主窗口 ────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("照片自动筛选工具 by HZH  v2.0")
        self.setMinimumSize(920, 720)
        self.resize(1020, 780)
        self.results_data = []
        self.worker = None
        self._setup_ui()
        self._apply_style()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # 标题
        title = QLabel("照片自动筛选工具 by HZH  v2.0")
        title_font = QFont(); title_font.setPointSize(16); title_font.setBold(True)
        title.setFont(title_font)
        main_layout.addWidget(title)

        subtitle = QLabel("曝光 + 肤色 + 睁眼 + 构图水平(可选)  |  无人脸仅检测曝光和构图")
        subtitle.setStyleSheet("color: #666;")
        main_layout.addWidget(subtitle)

        # ── 文件夹 ──
        folder_group = QGroupBox("文件夹设置")
        folder_layout = QVBoxLayout(folder_group)
        in_row = QHBoxLayout()
        in_row.addWidget(QLabel("照片文件夹:"))
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("选择照片文件夹...")
        in_row.addWidget(self.input_edit, 1)
        btn_in = QPushButton("浏览..."); btn_in.clicked.connect(self._browse_input)
        in_row.addWidget(btn_in)
        folder_layout.addLayout(in_row)
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("输出文件夹:"))
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("留空则仅分析不输出（可选）")
        out_row.addWidget(self.output_edit, 1)
        btn_out = QPushButton("浏览..."); btn_out.clicked.connect(self._browse_output)
        out_row.addWidget(btn_out)
        folder_layout.addLayout(out_row)
        self.copy_check = QCheckBox("复制照片（否则移动）")
        self.copy_check.setChecked(True)
        folder_layout.addWidget(self.copy_check)
        main_layout.addWidget(folder_group)

        # ── 检测选项 ──
        option_group = QGroupBox("检测选项")
        option_layout = QVBoxLayout(option_group)
        self.level_check = QCheckBox("检测构图水平（横平竖直）[测试功能]")
        self.level_check.setToolTip("测试功能，建议会议照片开启")
        option_layout.addWidget(self.level_check)
        main_layout.addWidget(option_group)

        # ── 阈值 ──
        thresh_group = QGroupBox("检测阈值（拖动滑块调整）")
        thresh_layout = QVBoxLayout(thresh_group)
        self.ear_slider = self._make_slider(
            thresh_layout, "睁眼灵敏度", DEFAULT_EAR, 0.15, 0.25, 0.01, "越小越宽容")
        self.over_slider = self._make_slider(
            thresh_layout, "过曝容忍度", DEFAULT_OVER, 0.01, 0.20, 0.01, "越大越宽容")
        self.under_slider = self._make_slider(
            thresh_layout, "欠曝容忍度", DEFAULT_UNDER, 0.05, 0.40, 0.01, "越大越宽容")
        main_layout.addWidget(thresh_group)

        # ── 按钮 ──
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("开始分析")
        self.start_btn.setMinimumHeight(36)
        self.start_btn.clicked.connect(self._start_analysis)
        btn_row.addWidget(self.start_btn)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setMinimumHeight(36); self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_analysis)
        btn_row.addWidget(self.stop_btn)
        btn_row.addStretch()
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #888;")
        btn_row.addWidget(self.status_label)
        main_layout.addLayout(btn_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # ── 表格 ──
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["状态", "文件名", "结果", "详情"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 50)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        main_layout.addWidget(self.table, 1)

        # ── 汇总 ──
        self.summary_label = QLabel("")
        self.summary_label.setFont(QFont("", 10, QFont.Bold))
        main_layout.addWidget(self.summary_label)

        # 水印
        watermark = QLabel("by HZH  v2.0")
        watermark.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        watermark.setStyleSheet("color: rgba(180,180,180,80); font-size: 11px;")
        main_layout.addWidget(watermark)

    def _make_slider(self, parent_layout, name, default, min_v, max_v, step, hint):
        row = QHBoxLayout()
        label = QLabel(f"{name}:"); label.setMinimumWidth(80)
        row.addWidget(label)
        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(int(min_v / step)); slider.setMaximum(int(max_v / step))
        slider.setValue(int(default / step))
        slider.setTickPosition(QSlider.TicksBelow)
        slider.setTickInterval(int((max_v - min_v) / step / 10))
        row.addWidget(slider, 1)
        value_label = QLabel(f"{default:.2f}")
        value_label.setMinimumWidth(40)
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(value_label)
        hint_label = QLabel(hint)
        hint_label.setStyleSheet("color: #999; font-size: 11px;"); hint_label.setMinimumWidth(160)
        row.addWidget(hint_label)
        slider.valueChanged.connect(lambda v, vl=value_label, s=step: vl.setText(f"{v * s:.2f}"))
        parent_layout.addLayout(row)
        return slider

    def _apply_style(self):
        self.setStyleSheet("""
            QGroupBox { font-weight: bold; border: 1px solid #ccc; border-radius: 6px;
                margin-top: 8px; padding-top: 16px; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
            QPushButton { padding: 6px 16px; border: 1px solid #bbb; border-radius: 4px;
                background: #f5f5f5; }
            QPushButton:hover { background: #e0e0e0; }
            QPushButton#startBtn { background: #4CAF50; color: white; border: none;
                font-weight: bold; }
            QPushButton#startBtn:hover { background: #43A047; }
            QPushButton#startBtn:disabled { background: #ccc; }
            QTableWidget { border: 1px solid #ddd; border-radius: 4px; gridline-color: #eee; }
            QHeaderView::section { background: #f8f8f8; padding: 6px; border: none;
                border-bottom: 2px solid #ddd; font-weight: bold; }
            QSlider::groove:horizontal { border: 1px solid #ccc; height: 6px;
                background: #eee; border-radius: 3px; }
            QSlider::handle:horizontal { background: #4CAF50; border: none;
                width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; }
            QProgressBar { border: 1px solid #ccc; border-radius: 4px; text-align: center; }
            QProgressBar::chunk { background: #4CAF50; border-radius: 3px; }
            QCheckBox { spacing: 6px; }
        """)
        self.start_btn.setObjectName("startBtn")

    # ── 槽函数 ──
    def _browse_input(self):
        folder = QFileDialog.getExistingDirectory(self, "选择照片文件夹")
        if folder: self.input_edit.setText(folder)

    def _browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
        if folder: self.output_edit.setText(folder)

    def _start_analysis(self):
        input_dir = self.input_edit.text().strip()
        if not input_dir:
            QMessageBox.warning(self, "提示", "请先选择照片文件夹。"); return
        input_path = Path(input_dir)
        if not input_path.is_dir():
            QMessageBox.warning(self, "提示", f"文件夹不存在:\n{input_dir}"); return
        extensions = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.webp'}
        photo_paths = sorted([p for p in input_path.iterdir()
                              if p.suffix.lower() in extensions and p.is_file()])
        if not photo_paths:
            QMessageBox.information(self, "提示", "该文件夹中没有找到照片文件。"); return

        ear, over, under = (self.ear_slider.value() * 0.01,
                            self.over_slider.value() * 0.01,
                            self.under_slider.value() * 0.01)
        output_dir = self.output_edit.text().strip() or None
        enable_level = self.level_check.isChecked()

        self.table.setRowCount(0)
        self.results_data = []
        self.summary_label.setText("")
        self.progress_bar.setMaximum(len(photo_paths))
        self.progress_bar.setValue(0); self.progress_bar.setVisible(True)
        self.start_btn.setEnabled(False); self.stop_btn.setEnabled(True)
        self.status_label.setText("正在加载 AI 模型...")

        self.worker = ProcessWorker(photo_paths, ear, over, under,
                                    output_dir, self.copy_check.isChecked(),
                                    enable_level)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.error_signal.connect(self._on_error)
        self.worker.status_update.connect(self.status_label.setText)
        self.worker.start()

    def _stop_analysis(self):
        if self.worker and self.worker.isRunning():
            self.worker.terminate(); self.worker.wait()
            self.status_label.setText("已停止")
            self.start_btn.setEnabled(True); self.stop_btn.setEnabled(False)
            self._update_summary()

    def _on_progress(self, index, filename, passed, reason):
        self.progress_bar.setValue(index)
        self.status_label.setText(f"分析中: {filename}")
        row = self.table.rowCount(); self.table.insertRow(row)
        status_item = QTableWidgetItem("OK" if passed else "NG")
        status_item.setTextAlignment(Qt.AlignCenter)
        status_item.setForeground(QColor("#2e7d32") if passed else QColor("#e53935"))
        self.table.setItem(row, 0, status_item)
        self.table.setItem(row, 1, QTableWidgetItem(filename))
        result_item = QTableWidgetItem("通过" if passed else "不合格")
        result_item.setForeground(QColor("#2e7d32") if passed else QColor("#e53935"))
        self.table.setItem(row, 2, result_item)
        self.table.setItem(row, 3, QTableWidgetItem(reason))
        self.table.scrollToBottom()

    def _on_finished(self, results):
        self.results_data = results
        self.progress_bar.setVisible(False)
        self.start_btn.setEnabled(True); self.stop_btn.setEnabled(False)
        self.status_label.setText("分析完成")
        self._update_summary()

        # 彩蛋：开启构图检测时，根据合格率弹出魏老师评语
        if results and any(r.level_enabled for r in results):
            passed = [r for r in results if r.all_pass]
            rate = len(passed) / len(results) * 100 if results else 0
            if rate < 30:
                QMessageBox.information(self, "魏老师点评", "你这拍的有什么意义呢？——魏老师")
            elif rate > 80:
                QMessageBox.information(self, "魏老师点评", "哇！代表作！——魏老师")

    def _on_error(self, error_msg):
        self.progress_bar.setVisible(False)
        self.start_btn.setEnabled(True); self.stop_btn.setEnabled(False)
        self.status_label.setText("发生错误")
        QMessageBox.critical(self, "错误", f"处理过程中发生错误:\n\n{error_msg}")

    def _update_summary(self):
        if not self.results_data: return
        passed = [r for r in self.results_data if r.all_pass]
        failed = [r for r in self.results_data if not r.all_pass]
        no_face = [r for r in self.results_data if not r.face_detected]
        has_face = [r for r in self.results_data if r.face_detected]
        closed = [r for r in has_face if not r.eyes_open]
        bad_skin = [r for r in has_face if not r.skin_ok]
        bad_exp = [r for r in self.results_data if not r.exposure_ok]
        bad_level = [r for r in self.results_data if r.level_enabled and not r.level_ok]
        pct = len(passed) / len(self.results_data) * 100 if self.results_data else 0
        parts = [
            f"总计: {len(self.results_data)} 张",
            f"合格: {len(passed)} 张 ({pct:.1f}%)",
            f"不合格: {len(failed)} 张",
            f"无人脸: {len(no_face)}",
            f"闭眼: {len(closed)}",
            f"肤色: {len(bad_skin)}",
            f"曝光: {len(bad_exp)}",
        ]
        if bad_level:
            parts.append(f"构图: {len(bad_level)}")
        self.summary_label.setText("  |  ".join(parts))


# ── 入口 ──────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("照片筛选工具 v2.0")
    try:
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except Exception:
        pass
    splash = create_splash()
    splash.show(); app.processEvents()
    splash.showMessage("正在初始化界面...", Qt.AlignHCenter | Qt.AlignBottom, QColor("#888"))
    app.processEvents()
    window = MainWindow()
    splash.showMessage("就绪!", Qt.AlignHCenter | Qt.AlignBottom, QColor("#4CAF50"))
    app.processEvents()
    window.show()
    splash.finish(window)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
