"""
主窗口 — 照片自动筛选工具 v5.0 GUI。
从 photo_filter_gui.py 重构拆分。
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QSlider, QProgressBar,
    QTableWidget, QTableWidgetItem, QFileDialog, QGroupBox,
    QCheckBox, QComboBox, QFrame, QHeaderView, QMessageBox, QSplashScreen,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QPixmap, QPainter, QPen, QBrush

from core.models import DetectionConfig
from gui.worker import ProcessWorker
from gui.widgets.toggle_switch import ToggleSwitch
from gui.theme_manager import ThemeManager
from gui.preview_loader import PreviewManager
from utils.constants import (
    DEFAULT_EAR_THRESHOLD, DEFAULT_OVEREXPOSURE_RATIO, DEFAULT_UNDEREXPOSURE_RATIO,
    DEFAULT_EXPRESSION_SMILE_THRESHOLD, DEFAULT_RED_EYE_THRESHOLD,
    EAR_MIN, EAR_MAX, ALL_SUPPORTED_EXTENSIONS,
    OVER_SLIDER_RANGE, UNDER_SLIDER_RANGE, EAR_SLIDER_RANGE,
    EXPRESSION_SMILE_SLIDER_RANGE, RED_EYE_SLIDER_RANGE,
    FACE_MODES, FACE_MODE_BEST, FACE_MODE_ALL,
)
from utils.config import AppConfig


# ── 闪屏 ──────────────────────────────────────────────────

def create_splash() -> QSplashScreen:
    """创建启动闪屏。"""
    pixmap = QPixmap(400, 200)
    pixmap.fill(QColor("#fafafa"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor("#ddd"), 1))
    painter.setBrush(QBrush(QColor("#fafafa")))
    painter.drawRoundedRect(2, 2, 396, 196, 10, 10)
    painter.setPen(QColor("#333"))
    font = painter.font()
    font.setPointSize(16)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(0, 60, 400, 30, Qt.AlignCenter, "照片自动筛选工具 by HZH")
    font.setPointSize(10)
    font.setBold(False)
    painter.setFont(font)
    painter.setPen(QColor("#888"))
    painter.drawText(0, 90, 400, 25, Qt.AlignCenter, "正在启动，请稍候...")
    font.setPointSize(8)
    painter.setFont(font)
    painter.drawText(0, 170, 400, 20, Qt.AlignCenter, "by HZH  |  v5.1")
    painter.end()
    return QSplashScreen(pixmap)


# ── 主窗口 ────────────────────────────────────────────────

class MainWindow(QMainWindow):
    """照片筛选工具主窗口。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("照片自动筛选工具 by HZH  v5.1")
        self.setMinimumSize(920, 720)
        self.resize(1020, 780)
        self.results_data = []
        self.worker = None
        self._app_config = AppConfig()
        # 异步缩略图预览（v5.1: 大图/RAW 解码不进主线程）
        self._preview_mgr = PreviewManager(self)
        self._preview_path = ""   # 当前预览对应的路径（防过期覆盖）

        self._setup_ui()
        self._apply_style()
        self._restore_settings()

    def _setup_ui(self):
        """构建界面布局。"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(12, 10, 12, 10)

        # 标题行 + 主题切换按钮
        title_row = QHBoxLayout()
        title = QLabel("照片自动筛选工具 by HZH  v5.1")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title_row.addWidget(title)
        title_row.addStretch()

        # 设置按钮（右上角）
        settings_btn = QPushButton("⚙ 设置")
        settings_btn.setMinimumHeight(30)
        settings_btn.clicked.connect(self._open_settings)
        title_row.addWidget(settings_btn)
        main_layout.addLayout(title_row)

        # ── 文件夹 ──
        folder_group = QGroupBox("文件夹设置")
        folder_layout = QVBoxLayout(folder_group)

        in_row = QHBoxLayout()
        in_row.addWidget(QLabel("照片文件夹:"))
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("选择照片文件夹...")
        in_row.addWidget(self.input_edit, 1)
        btn_in = QPushButton("浏览...")
        btn_in.clicked.connect(self._browse_input)
        in_row.addWidget(btn_in)
        folder_layout.addLayout(in_row)

        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("输出文件夹:"))
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("留空则仅分析不输出（可选）")
        out_row.addWidget(self.output_edit, 1)
        btn_out = QPushButton("浏览...")
        btn_out.clicked.connect(self._browse_output)
        out_row.addWidget(btn_out)
        folder_layout.addLayout(out_row)

        self.copy_check = ToggleSwitch("复制照片（否则移动）")
        self.copy_check.setChecked(True)
        folder_layout.addWidget(self.copy_check)

        main_layout.addWidget(folder_group)

        # ── 检测选项（合并：开关 + 阈值）──
        detect_group = QGroupBox("检测选项")
        detect_layout = QVBoxLayout(detect_group)
        detect_layout.setSpacing(4)
        detect_layout.setContentsMargins(10, 14, 10, 8)

        # ── 开关（3列紧凑网格）──
        toggle_grid = QHBoxLayout()
        toggle_grid.setSpacing(10)
        col_left = QVBoxLayout(); col_left.setSpacing(4)
        col_mid = QVBoxLayout(); col_mid.setSpacing(4)
        col_right = QVBoxLayout(); col_right.setSpacing(4)

        # ── 左列：人脸检测 + 合照模式 + 表情 ──

        # 人脸检测 + 合照模式（同行）
        face_row = QHBoxLayout()
        face_row.setSpacing(6)
        self.face_check = ToggleSwitch("启用人脸检测（睁眼+肤色）")
        self.face_check.setChecked(True)
        self.face_check.setToolTip("关闭后仅检测曝光、构图和模糊，大幅提升速度")
        self.face_check.toggled.connect(self._on_face_toggled)
        face_row.addWidget(self.face_check, 1)

        self.face_mode_combo = QComboBox()
        self.face_mode_combo.addItem("最优人脸", FACE_MODE_BEST)
        self.face_mode_combo.addItem("所有人脸 ✓", FACE_MODE_ALL)
        self.face_mode_combo.setToolTip(
            "最优人脸：生活照模式，取最佳人脸评估\n"
            "所有人脸：合照模式，每张脸都必须通过，适用于会议/活动合照"
        )
        self.face_mode_combo.setFixedWidth(100)
        self.face_mode_combo.setStyleSheet("font-size: 11px; padding: 2px 4px;")
        face_row.addWidget(self.face_mode_combo, 0)
        col_left.addLayout(face_row)

        # 表情检测 + 笑容阈值（紧跟人脸检测）
        expr_row = QHBoxLayout()
        expr_row.setSpacing(6)
        expr_row.setContentsMargins(2, 0, 0, 0)
        self.expression_check = ToggleSwitch("检测笑容/表情")
        self.expression_check.setToolTip("基于 MediaPipe Blendshapes，检测笑容和表情质量")
        self.expression_check.toggled.connect(self._on_expression_toggled)
        expr_row.addWidget(self.expression_check)

        self.expression_slider = QSlider(Qt.Horizontal)
        self.expression_slider.setMinimum(0)
        self.expression_slider.setMaximum(12)
        self.expression_slider.setValue(5)
        self.expression_slider.setFixedWidth(70)
        self.expression_slider.setToolTip("笑容阈值，越低越宽容")
        expr_row.addWidget(self.expression_slider, 0)
        self.expression_value_label = QLabel("0.25")
        self.expression_value_label.setFixedWidth(24)
        self.expression_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.expression_value_label.setStyleSheet("font-size: 10px; color: #888;")
        expr_row.addWidget(self.expression_value_label, 0)
        expr_row.addStretch()
        self.expression_slider.setEnabled(False)
        self.expression_slider.valueChanged.connect(
            lambda v: self.expression_value_label.setText(f"{v * 0.05:.2f}"))
        col_left.addLayout(expr_row)

        # 构图水平
        self.level_check = ToggleSwitch("检测构图水平")
        self.level_check.setToolTip("检测照片是否倾斜，支持地平线和通用两种方法")
        self.level_check.toggled.connect(self._on_level_toggled)
        col_left.addWidget(self.level_check)

        # 构图检测子选项紧跟其后
        level_detail_row = QHBoxLayout()
        level_detail_row.setContentsMargins(2, 0, 0, 0)
        level_detail_row.setSpacing(2)
        self.level_method_combo = QComboBox()
        self.level_method_combo.addItem("地平线检测（推荐）", "horizon")
        self.level_method_combo.addItem("通用检测", "general")
        self.level_method_combo.setToolTip("地平线检测：只找长水平线判断倾斜，复杂场景不误判 | 通用检测：分析所有线条角度一致性（适合建筑/室内）")
        self.level_method_combo.setFixedWidth(162)
        level_detail_row.addWidget(self.level_method_combo)
        level_detail_row.addWidget(QLabel("  严格度"), 0)
        self.level_angle_slider = QSlider(Qt.Horizontal)
        self.level_angle_slider.setMinimum(4)
        self.level_angle_slider.setMaximum(24)
        self.level_angle_slider.setValue(10)
        self.level_angle_slider.setFixedWidth(80)
        level_detail_row.addWidget(self.level_angle_slider, 0)
        self.level_angle_label = QLabel("5.0°")
        self.level_angle_label.setFixedWidth(28)
        self.level_angle_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        level_detail_row.addWidget(self.level_angle_label, 0)
        level_detail_row.addStretch()
        col_left.addLayout(level_detail_row)
        self.level_method_combo.setEnabled(False)
        self.level_angle_slider.setEnabled(False)
        self.level_angle_slider.valueChanged.connect(self._on_level_angle_changed)
        self.level_method_combo.currentIndexChanged.connect(self._on_level_method_changed)

        # ── 中间列：红眼 ──

        self.red_eye_check = ToggleSwitch("检测红眼")
        self.red_eye_check.setToolTip("检测闪光灯造成的红眼现象（HSV 色彩分析）")
        self.red_eye_check.toggled.connect(self._on_red_eye_toggled)
        col_mid.addWidget(self.red_eye_check)

        # 红眼阈值
        re_inline = QHBoxLayout()
        re_inline.setSpacing(4)
        re_inline.setContentsMargins(2, 0, 0, 0)
        self.red_eye_slider = QSlider(Qt.Horizontal)
        self.red_eye_slider.setMinimum(2)
        self.red_eye_slider.setMaximum(25)
        self.red_eye_slider.setValue(8)
        re_inline.addWidget(QLabel("阈值"), 0)
        self.red_eye_slider.setFixedWidth(80)
        re_inline.addWidget(self.red_eye_slider, 0)
        self.red_eye_value_label = QLabel("0.08")
        self.red_eye_value_label.setFixedWidth(28)
        self.red_eye_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.red_eye_value_label.setStyleSheet("font-size: 10px; color: #888;")
        re_inline.addWidget(self.red_eye_value_label, 0)
        re_inline.addStretch()
        self.red_eye_slider.setEnabled(False)
        self.red_eye_slider.valueChanged.connect(
            lambda v: self.red_eye_value_label.setText(f"{v * 0.01:.2f}"))
        col_mid.addLayout(re_inline)

        col_mid.addStretch()

        # ── 右列：模糊 + 重复 ──

        self.blur_check = ToggleSwitch("检测模糊")
        self.blur_check.setToolTip("智能检测模糊照片（取最清晰区域判断，浅景深不误判）")
        self.blur_check.toggled.connect(self._on_blur_toggled)
        col_right.addWidget(self.blur_check)

        # 模糊宽容度紧跟其后
        blur_inline = QHBoxLayout()
        blur_inline.setSpacing(4)
        blur_inline.setContentsMargins(2, 0, 0, 0)
        self.blur_slider = QSlider(Qt.Horizontal)
        self.blur_slider.setMinimum(2)
        self.blur_slider.setMaximum(40)
        self.blur_slider.setValue(8)
        blur_inline.addWidget(QLabel("宽容度"), 0)
        self.blur_slider.setFixedWidth(100)
        blur_inline.addWidget(self.blur_slider, 0)
        self.blur_value_label = QLabel("40")
        self.blur_value_label.setFixedWidth(24)
        self.blur_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        blur_inline.addWidget(self.blur_value_label, 0)
        blur_inline.addStretch()
        self.blur_slider.setEnabled(False)
        self.blur_slider.valueChanged.connect(
            lambda v: self.blur_value_label.setText(str(v * 5)))
        col_right.addLayout(blur_inline)

        self.duplicate_check = ToggleSwitch("检测重复照片")
        self.duplicate_check.setToolTip("使用 dHash 感知哈希识别相似/重复照片")
        col_right.addWidget(self.duplicate_check)

        col_right.addStretch()

        toggle_grid.addLayout(col_left, 1)
        toggle_grid.addLayout(col_mid, 1)
        toggle_grid.addLayout(col_right, 1)
        detect_layout.addLayout(toggle_grid)


        self.advanced_widget = QWidget()
        self.advanced_widget.setVisible(False)
        adv_layout = QVBoxLayout(self.advanced_widget)
        adv_layout.setContentsMargins(0, 4, 0, 0)
        adv_layout.setSpacing(4)
        # ── 阈值（双列紧凑）──
        config = self._app_config
        threshold_grid = QHBoxLayout()
        threshold_grid.setSpacing(12)
        col1 = QVBoxLayout(); col1.setSpacing(2)
        col2 = QVBoxLayout(); col2.setSpacing(2)

        self.ear_slider = self._make_compact_slider(
            col1, "睁眼灵敏度", config.ear_threshold,
            EAR_SLIDER_RANGE[0], EAR_SLIDER_RANGE[1], EAR_SLIDER_RANGE[2])
        self.over_slider = self._make_compact_slider(
            col1, "过曝容忍度", config.over_threshold,
            OVER_SLIDER_RANGE[0], OVER_SLIDER_RANGE[1], OVER_SLIDER_RANGE[2])
        self.under_slider = self._make_compact_slider(
            col2, "欠曝容忍度", config.under_threshold,
            UNDER_SLIDER_RANGE[0], UNDER_SLIDER_RANGE[1], UNDER_SLIDER_RANGE[2])

        # 重复检测敏感度（v5.1 新增 UI：此前汉明阈值写死为 5，不可调）
        dup_row = QHBoxLayout()
        dup_row.setSpacing(4)
        dup_label = QLabel("重复敏感度:")
        dup_label.setStyleSheet("font-size: 11px; color: #555;")
        dup_row.addWidget(dup_label)
        self.duplicate_hamming_slider = QSlider(Qt.Horizontal)
        self.duplicate_hamming_slider.setMinimum(1)
        self.duplicate_hamming_slider.setMaximum(15)
        self.duplicate_hamming_slider.setValue(int(config.duplicate_hamming))
        self.duplicate_hamming_slider.setFixedWidth(120)
        self.duplicate_hamming_slider.setToolTip(
            "重复判定阈值（汉明距离），越小越严格（只找几乎相同的照片）；\n"
            "越大越宽容（连取景略有不同的连拍也算重复）")
        dup_row.addWidget(self.duplicate_hamming_slider, 0)
        self.duplicate_hamming_label = QLabel(str(config.duplicate_hamming))
        self.duplicate_hamming_label.setFixedWidth(36)
        self.duplicate_hamming_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.duplicate_hamming_label.setStyleSheet("font-size: 11px;")
        dup_row.addWidget(self.duplicate_hamming_label, 0)
        dup_row.addStretch()
        self.duplicate_hamming_slider.valueChanged.connect(
            lambda v: self.duplicate_hamming_label.setText(str(v)))
        col2.addLayout(dup_row)

        threshold_grid.addLayout(col1, 1)
        threshold_grid.addLayout(col2, 1)
        adv_layout.addLayout(threshold_grid)

        # ── 高级选项 展开/收起 ──

        adv_toggle_row = QHBoxLayout()
        self.adv_toggle_btn = QPushButton("▸ 阈值调整")
        self.adv_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.adv_toggle_btn.setMinimumHeight(32)
        self.adv_toggle_btn.setStyleSheet(
            "QPushButton {"
            "  color: #5c6bc0; font-size: 12px; font-weight: bold;"
            "  border: 1px dashed #b0b8d0; border-radius: 8px;"
            "  background: #f0f3ff; padding: 6px 14px;"
            "}"
            "QPushButton:hover {"
            "  background: #e4e8f8; border-color: #5c6bc0;"
            "  color: #3949ab;"
            "}")
        self.adv_toggle_btn.clicked.connect(self._toggle_advanced)
        adv_toggle_row.addWidget(self.adv_toggle_btn)
        adv_toggle_row.addStretch()
        detect_layout.addLayout(adv_toggle_row)



        detect_layout.addWidget(self.advanced_widget)

        main_layout.addWidget(detect_group)

        # ── 按钮 ──
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("开始分析")
        self.start_btn.setMinimumHeight(36)
        self.start_btn.clicked.connect(self._start_analysis)
        btn_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.setMinimumHeight(36)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_analysis)
        btn_row.addWidget(self.stop_btn)

        btn_row.addStretch()
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #888;")
        btn_row.addWidget(self.status_label)
        main_layout.addLayout(btn_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFormat("%p% (%v/%m)")
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # ── 表格 + 预览（左右分栏）──
        split_row = QHBoxLayout()
        split_row.setSpacing(8)

        # 左侧：结果表格
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["状态", "文件名", "结果", "详情"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 40)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        # 双击打开原图，单击预览
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        split_row.addWidget(self.table, 1)

        # 右侧：实时预览窗
        self.preview_label = QLabel()
        self.preview_label.setFixedWidth(220)
        self.preview_label.setMinimumHeight(200)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet(
            "border: 1px solid #dce1e6; border-radius: 8px;"
            "background: #f0f2f5; color: #999; font-size: 11px;")
        self.preview_label.setText("预览")
        self.preview_label.setVisible(False)
        split_row.addWidget(self.preview_label)

        main_layout.addLayout(split_row, 1)

        # ── 汇总卡片 ──
        self.summary_widget = QWidget()
        self.summary_widget.setVisible(False)
        summary_row = QHBoxLayout(self.summary_widget)
        summary_row.setContentsMargins(0, 4, 0, 0)
        summary_row.setSpacing(10)
        self.summary_cards = {}
        for key, label, color in [
            ("pass", "合格", "#2e7d32"),
            ("fail", "不合格", "#c62828"),
            ("duplicate", "重复", "#e65100"),
        ]:
            card = QFrame()
            card.setStyleSheet(f"background: {color}15; border: 1px solid {color}40;"
                              f"border-radius: 8px; padding: 6px 12px;")
            cl = QVBoxLayout(card)
            cl.setSpacing(0)
            cl.setContentsMargins(14, 8, 14, 8)
            num = QLabel("0")
            num.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: bold; border: none; background: transparent;")
            num.setAlignment(Qt.AlignCenter)
            cl.addWidget(num)
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {color}; font-size: 11px; border: none; background: transparent;")
            lbl.setAlignment(Qt.AlignCenter)
            cl.addWidget(lbl)
            summary_row.addWidget(card)
            self.summary_cards[key] = num
        summary_row.addStretch()
        main_layout.addWidget(self.summary_widget)

        # 水印
        watermark = QLabel("by HZH  v5.0")
        watermark.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        watermark.setStyleSheet("color: rgba(180,180,180,80); font-size: 11px;")
        main_layout.addWidget(watermark)

    def _make_slider(self, parent_layout, name, default_val, min_v, max_v, step, hint):
        """创建带标签的滑块控件。"""
        row = QHBoxLayout()
        label = QLabel(f"{name}:")
        label.setMinimumWidth(80)
        row.addWidget(label)

        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(int(min_v / step))
        slider.setMaximum(int(max_v / step))
        slider.setValue(int(default_val / step))
        row.addWidget(slider, 1)

        value_label = QLabel(f"{default_val:.2f}")
        value_label.setMinimumWidth(40)
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(value_label)

        hint_label = QLabel(hint)
        hint_label.setStyleSheet("color: #999; font-size: 11px;")
        hint_label.setMinimumWidth(160)
        row.addWidget(hint_label)

        slider.valueChanged.connect(
            lambda v, vl=value_label, s=step: vl.setText(f"{v * s:.2f}"))
        parent_layout.addLayout(row)
        return slider


    def _make_compact_slider(self, layout, name, default_val, min_v, max_v, step):
        row = QHBoxLayout()
        row.setSpacing(4)
        label = QLabel(f"{name}:")
        label.setStyleSheet("font-size: 11px; color: #555;")
        row.addWidget(label)
        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(int(min_v / step))
        slider.setMaximum(int(max_v / step))
        slider.setValue(int(default_val / step))
        slider.setFixedWidth(120)
        row.addWidget(slider, 0)
        value_label = QLabel(f"{default_val:.2f}")
        value_label.setFixedWidth(36)
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        value_label.setStyleSheet("font-size: 11px;")
        row.addWidget(value_label, 0)
        row.addStretch()
        slider.valueChanged.connect(
            lambda v, vl=value_label, s=step: vl.setText(f"{v * s:.2f}"))
        layout.addLayout(row)
        return slider

    def _apply_style(self):
        """应用 QSS 样式表（通过 ThemeManager）。"""
        self.start_btn.setObjectName("startBtn")
        theme_mgr = ThemeManager()
        theme_mgr.restore()  # 启动时加载保存的主题（auto则跟随系统）

    # ── 设置持久化 ──────────────────────────────────────────

    def _restore_settings(self):
        """恢复上次保存的设置。"""
        config = self._app_config
        saved_input = config.input_dir
        if saved_input:
            self.input_edit.setText(saved_input)
        saved_output = config.output_dir
        if saved_output:
            self.output_edit.setText(saved_output)

        # 恢复阈值滑块
        self.ear_slider.setValue(int(config.ear_threshold / EAR_SLIDER_RANGE[2]))
        self.over_slider.setValue(int(config.over_threshold / OVER_SLIDER_RANGE[2]))
        self.under_slider.setValue(int(config.under_threshold / UNDER_SLIDER_RANGE[2]))

        # 人脸检测
        face_enabled = config.enable_face_detection
        self.face_check.setChecked(face_enabled)
        self.ear_slider.setEnabled(face_enabled)
        self.face_mode_combo.setEnabled(face_enabled)
        self.expression_check.setEnabled(face_enabled)
        self.red_eye_check.setEnabled(face_enabled)

        # 合照模式
        fm_idx = self.face_mode_combo.findData(config.face_mode)
        if fm_idx >= 0:
            self.face_mode_combo.setCurrentIndex(fm_idx)

        # 表情/红眼依赖人脸检测：人脸关闭时强制子项关闭（v5.1 修复恢复状态失真，
        # 避免出现"开关显示 ON 但实际不生效"）
        expr_enabled = config.enable_expression and face_enabled
        re_enabled = config.enable_red_eye and face_enabled

        # 表情
        self.expression_check.setChecked(expr_enabled)
        expr_slider_val = int(config.expression_smile_threshold / EXPRESSION_SMILE_SLIDER_RANGE[2])
        self.expression_slider.setValue(max(0, min(12, expr_slider_val)))
        self.expression_slider.setEnabled(expr_enabled)

        # 红眼
        self.red_eye_check.setChecked(re_enabled)
        re_slider_val = int(config.red_eye_threshold / RED_EYE_SLIDER_RANGE[2])
        self.red_eye_slider.setValue(max(2, min(25, re_slider_val)))
        self.red_eye_slider.setEnabled(re_enabled)

        # 构图水平
        self.level_check.setChecked(config.enable_level)
        saved_method = config.level_method
        idx = self.level_method_combo.findData(saved_method)
        if idx >= 0:
            self.level_method_combo.setCurrentIndex(idx)
        # 先按方法设置滑块量程，再恢复数值（v5.1 修复 general 方法量程错乱）
        self._apply_level_slider_range(saved_method)
        saved_angle = config.level_angle_tolerance
        slider_val = int(round(saved_angle / 0.5))
        self.level_angle_slider.setValue(max(
            self.level_angle_slider.minimum(),
            min(self.level_angle_slider.maximum(), slider_val)))
        self._update_level_angle_label()
        self.level_method_combo.setEnabled(config.enable_level)
        self.level_angle_slider.setEnabled(config.enable_level)

        # 模糊
        self.blur_check.setChecked(config.enable_blur)
        self.blur_slider.setValue(max(2, min(40, int(config.blur_threshold / 5))))
        self.blur_slider.setEnabled(config.enable_blur)

        # 重复照片
        self.duplicate_check.setChecked(config.enable_duplicate)
        if hasattr(self, "duplicate_hamming_slider"):
            self.duplicate_hamming_slider.setValue(
                max(1, min(15, int(config.duplicate_hamming))))
            self.duplicate_hamming_label.setText(str(self.duplicate_hamming_slider.value()))

        self.copy_check.setChecked(config.copy_mode)

        # 恢复窗口几何
        geo = config.window_geometry
        if geo:
            self.restoreGeometry(geo)
        state = config.window_state
        if state:
            self.restoreState(state)

    def _save_settings(self):
        """保存当前设置到 QSettings。"""
        config = self._app_config
        config.input_dir = self.input_edit.text().strip()
        config.output_dir = self.output_edit.text().strip()
        config.ear_threshold = self.ear_slider.value() * EAR_SLIDER_RANGE[2]
        config.over_threshold = self.over_slider.value() * OVER_SLIDER_RANGE[2]
        config.under_threshold = self.under_slider.value() * UNDER_SLIDER_RANGE[2]
        config.enable_face_detection = self.face_check.isChecked()
        config.face_mode = self.face_mode_combo.currentData() or FACE_MODE_BEST
        config.enable_expression = self.expression_check.isChecked()
        config.expression_smile_threshold = float(self.expression_slider.value() * 0.05)
        config.enable_red_eye = self.red_eye_check.isChecked()
        config.red_eye_threshold = float(self.red_eye_slider.value() * 0.01)
        config.enable_blur = self.blur_check.isChecked()
        config.blur_threshold = float(self.blur_slider.value() * 5)
        config.enable_duplicate = self.duplicate_check.isChecked()  # v5.1: 补持久化
        if hasattr(self, "duplicate_hamming_slider"):
            config.duplicate_hamming = self.duplicate_hamming_slider.value()  # v5.1: 敏感度持久化
        config.enable_level = self.level_check.isChecked()
        config.level_method = self.level_method_combo.currentData() or "horizon"
        config.level_angle_tolerance = self.level_angle_slider.value() * 0.5
        config.copy_mode = self.copy_check.isChecked()
        config.window_geometry = self.saveGeometry()
        config.window_state = self.saveState()

    def closeEvent(self, event):
        """窗口关闭时保存设置。分析中弹出确认。"""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "确认退出",
                "照片分析正在进行中，确定要退出吗？\n\n退出后当前分析将被中断。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.No:
                event.ignore()
                return
            self._stop_analysis()
            # 等待工作线程退出（用户已确认退出，此处阻塞可接受）
            if self.worker:
                self.worker.wait(10000)
                if self.worker.isRunning():
                    self.worker.terminate_and_cleanup()
        self._save_settings()
        super().closeEvent(event)

    # ── 拖拽支持 ──────────────────────────────────────────

    def dragEnterEvent(self, event):
        """拖拽进入窗口。"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """处理拖放 — 自动填充文件夹路径。"""
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_dir():
                self.input_edit.setText(path)

    # ── 槽函数 ──────────────────────────────────────────────

    def _browse_input(self):
        folder = QFileDialog.getExistingDirectory(self, "选择照片文件夹")
        if folder:
            self.input_edit.setText(folder)

    def _browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
        if folder:
            self.output_edit.setText(folder)

    def _get_current_config(self) -> DetectionConfig:
        """从当前 UI 状态构建检测配置。"""
        step_ear = EAR_SLIDER_RANGE[2]
        step_over = OVER_SLIDER_RANGE[2]
        step_under = UNDER_SLIDER_RANGE[2]
        return DetectionConfig(
            ear_threshold=self.ear_slider.value() * step_ear,
            over_threshold=self.over_slider.value() * step_over,
            under_threshold=self.under_slider.value() * step_under,
            enable_face_detection=self.face_check.isChecked(),
            face_mode=self.face_mode_combo.currentData() or FACE_MODE_BEST,
            enable_expression=self.expression_check.isChecked(),
            expression_smile_threshold=float(self.expression_slider.value() * 0.05),
            enable_red_eye=self.red_eye_check.isChecked(),
            red_eye_threshold=float(self.red_eye_slider.value() * 0.01),
            enable_level=self.level_check.isChecked(),
            level_method=self.level_method_combo.currentData(),
            level_angle_tolerance=self.level_angle_slider.value() * 0.5,
            blur_threshold=float(self.blur_slider.value() * 5),
            prefer_raw=self._app_config.prefer_raw,
            enable_blur=self.blur_check.isChecked(),
            enable_duplicate=self.duplicate_check.isChecked(),
            duplicate_hamming=self.duplicate_hamming_slider.value(),  # v5.1: 敏感度生效
        )

    # ── 检测选项辅助槽 ────────────────────────────────────────

    def _on_face_toggled(self, checked: bool):
        """人脸检测开关切换时启用/禁用睁眼滑块、合照模式、表情开关。"""
        self.ear_slider.setEnabled(checked)
        self.face_mode_combo.setEnabled(checked)
        # 关闭人脸检测时，同时禁用表情和红眼（它们依赖人脸）
        if not checked:
            self.expression_check.setChecked(False)
            self.expression_slider.setEnabled(False)
            self.red_eye_check.setChecked(False)
            self.red_eye_slider.setEnabled(False)
        # 表情和红眼开关随人脸检测状态
        self.expression_check.setEnabled(checked)
        self.red_eye_check.setEnabled(checked)

    def _on_blur_toggled(self, checked: bool):
        """模糊检测开关切换时启用/禁用宽容度滑块。"""
        self.blur_slider.setEnabled(checked)

    def _on_expression_toggled(self, checked: bool):
        """表情检测开关切换时启用/禁用笑容阈值滑块。"""
        self.expression_slider.setEnabled(checked)

    def _on_red_eye_toggled(self, checked: bool):
        """红眼检测开关切换时启用/禁用阈值滑块。"""
        self.red_eye_slider.setEnabled(checked)


    def _toggle_advanced(self):
        """展开/收起高级选项。"""
        visible = not self.advanced_widget.isVisible()
        self.advanced_widget.setVisible(visible)
        self.adv_toggle_btn.setText("▾ 阈值调整" if visible else "▸ 阈值调整")

    def _on_level_toggled(self, checked: bool):
        """构图检测开关切换时启用/禁用子控件。"""
        self.level_method_combo.setEnabled(checked)
        self.level_angle_slider.setEnabled(checked)

    def _on_level_angle_changed(self, value: int):
        """构图严格度滑块变化时更新标签。"""
        self._update_level_angle_label()

    def _apply_level_slider_range(self, method: str):
        """
        按构图方法设置滑块量程。滑块值 ×0.5 = 角度（与保存/恢复一致）。
        v5.1 修复：此前 general 方法显示 9.0° 实际用 4.5°（量程/默认值错位）。
        """
        if method == "general":
            # 通用检测：4°~20°，步长 0.5°，默认 9°
            self.level_angle_slider.setMinimum(8)    # 4°
            self.level_angle_slider.setMaximum(40)   # 20°
            self.level_angle_slider.setValue(18)     # 9°
        else:
            # 地平线检测：2°~12°，步长 0.5°，默认 5°
            self.level_angle_slider.setMinimum(4)    # 2°
            self.level_angle_slider.setMaximum(24)   # 12°
            self.level_angle_slider.setValue(10)     # 5°

    def _update_level_angle_label(self):
        """刷新构图角度标签。"""
        self.level_angle_label.setText(f"{self.level_angle_slider.value() * 0.5:.1f}°")

    def _on_level_method_changed(self, index: int):
        """构图方法切换时更新滑块范围和默认值。"""
        method = self.level_method_combo.currentData() or "horizon"
        self._apply_level_slider_range(method)
        self._update_level_angle_label()

    def _start_analysis(self):
        input_dir = self.input_edit.text().strip()
        if not input_dir:
            QMessageBox.warning(self, "提示", "请先选择照片文件夹。")
            return
        input_path = Path(input_dir)
        if not input_path.is_dir():
            QMessageBox.warning(self, "提示", f"文件夹不存在:\n{input_dir}")
            return

        photo_paths = sorted([
            p for p in input_path.iterdir()
            if p.suffix.lower() in ALL_SUPPORTED_EXTENSIONS and p.is_file()
        ])
        if not photo_paths:
            QMessageBox.information(self, "提示", "该文件夹中没有找到照片文件。")
            return

        config = self._get_current_config()
        output_dir = self.output_edit.text().strip() or None

        self.table.setRowCount(0)
        self.results_data = []
        self.summary_widget.setVisible(False)
        self._path_map = {p.name: str(p) for p in photo_paths}
        self.progress_bar.setMaximum(len(photo_paths) + (1 if config.enable_duplicate else 0))
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.preview_label.setVisible(False)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("正在加载 AI 模型...")

        # v5.1: 断开旧 worker 的信号，避免停止后再开始时的竞态（旧结果覆盖新表格）
        if self.worker is not None:
            try:
                self.worker.progress.disconnect()
                self.worker.finished_signal.disconnect()
                self.worker.cancelled_signal.disconnect()
                self.worker.error_signal.disconnect()
                self.worker.status_update.disconnect()
            except (RuntimeError, TypeError):
                pass

        self.worker = ProcessWorker(
            photo_paths, config,
            output_dir=output_dir,
            copy_mode=self.copy_check.isChecked(),
            max_workers=self._app_config.max_workers,  # v5.1: 让"并行线程数"设置真正生效
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.cancelled_signal.connect(self._on_cancelled)
        self.worker.error_signal.connect(self._on_error)
        self.worker.status_update.connect(self.status_label.setText)
        self.worker.start()

    def _stop_analysis(self):
        """请求停止分析（v5.1: 不阻塞主线程，由 cancelled_signal 收尾）。"""
        if self.worker and self.worker.isRunning():
            self.status_label.setText("正在停止...")
            self.stop_btn.setEnabled(False)
            self.worker.stop()
            # 不再同步 wait(3000) —— 优雅停止完成后由 _on_cancelled 恢复界面

    def _on_progress(self, index, filename, passed, reason):
        """处理进度更新。"""
        self.progress_bar.setValue(index)
        self.status_label.setText(f"分析中: {filename}" if filename else reason)

        # v5.1: 重复检测完成等非照片事件不插入表格空行
        if not filename:
            return

        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setRowHeight(row, 28)

        # 彩色圆点替代 OK/NG
        status_item = QTableWidgetItem("●" if passed else "●")
        status_item.setTextAlignment(Qt.AlignCenter)
        status_item.setForeground(QColor("#2e7d32") if passed else QColor("#e53935"))
        fnt = QFont()
        fnt.setPointSize(16)
        status_item.setFont(fnt)
        file_path = self._path_map.get(filename, "")
        status_item.setData(Qt.UserRole, file_path)
        self.table.setItem(row, 0, status_item)
        self.table.setItem(row, 1, QTableWidgetItem(filename))

        result_item = QTableWidgetItem("通过" if passed else "不合格")
        result_item.setForeground(QColor("#2e7d32") if passed else QColor("#e53935"))
        bf = QFont()
        bf.setBold(True)
        result_item.setFont(bf)
        self.table.setItem(row, 2, result_item)
        self.table.setItem(row, 3, QTableWidgetItem(reason))
        self.table.scrollToBottom()

        # 实时预览（v5.1: 后台线程解码，RAW 走内嵌 JPEG 快路径，不卡 UI）
        if file_path:
            self._request_preview(file_path, 220)

    def _request_preview(self, photo_path: str, size: int = 220):
        """异步请求缩略图预览，防止过期请求覆盖当前预览。"""
        from pathlib import Path
        pp = Path(photo_path)
        if not pp.exists():
            return
        self._preview_path = str(pp)
        self._preview_mgr.request_preview(
            str(pp), size,
            on_loaded=lambda path, img: self._show_preview(path, img),
            on_failed=lambda path: None,
        )

    def _show_preview(self, photo_path: str, img):
        """显示预览图（主线程，来自后台加载）。"""
        if photo_path != self._preview_path:
            return  # 过期请求，丢弃
        from PySide6.QtGui import QPixmap
        pix = QPixmap.fromImage(img)
        if not pix.isNull():
            self.preview_label.setPixmap(pix.scaled(
                220, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.preview_label.setVisible(True)

    def _on_finished(self, results):
        """分析完成（仅在未取消时触发）。"""
        self.results_data = results
        self.progress_bar.setVisible(False)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("分析完成")

        # v5.1: move（移动）模式后，表格行路径更新到新位置，预览不再"文件不存在"
        path_by_name = {r.path.name: str(r.path) for r in results}
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 1)
            status_item = self.table.item(row, 0)
            if name_item and status_item:
                name = name_item.text()
                if name in path_by_name:
                    status_item.setData(Qt.UserRole, path_by_name[name])

        # 回刷表格：更新被标记为重复的行
        dup_count = 0
        path_to_row = {}
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                path_to_row[item.data(Qt.UserRole)] = row
        for r in results:
            if r.is_duplicate_of and str(r.path) in path_to_row:
                row = path_to_row[str(r.path)]
                self.table.item(row, 0).setText("●")
                self.table.item(row, 0).setForeground(QColor("#e65100"))
                self.table.item(row, 2).setText("重复")
                self.table.item(row, 2).setForeground(QColor("#e65100"))
                self.table.item(row, 3).setText(f"重复 → {r.is_duplicate_of.name}")
                dup_count += 1

        self.preview_label.setText("← 单击照片预览")
        self.preview_label.setVisible(True)
        self._update_summary()
        if dup_count > 0:
            self.status_label.setText(f"分析完成  |  发现 {dup_count} 张重复照片")

        # 彩蛋：根据合格率弹出魏老师评语（有人脸检测时触发更有意义）
        if results and any(r.face_detected for r in results):
            passed = [r for r in results if r.all_pass]
            rate = len(passed) / len(results) * 100 if results else 0
            if rate < 30:
                QMessageBox.information(
                    self, "魏老师点评", "你这拍的有什么意义呢？——魏老师")
            elif rate > 80:
                QMessageBox.information(
                    self, "魏老师点评", "哇！代表作！——魏老师")

    def _on_cancelled(self):
        """用户主动停止分析（v5.1: 与"完成"分开，不弹评语、不输出）。"""
        self.progress_bar.setVisible(False)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("已停止")
        self._update_summary()

    def _on_error(self, error_msg):
        """处理错误。"""
        self.progress_bar.setVisible(False)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("发生错误")
        QMessageBox.critical(self, "错误", f"处理过程中发生错误:\n\n{error_msg}")

    def _update_summary(self):
        """更新底部汇总卡片。"""
        if not self.results_data:
            self.summary_widget.setVisible(False)
            return
        passed = [r for r in self.results_data if r.all_pass]
        failed = [r for r in self.results_data if not r.all_pass]
        dups = [r for r in self.results_data if r.is_duplicate_of]

        self.summary_cards["pass"].setText(str(len(passed)))
        self.summary_cards["fail"].setText(str(len(failed)))
        self.summary_cards["duplicate"].setText(str(len(dups)))
        self.summary_widget.setVisible(True)

    def _on_cell_clicked(self, row, col):
        """单击表格行 — 在右侧预览面板显示照片（v5.1: 异步加载不卡 UI）。"""
        item = self.table.item(row, 0)
        if item is None:
            return
        photo_path = item.data(Qt.UserRole)
        if not photo_path:
            return
        self._request_preview(photo_path, 240)

    def _on_cell_double_clicked(self, row, col):
        """双击表格行 — 用系统默认程序打开原图。"""
        item = self.table.item(row, 0)
        if item is None:
            return
        photo_path = item.data(Qt.UserRole)
        if photo_path:
            from pathlib import Path
            if Path(photo_path).exists():
                import os
                os.startfile(str(photo_path))

    def _open_settings(self):
        """打开设置对话框。"""
        from gui.dialogs.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self)
        dlg.exec()
