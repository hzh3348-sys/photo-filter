"""
主窗口 — 照片自动筛选工具 v5.0 GUI。
从 photo_filter_gui.py 重构拆分。
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QProgressBar,
    QTableWidget, QTableWidgetItem, QFileDialog, QGroupBox,
    QCheckBox, QComboBox, QFrame, QHeaderView, QMessageBox, QSplashScreen,
    QSplitter,
)
from PySide6.QtCore import (
    Qt, Signal, QSize, QEvent,
    QPropertyAnimation, QVariantAnimation, QEasingCurve,
)
from PySide6.QtGui import (
    QFont, QColor, QPixmap, QPainter, QPen, QBrush, QImage, QPainterPath,
)

from core.models import DetectionConfig
from gui.worker import ProcessWorker
from gui.widgets.toggle_switch import ToggleSwitch
from gui.widgets.chevron_combo import ChevronComboBox
from gui.theme_manager import ThemeManager, THEME_LIGHT, THEME_DARK
from gui.preview_loader import PreviewManager
from gui import icons
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
    painter.drawText(0, 170, 400, 20, Qt.AlignCenter, "by HZH  |  v5.3.1")
    painter.end()
    return QSplashScreen(pixmap)


# ── 主窗口 ────────────────────────────────────────────────

class MainWindow(QMainWindow):
    """照片筛选工具主窗口。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("照片自动筛选工具 by HZH  v5.3.1")
        self.setMinimumSize(980, 720)
        self.resize(1080, 800)
        self.results_data = []
        self.worker = None
        self._app_config = AppConfig()
        # 异步缩略图预览（v5.1: 大图/RAW 解码不进主线程）
        self._preview_mgr = PreviewManager(self)
        self._preview_path = ""   # 当前预览对应的路径（防过期覆盖）

        # ── UI 动画状态（v5.3.1 精细度）──
        self._sidebar_width = 320      # 侧边栏展开宽度（折叠动画目标值）
        self._sidebar_anim = None
        self._progress_anim = None
        self._preview_last_size = 0    # 已显示预览的源图宽度（防低清迟到覆盖）
        self._stat_anims = []          # 统计数字滚动动画引用（防 GC）

        self._setup_ui()
        self._apply_style()
        self._restore_settings()

    def _setup_ui(self):
        """构建现代简洁界面（v5.2 重构：玻璃背景 + 顶部栏 + 左侧控制面板 + 右侧结果区）。"""
        central = QWidget()
        self.setCentralWidget(central)
        # 玻璃背景层（最底层，模糊渐变 + 光斑）
        self._bg_label = QLabel(central)
        self._bg_label.setAttribute(Qt.WA_TransparentForMouseEvents)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ══ 顶部栏（半透明玻璃条）══
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(54)
        hrow = QHBoxLayout(header)
        hrow.setContentsMargins(14, 0, 14, 0)
        hrow.setSpacing(8)
        self.sidebar_btn = QPushButton()
        self.sidebar_btn.setFixedSize(34, 34)
        self.sidebar_btn.setToolTip("收起左侧面板")
        self.sidebar_btn.setCursor(Qt.PointingHandCursor)
        self.sidebar_btn.clicked.connect(self._toggle_sidebar)
        hrow.addWidget(self.sidebar_btn)
        title = QLabel("照片自动筛选工具")
        title.setObjectName("appTitle")
        hrow.addWidget(title)
        ver = QLabel("v5.3.1")
        ver.setObjectName("appVersion")
        hrow.addWidget(ver)
        hrow.addStretch()
        self.theme_btn = QPushButton()
        self.theme_btn.setFixedSize(34, 34)
        self.theme_btn.setToolTip("切换深色/浅色主题")
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.clicked.connect(self._toggle_theme)
        hrow.addWidget(self.theme_btn)
        root.addWidget(header)

        # ══ 主体：左控制面板 + 右结果区（QSplitter 可拖拽调宽 + 折叠）══
        body = QSplitter(Qt.Horizontal)
        body.setHandleWidth(6)
        body.setChildrenCollapsible(False)
        body.setObjectName("mainSplitter")
        root.addWidget(body, 1)

        # ── 左侧面板 ──
        left = QWidget()
        left.setMinimumWidth(300)
        left.setMaximumWidth(520)
        self._sidebar_widget = left
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(12)

        # 文件夹卡片
        folder_card, fc = self._make_card("文件夹")
        in_row = QHBoxLayout()
        in_row.setSpacing(6)
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("选择照片文件夹…")
        in_row.addWidget(self.input_edit, 1)
        btn_in = QPushButton("浏览")
        btn_in.setIcon(icons.icon("folder", "#6a7590", 14))
        btn_in.setIconSize(QSize(14, 14))
        btn_in.clicked.connect(self._browse_input)
        in_row.addWidget(btn_in)
        fc.addLayout(in_row)
        out_row = QHBoxLayout()
        out_row.setSpacing(6)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("留空仅分析不输出")
        out_row.addWidget(self.output_edit, 1)
        btn_out = QPushButton("浏览")
        btn_out.setIcon(icons.icon("folder", "#6a7590", 14))
        btn_out.setIconSize(QSize(14, 14))
        btn_out.clicked.connect(self._browse_output)
        out_row.addWidget(btn_out)
        fc.addLayout(out_row)
        self.copy_check = ToggleSwitch("复制照片（否则移动）")
        self.copy_check.setChecked(True)
        fc.addWidget(self.copy_check)
        lv.addWidget(folder_card)

        # 检测项卡片
        detect_card, dc = self._make_card("检测项")

        # 人脸检测 + 合照模式
        self.face_mode_combo = ChevronComboBox()
        self.face_mode_combo.addItem("最优人脸", FACE_MODE_BEST)
        self.face_mode_combo.addItem("所有人脸", FACE_MODE_ALL)
        self.face_mode_combo.setToolTip(
            "最优人脸：生活照模式，取最佳人脸评估\n所有人脸：合照模式，每张脸都必须通过")
        self.face_mode_combo.setMinimumWidth(96)
        # v5.3.1: 自绘下拉框不吃 QSS 字体，改用真实字体
        _combo_font = QFont()
        _combo_font.setPixelSize(11)
        self.face_mode_combo.setFont(_combo_font)
        self.face_check = ToggleSwitch()
        self.face_check.setToolTip("启用人脸检测（睁眼+肤色），关闭后仅检曝光")
        self.face_check.setChecked(True)
        self.face_check.toggled.connect(self._on_face_toggled)
        self._opt_row(dc, "人脸检测", self.face_check, extra=self.face_mode_combo)

        # v5.3.1: 表情/红眼/清晰度/睁眼/肤色等子项已收进「设置 → 人脸检测」独立开关

        # 构图水平
        self.level_check = ToggleSwitch()
        self.level_check.setToolTip("检测照片是否倾斜，支持地平线和通用两种方法")
        self.level_check.toggled.connect(self._on_level_toggled)
        self.level_method_combo = ChevronComboBox()
        self.level_method_combo.addItem("地平线", "horizon")
        self.level_method_combo.addItem("通用", "general")
        self.level_method_combo.setToolTip("地平线检测：只找长水平线判断倾斜 | 通用检测：分析所有线条角度一致性")
        self.level_method_combo.setMinimumWidth(80)
        _combo_font = QFont()
        _combo_font.setPixelSize(11)
        self.level_method_combo.setFont(_combo_font)
        self.level_method_combo.setEnabled(False)
        self.level_method_combo.currentIndexChanged.connect(self._on_level_method_changed)
        self._opt_row(dc, "构图水平", self.level_check, extra=self.level_method_combo)

        # 模糊检测
        self.blur_check = ToggleSwitch()
        self.blur_check.setToolTip("智能检测模糊照片（取最清晰区域判断，浅景深不误判）\n宽容度可在 设置 中调整")
        self.blur_check.toggled.connect(self._on_blur_toggled)
        self._opt_row(dc, "模糊检测", self.blur_check)

        # 重复检测
        self.duplicate_check = ToggleSwitch()
        self.duplicate_check.setToolTip("使用 dHash 感知哈希识别相似/重复照片\n敏感度可在 设置 中调整")
        self._opt_row(dc, "重复检测", self.duplicate_check)

        lv.addWidget(detect_card)

        # 操作卡片
        action_card, ac = self._make_card(None)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.start_btn = QPushButton("开始分析")
        self.start_btn.setIcon(icons.icon("play", "#ffffff", 14))
        self.start_btn.setIconSize(QSize(14, 14))
        self.start_btn.setMinimumHeight(40)
        self.start_btn.clicked.connect(self._start_analysis)
        btn_row.addWidget(self.start_btn, 1)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setIcon(icons.icon("stop", "#e5484d", 14))
        self.stop_btn.setIconSize(QSize(14, 14))
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_analysis)
        btn_row.addWidget(self.stop_btn)
        ac.addLayout(btn_row)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFormat("%p% (%v/%m)")
        self.progress_bar.setVisible(False)
        ac.addWidget(self.progress_bar)
        self.status_label = QLabel("就绪")
        self.status_label.setObjectName("hint")
        ac.addWidget(self.status_label)
        lv.addWidget(action_card)
        lv.addStretch()

        # 设置入口（v5.2: 从顶栏移到左侧边栏底部）
        self.settings_btn = QPushButton("设置")
        self.settings_btn.setObjectName("sidebarBtn")
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setToolTip("应用设置（阈值 / 外观 / 性能 / 行为）")
        self.settings_btn.clicked.connect(self._open_settings)
        lv.addWidget(self.settings_btn)
        body.addWidget(left)

        # ── 右侧面板 ──
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(10)

        # 汇总卡片（分析后显示）
        self.summary_widget = QWidget()
        self.summary_widget.setVisible(False)
        summary_row = QHBoxLayout(self.summary_widget)
        summary_row.setContentsMargins(0, 0, 0, 0)
        summary_row.setSpacing(10)
        self.summary_cards = {}
        for key, label, color in [
            ("pass", "合格", "#16a34a"),
            ("fail", "不合格", "#dc2626"),
            ("duplicate", "重复", "#ea580c"),
        ]:
            card = QFrame()
            card.setObjectName("statCard")
            card.setStyleSheet(
                f"QFrame#statCard {{ background: {color}14; border: 1px solid {color}40;"
                f" border-radius: 12px; }}"
                f"QFrame#statCard:hover {{ border-color: {color}80; }}")
            cl = QVBoxLayout(card)
            cl.setSpacing(2)
            cl.setContentsMargins(14, 10, 14, 10)
            num = QLabel("0")
            num.setStyleSheet(
                f"color: {color}; font-size: 22px; font-weight: 700;"
                " border: none; background: transparent;")
            num.setAlignment(Qt.AlignCenter)
            cl.addWidget(num)
            lbl = QLabel(label)
            lbl.setStyleSheet(
                f"color: {color}; font-size: 11px; border: none; background: transparent;")
            lbl.setAlignment(Qt.AlignCenter)
            cl.addWidget(lbl)
            summary_row.addWidget(card, 1)
            self.summary_cards[key] = num
        rv.addWidget(self.summary_widget)

        # 表格 + 预览
        split_row = QHBoxLayout()
        split_row.setSpacing(12)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["状态", "文件名", "结果", "详情"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 56)   # v5.2: 加宽，避免"状态"两字显示不全
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setVisible(False)
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)

        # 空状态引导（表格无数据时显示）
        self._empty_hint = QLabel(
            "拖入照片文件夹，或点击左侧「浏览」选择目录\n分析结果将实时显示在这里",
            self.table.viewport())
        self._empty_hint.setObjectName("emptyHint")
        self._empty_hint.setAlignment(Qt.AlignCenter)
        self._empty_hint.setWordWrap(True)
        self.table.viewport().installEventFilter(self)

        split_row.addWidget(self.table, 1)

        # 预览卡片
        preview_card, pv = self._make_card("预览")
        preview_card.setFixedWidth(252)
        self.preview_label = QLabel()
        self.preview_label.setObjectName("previewBox")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setText("选择照片查看预览")
        self.preview_label.setVisible(False)
        pv.addWidget(self.preview_label, 1)
        split_row.addWidget(preview_card)

        rv.addLayout(split_row, 1)
        body.addWidget(right)
        body.setSizes([372, 900])  # 初始左/右宽度

    def _toggle_sidebar(self):
        """折叠/展开左侧控制面板（v5.3.1: 宽度平滑动画）。"""
        left = self._sidebar_widget
        try:
            if self._sidebar_anim is None:
                self._sidebar_anim = QPropertyAnimation(left, b"maximumWidth", self)
                self._sidebar_anim.setDuration(170)
                self._sidebar_anim.setEasingCurve(QEasingCurve.InOutCubic)
                self._sidebar_anim.finished.connect(self._on_sidebar_anim_finished)
            anim = self._sidebar_anim
            anim.stop()

            if left.isHidden() or left.width() <= 1:
                # 展开：0 → 记忆宽度
                left.show()
                left.setMinimumWidth(0)
                anim.setStartValue(0)
                anim.setEndValue(self._sidebar_width)
                anim.start()
                self.sidebar_btn.setToolTip("收起左侧面板")
            else:
                # 折叠：当前宽度 → 0
                self._sidebar_width = max(left.width(), 300)
                left.setMinimumWidth(0)
                anim.setStartValue(left.width())
                anim.setEndValue(0)
                anim.start()
                self.sidebar_btn.setToolTip("展开左侧面板")
        except Exception:
            # 动画异常时回退为即时折叠，不阻塞交互
            if left.isHidden():
                left.show()
                self.sidebar_btn.setToolTip("收起左侧面板")
            else:
                left.hide()
                self.sidebar_btn.setToolTip("展开左侧面板")
        self._update_theme_icon()  # 刷新折叠箭头方向

    def _on_sidebar_anim_finished(self):
        """侧边栏动画结束：恢复约束与卡片阴影。"""
        left = self._sidebar_widget
        if left.width() <= 1:
            left.hide()
        left.setMinimumWidth(300)
        left.setMaximumWidth(520)
        self._update_theme_icon()

    # ── 玻璃背景 ──────────────────────────────────────────

    def _apply_glass_background(self):
        """生成深色渐变背景（Harness 风格：干净深色 + 极淡光斑，低饱和度）。

        卡片/顶栏半透明透出该背景，呈现专业克制的层次感。
        低分辨率生成后放大，避免 resize 卡顿。
        """
        try:
            import numpy as np
            import cv2
        except ImportError:
            return
        w, h = self.width(), self.height()
        if w < 60 or h < 60:
            return
        try:
            tm = ThemeManager()
            dark = tm.effective_theme == THEME_DARK

            sw, sh = max(8, w // 8), max(8, h // 8)
            if dark:
                # Harness 风格：近黑深蓝渐变，极淡的冷色光斑
                top = np.array([11, 13, 18], dtype=np.float64)
                bottom = np.array([17, 20, 27], dtype=np.float64)
                spots = [(0.25, 0.3, 0.5, (24, 34, 52)),     # 深蓝
                         (0.75, 0.62, 0.55, (28, 36, 48)),
                         (0.6, 0.1, 0.4, (20, 30, 44))]
                alpha = 0.10
            else:
                # 浅色：干净冷灰白渐变 + 极淡蓝紫光斑
                top = np.array([240, 242, 247], dtype=np.float64)
                bottom = np.array([248, 249, 252], dtype=np.float64)
                spots = [(0.25, 0.3, 0.5, (222, 228, 246)),
                         (0.75, 0.62, 0.55, (232, 226, 246)),
                         (0.6, 0.1, 0.4, (214, 230, 246))]
                alpha = 0.25

            grad = np.zeros((sh, sw, 3), dtype=np.float64)
            for y in range(sh):
                t = y / max(1, sh - 1)
                grad[y, :] = top * (1 - t) + bottom * t

            for (cx, cy, r, col) in spots:
                cc = (int(cx * sw), int(cy * sh))
                rr = max(4, int(r * sw))
                overlay = grad.copy()
                cv2.circle(overlay, cc, rr, col, -1)
                grad = cv2.addWeighted(grad, 1.0 - alpha, overlay, alpha, 0)

            grad = np.clip(grad, 0, 255).astype(np.uint8)
            blurred = cv2.GaussianBlur(grad, (0, 0), 18)
            rgb = cv2.cvtColor(blurred, cv2.COLOR_BGR2RGB)
            qimg = QImage(rgb.data, sw, sh, 3 * sw, QImage.Format_RGB888).copy()
            pix = QPixmap.fromImage(qimg).scaled(
                w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            self._bg_label.setPixmap(pix)
            self._bg_label.setGeometry(0, 0, w, h)
            self._bg_label.lower()
        except Exception:
            pass  # 背景失败不影响功能

    def resizeEvent(self, event):
        """窗口大小变化时重绘玻璃背景（低分辨率生成，开销小）。"""
        super().resizeEvent(event)
        if hasattr(self, "_bg_label"):
            self._apply_glass_background()
        self._layout_empty_hint()

    def eventFilter(self, obj, event):
        """表格视口尺寸变化时跟随重排空状态提示。"""
        if obj is self.table.viewport() and event.type() == QEvent.Resize:
            self._layout_empty_hint()
        return super().eventFilter(obj, event)

    def _apply_style(self):
        """应用 QSS 样式表 + 控件 objectName（v5.2 现代主题）。"""
        self.start_btn.setObjectName("primaryBtn")
        self.stop_btn.setObjectName("stopBtn")
        self.settings_btn.setObjectName("sidebarBtn")
        self.theme_btn.setObjectName("iconBtn")
        self.sidebar_btn.setObjectName("iconBtn")
        theme_mgr = ThemeManager()
        theme_mgr.restore()  # 启动时加载保存的主题（auto则跟随系统）
        self._update_theme_icon()

    def _toggle_theme(self):
        """切换浅色/深色主题（v5.3.1: 直接切换，不引入透明度效果，避免界面模糊）。"""
        tm = ThemeManager()
        nxt = THEME_DARK if tm.effective_theme == THEME_LIGHT else THEME_LIGHT
        tm.apply_theme(nxt)
        self.refresh_theme_appearance()

    def refresh_theme_appearance(self):
        """主题已切换后刷新界面外观（设置对话框等外部入口调用）。"""
        self._update_theme_icon()
        self._apply_glass_background()
        self._layout_empty_hint()

    def _update_theme_icon(self):
        """刷新主题/折叠/设置按钮图标（v5.2 矢量图标）。"""
        if not hasattr(self, "theme_btn"):
            return
        tm = ThemeManager()
        dark = tm.effective_theme == THEME_DARK
        c = icons.theme_color(dark)
        self.theme_btn.setIcon(icons.icon("moon" if not dark else "sun", c, 16))
        self.theme_btn.setIconSize(QSize(16, 16))
        self.theme_btn.setText("")
        self.sidebar_btn.setIcon(icons.icon(
            "chevron-right" if self._sidebar_widget.isHidden() else "chevron-left", c, 16))
        self.sidebar_btn.setIconSize(QSize(16, 16))
        self.settings_btn.setIcon(icons.icon("gear", c, 16))
        self.settings_btn.setIconSize(QSize(16, 16))

    def _make_card(self, title: str):
        """创建细边框面板卡片（Harness 风格：纯边框层次），返回 (card, layout)。

        v5.3.1: 不再使用 QGraphicsDropShadowEffect——它投影的是整个卡片渲染结果，
        会把卡片内按钮/开关的文字也描出一层暗影（"字完全是两层"），
        且动画期间重绘昂贵导致侧边栏掉帧。细边框 + 背景色差已足够分层。
        """
        card = QFrame()
        card.setObjectName("card")
        v = QVBoxLayout(card)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(8)
        if title:
            t = QLabel(title)
            t.setObjectName("cardTitle")
            v.addWidget(t)
        return card, v

    def _opt_row(self, layout, name, toggle, extra=None):
        """检测项开关行：名称(左) + 附属控件(中) + 开关(右)。"""
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel(name)
        lbl.setObjectName("optName")
        row.addWidget(lbl)
        row.addStretch()
        if extra is not None:
            row.addWidget(extra)
        row.addWidget(toggle)
        layout.addLayout(row)

    # ── UI 动画与细节辅助（v5.3.1）─────────────────────────────

    def _animate_progress(self, target: int):
        """进度条平滑推进（而非瞬跳）。"""
        if self._progress_anim is None:
            self._progress_anim = QPropertyAnimation(self.progress_bar, b"value", self)
            self._progress_anim.setDuration(220)
            self._progress_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._progress_anim.stop()
        self._progress_anim.setStartValue(self.progress_bar.value())
        self._progress_anim.setEndValue(target)
        self._progress_anim.start()

    def _set_status(self, text: str, state: str = "idle"):
        """状态标签分级着色：idle 灰 / run 蓝 / ok 绿 / err 红。"""
        self.status_label.setText(text)
        self.status_label.setProperty("state", state)
        st = self.status_label.style()
        st.unpolish(self.status_label)
        st.polish(self.status_label)

    def _on_status_update(self, text: str):
        """worker 状态消息 → 自动分级着色。"""
        if "出错" in text or "异常" in text:
            self._set_status(text, "err")
        elif "完成" in text:
            self._set_status(text, "ok")
        elif "停止" in text or "已取消" in text:
            self._set_status(text, "idle")
        else:
            self._set_status(text, "run")

    def _animate_stat(self, label, target: int, duration: int = 500):
        """汇总卡片数字从当前值滚动到目标值。"""
        try:
            start = int(label.text() or 0)
        except ValueError:
            start = 0
        if start == target:
            label.setText(str(target))
            return
        anim = QVariantAnimation(self)
        anim.setDuration(duration)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.setStartValue(start)
        anim.setEndValue(target)
        anim.valueChanged.connect(lambda v: label.setText(str(int(v))))
        anim.finished.connect(lambda: (label.setText(str(target)), anim.deleteLater()))
        self._stat_anims.append(anim)
        anim.start()

    def _clear_stat_anims(self):
        """停止并清理上一次的统计滚动动画。"""
        for a in self._stat_anims:
            try:
                a.stop()
                a.deleteLater()
            except Exception:
                pass
        self._stat_anims = []

    def _rounded_pixmap(self, pix: QPixmap, radius: int = 10) -> QPixmap:
        """把照片裁剪成圆角矩形（与预览卡片圆角对齐）。"""
        if pix.isNull():
            return pix
        out = QPixmap(pix.size())
        out.fill(Qt.transparent)
        p = QPainter(out)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, pix.width(), pix.height(), radius, radius)
        p.setClipPath(path)
        p.drawPixmap(0, 0, pix)
        p.end()
        return out

    def _layout_empty_hint(self):
        """空状态提示铺满表格视口。"""
        if not hasattr(self, "_empty_hint"):
            return
        vp = self.table.viewport()
        self._empty_hint.setGeometry(0, 0, vp.width(), vp.height())
        self._empty_hint.setVisible(self.table.rowCount() == 0)

    def _update_empty_hint(self):
        """按当前行数刷新空状态提示显隐。"""
        if hasattr(self, "_empty_hint"):
            self._empty_hint.setVisible(self.table.rowCount() == 0)

    # ── 设置持久化 ──────────────────────────────────────────

    def _restore_settings(self):
        """恢复上次保存的设置（v5.2: 阈值统一从 QSettings 读取，主界面不再有滑块）。"""
        config = self._app_config
        saved_input = config.input_dir
        if saved_input:
            self.input_edit.setText(saved_input)
        saved_output = config.output_dir
        if saved_output:
            self.output_edit.setText(saved_output)

        # 人脸检测（子项开关在设置中管理）
        face_enabled = config.enable_face_detection
        self.face_check.setChecked(face_enabled)
        self.face_mode_combo.setEnabled(face_enabled)

        # 合照模式
        fm_idx = self.face_mode_combo.findData(config.face_mode)
        if fm_idx >= 0:
            self.face_mode_combo.setCurrentIndex(fm_idx)

        # 构图水平（方法下拉 + 开关）
        self.level_check.setChecked(config.enable_level)
        saved_method = config.level_method
        idx = self.level_method_combo.findData(saved_method)
        if idx >= 0:
            self.level_method_combo.setCurrentIndex(idx)
        self.level_method_combo.setEnabled(config.enable_level)

        # 模糊
        self.blur_check.setChecked(config.enable_blur)

        # 重复照片
        self.duplicate_check.setChecked(config.enable_duplicate)

        self.copy_check.setChecked(config.copy_mode)

        # 恢复窗口几何
        geo = config.window_geometry
        if geo:
            self.restoreGeometry(geo)
        state = config.window_state
        if state:
            self.restoreState(state)

    def _save_settings(self):
        """保存当前设置到 QSettings（v5.2: 阈值由设置对话框管理，这里只存界面项）。"""
        config = self._app_config
        config.input_dir = self.input_edit.text().strip()
        config.output_dir = self.output_edit.text().strip()
        config.enable_face_detection = self.face_check.isChecked()
        config.face_mode = self.face_mode_combo.currentData() or FACE_MODE_BEST
        # v5.3.1: 人脸子项开关由设置对话框管理（enable_expression 等）
        config.enable_blur = self.blur_check.isChecked()
        config.enable_duplicate = self.duplicate_check.isChecked()
        config.enable_level = self.level_check.isChecked()
        config.level_method = self.level_method_combo.currentData() or "horizon"
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
        """从当前 UI 状态 + QSettings 构建检测配置（v5.2: 阈值统一从设置读取）。"""
        config = self._app_config
        return DetectionConfig(
            ear_threshold=config.ear_threshold,
            over_threshold=config.over_threshold,
            under_threshold=config.under_threshold,
            enable_face_detection=self.face_check.isChecked(),
            face_mode=self.face_mode_combo.currentData() or FACE_MODE_BEST,
            enable_eyes=config.enable_eyes,
            enable_skin=config.enable_skin,
            enable_clarity=config.enable_clarity,
            enable_yunet=config.enable_yunet,
            enable_expression=config.enable_expression,
            expression_smile_threshold=config.expression_smile_threshold,
            enable_red_eye=config.enable_red_eye,
            red_eye_threshold=config.red_eye_threshold,
            enable_level=self.level_check.isChecked(),
            level_method=self.level_method_combo.currentData(),
            level_angle_tolerance=config.level_angle_tolerance,
            blur_threshold=config.blur_threshold,
            prefer_raw=config.prefer_raw,
            enable_blur=self.blur_check.isChecked(),
            enable_duplicate=self.duplicate_check.isChecked(),
            duplicate_hamming=config.duplicate_hamming,
        )

    # ── 检测选项辅助槽 ────────────────────────────────────────

    def _on_face_toggled(self, checked: bool):
        """人脸检测开关切换：禁用/启用合照模式（子项开关在设置中）。"""
        self.face_mode_combo.setEnabled(checked)

    def _on_blur_toggled(self, checked: bool):
        """模糊检测开关（v5.2: 阈值在设置中，无需联动控件）。"""
        pass

    def _on_level_toggled(self, checked: bool):
        """构图检测开关切换时启用/禁用方法下拉。"""
        self.level_method_combo.setEnabled(checked)

    def _on_level_method_changed(self, index: int):
        """构图方法切换（v5.2: 严格度在设置中调整，这里只持久化选择）。"""
        if hasattr(self, "level_method_combo"):
            self._app_config.level_method = self.level_method_combo.currentData() or "horizon"

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
        self._update_empty_hint()
        self._path_map = {p.name: str(p) for p in photo_paths}
        self.progress_bar.setMaximum(len(photo_paths) + (1 if config.enable_duplicate else 0))
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        # v5.2: 分析开始即显示预览占位（自动跟随当前完成照片）
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText("分析中… 自动预览当前完成的照片")
        self.preview_label.setVisible(True)
        self._preview_path = ""
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._set_status("正在加载 AI 模型...", "run")

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
        self.worker.status_update.connect(self._on_status_update)
        self.worker.start()

    def _stop_analysis(self):
        """请求停止分析（v5.1: 不阻塞主线程，由 cancelled_signal 收尾）。"""
        if self.worker and self.worker.isRunning():
            self._set_status("正在停止...", "run")
            self.stop_btn.setEnabled(False)
            self.worker.stop()
            # 不再同步 wait(3000) —— 优雅停止完成后由 _on_cancelled 恢复界面

    def _on_progress(self, index, filename, passed, reason):
        """处理进度更新（v5.3.1: 进度平滑推进 + 状态分级）。"""
        self._animate_progress(index)
        self._set_status(f"分析中: {filename}" if filename else reason, "run")

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
        # v5.3.1: 状态/结果单元格加低透明度底色（柔化 pill 效果）
        tint = QColor(46, 125, 50, 24) if passed else QColor(229, 57, 53, 24)
        status_item.setBackground(tint)
        result_item.setBackground(tint)
        self.table.scrollToBottom()
        self._update_empty_hint()

        # 实时预览（v5.1: 后台线程解码，RAW 走内嵌 JPEG 快路径，不卡 UI）
        if file_path:
            self._request_preview(file_path, 220)

    def _request_preview(self, photo_path: str, size: int = 220):
        """异步请求缩略图预览。

        v5.3.1: 两级加载——先请求 96px 低清（DCT 降采样解码，几乎即时），
        再请求目标尺寸高清替换，保证"分析到哪张立即显示哪张"。
        """
        from pathlib import Path
        pp = Path(photo_path)
        if not pp.exists():
            return
        self._preview_path = str(pp)
        self._preview_last_size = 0
        self._preview_mgr.request_preview(
            str(pp), 96,
            on_loaded=lambda path, img: self._show_preview(path, img),
            on_failed=lambda path: None,
        )
        self._preview_mgr.request_preview(
            str(pp), size,
            on_loaded=lambda path, img: self._show_preview(path, img),
            on_failed=lambda path: None,
        )

    def _show_preview(self, photo_path: str, img):
        """显示预览图（主线程，来自后台加载）。"""
        if photo_path != self._preview_path:
            return  # 过期请求，丢弃
        # v5.3.1: 低清迟到回调不覆盖已显示的更高清图
        if img.width() < self._preview_last_size:
            return
        from PySide6.QtGui import QPixmap
        pix = QPixmap.fromImage(img)
        if not pix.isNull():
            # v5.3.1: 圆角遮罩与预览框 QSS(padding 6px / radius 10px) 对齐
            scaled = pix.scaled(216, 288, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview_label.setPixmap(self._rounded_pixmap(scaled, radius=10))
            self.preview_label.setVisible(True)
            self._preview_last_size = img.width()

    def _on_finished(self, results):
        """分析完成（仅在未取消时触发）。"""
        self.results_data = results
        self.progress_bar.setVisible(False)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._set_status("分析完成", "ok")

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
                dup_tint = QColor(230, 81, 0, 26)
                self.table.item(row, 0).setText("●")
                self.table.item(row, 0).setForeground(QColor("#e65100"))
                self.table.item(row, 0).setBackground(dup_tint)
                self.table.item(row, 2).setText("重复")
                self.table.item(row, 2).setForeground(QColor("#e65100"))
                self.table.item(row, 2).setBackground(dup_tint)
                self.table.item(row, 3).setText(f"重复 → {r.is_duplicate_of.name}")
                dup_count += 1

        # v5.2: 分析完成保留最后一张自动预览的照片（不再清成提示文字，
        # 之前 setText 会清除 pixmap，导致必须点击才显示预览）
        if not self._preview_path:
            self.preview_label.setText("选择照片查看预览")
            self.preview_label.setVisible(True)
        self._update_summary(animated=True)
        self._update_empty_hint()
        if dup_count > 0:
            self._set_status(f"分析完成  |  发现 {dup_count} 张重复照片", "ok")

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
        self._set_status("已停止", "idle")
        self._update_summary(animated=True)
        self._update_empty_hint()

    def _on_error(self, error_msg):
        """处理错误。"""
        self.progress_bar.setVisible(False)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._set_status("发生错误", "err")
        QMessageBox.critical(self, "错误", f"处理过程中发生错误:\n\n{error_msg}")

    def _update_summary(self, animated: bool = False):
        """更新底部汇总卡片（v5.3.1: 数字滚动 + 整体淡入）。"""
        if not self.results_data:
            self.summary_widget.setVisible(False)
            return
        passed = [r for r in self.results_data if r.all_pass]
        failed = [r for r in self.results_data if not r.all_pass]
        dups = [r for r in self.results_data if r.is_duplicate_of]

        if animated:
            self._clear_stat_anims()
            self._animate_stat(self.summary_cards["pass"], len(passed))
            self._animate_stat(self.summary_cards["fail"], len(failed))
            self._animate_stat(self.summary_cards["duplicate"], len(dups))
            if not self.summary_widget.isVisible():
                self.summary_widget.setVisible(True)
        else:
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
