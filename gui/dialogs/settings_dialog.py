"""
设置对话框 — 管理应用偏好 + 关于信息。
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QScrollArea,
    QPushButton, QLabel, QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox,
    QDialogButtonBox, QTextBrowser, QComboBox, QFrame, QWidget,
)
from PySide6.QtCore import Qt

from utils.config import AppConfig
from utils.constants import DEFAULT_MAX_WORKERS
from gui.theme_manager import ThemeManager, THEME_LABELS, THEME_AUTO, THEME_LIGHT, THEME_DARK
from gui.widgets.chevron_combo import ChevronComboBox


class SettingsDialog(QDialog):
    """应用设置对话框。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(420)
        self.resize(470, 660)   # v5.3: 固定合理高度，内容超高时走滚动
        self._config = AppConfig()
        self._theme_mgr = ThemeManager()
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        # v5.3: 内容放入滚动区（设置项太多，小屏/高分屏显示不全），按钮固定底部
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 10)
        outer.setSpacing(10)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setObjectName("settingsScroll")

        _content = QWidget()
        _content.setObjectName("settingsScrollContent")
        layout = QVBoxLayout(_content)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(12)

        # ── 外观 ──
        appearance_group = QGroupBox("外观")
        appearance_form = QFormLayout(appearance_group)

        self.theme_combo = ChevronComboBox()
        for key in [THEME_AUTO, THEME_LIGHT, THEME_DARK]:
            self.theme_combo.addItem(THEME_LABELS[key], key)
        appearance_form.addRow("主题:", self.theme_combo)

        layout.addWidget(appearance_group)

        # ── 性能 ──
        perf_group = QGroupBox("性能")
        perf_form = QFormLayout(perf_group)

        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, 8)
        self.workers_spin.setToolTip("并行处理线程数（越大越快，但占用更多内存）")
        perf_form.addRow("并行线程数:", self.workers_spin)

        layout.addWidget(perf_group)

        # ── 检测阈值（v5.2: 不常用选项从主界面移入设置）──
        thresh_group = QGroupBox("检测阈值")
        thresh_form = QFormLayout(thresh_group)

        self.ear_spin = QDoubleSpinBox()
        self.ear_spin.setRange(0.15, 0.25)
        self.ear_spin.setSingleStep(0.01)
        self.ear_spin.setDecimals(2)
        self.ear_spin.setToolTip("睁眼灵敏度（EAR 阈值），越小越宽松")
        thresh_form.addRow("睁眼灵敏度:", self.ear_spin)

        self.over_spin = QDoubleSpinBox()
        self.over_spin.setRange(0.20, 0.80)
        self.over_spin.setSingleStep(0.05)
        self.over_spin.setDecimals(2)
        self.over_spin.setToolTip("过曝像素占比容忍度，越小越严格")
        thresh_form.addRow("过曝容忍度:", self.over_spin)

        self.under_spin = QDoubleSpinBox()
        self.under_spin.setRange(0.20, 0.80)
        self.under_spin.setSingleStep(0.05)
        self.under_spin.setDecimals(2)
        self.under_spin.setToolTip("欠曝像素占比容忍度，越小越严格")
        thresh_form.addRow("欠曝容忍度:", self.under_spin)

        self.smile_spin = QDoubleSpinBox()
        self.smile_spin.setRange(0.0, 0.60)
        self.smile_spin.setSingleStep(0.05)
        self.smile_spin.setDecimals(2)
        self.smile_spin.setToolTip("表情检测笑容阈值，越低越宽容")
        thresh_form.addRow("笑容阈值:", self.smile_spin)

        self.red_eye_spin = QDoubleSpinBox()
        self.red_eye_spin.setRange(0.02, 0.25)
        self.red_eye_spin.setSingleStep(0.01)
        self.red_eye_spin.setDecimals(2)
        self.red_eye_spin.setToolTip("红眼检测红色像素占比阈值，越小越严格")
        thresh_form.addRow("红眼阈值:", self.red_eye_spin)

        self.blur_spin = QDoubleSpinBox()
        self.blur_spin.setRange(10, 200)
        self.blur_spin.setSingleStep(5)
        self.blur_spin.setDecimals(0)
        self.blur_spin.setSuffix("")
        self.blur_spin.setToolTip("模糊检测宽容度，越小越严格")
        thresh_form.addRow("模糊宽容度:", self.blur_spin)

        self.dup_spin = QSpinBox()
        self.dup_spin.setRange(1, 15)
        self.dup_spin.setToolTip("重复检测汉明距离阈值，越小越严格（只找几乎相同的）")
        thresh_form.addRow("重复敏感度:", self.dup_spin)

        self.level_method_combo = ChevronComboBox()
        self.level_method_combo.addItem("地平线检测（推荐）", "horizon")
        self.level_method_combo.addItem("通用检测", "general")
        thresh_form.addRow("构图方法:", self.level_method_combo)

        self.level_angle_spin = QDoubleSpinBox()
        self.level_angle_spin.setRange(2.0, 20.0)
        self.level_angle_spin.setSingleStep(0.5)
        self.level_angle_spin.setDecimals(1)
        self.level_angle_spin.setSuffix("°")
        self.level_angle_spin.setToolTip("构图允许倾斜角度，越小越严格")
        thresh_form.addRow("构图严格度:", self.level_angle_spin)

        layout.addWidget(thresh_group)

        # ── 人脸检测子项（v5.3 独立开关）──
        face_group = QGroupBox("人脸检测")
        face_form = QFormLayout(face_group)

        self.eyes_check = QCheckBox("睁眼检测")
        self.eyes_check.setToolTip("基于 EAR 算法判断眼睛是否睁开（关眼/眯眼筛选）")
        face_form.addRow(self.eyes_check)

        self.skin_check = QCheckBox("肤色检测")
        self.skin_check.setToolTip("L*a*b* 色彩空间判断面部肤色是否自然")
        face_form.addRow(self.skin_check)

        self.clarity_check = QCheckBox("人脸清晰度")
        self.clarity_check.setToolTip("专注人脸区域的局部锐度评估")
        face_form.addRow(self.clarity_check)

        self.expression_check = QCheckBox("表情/笑容")
        self.expression_check.setToolTip("MediaPipe Blendshapes 检测笑容度、张嘴、表情僵硬")
        face_form.addRow(self.expression_check)

        self.red_eye_check = QCheckBox("红眼检测")
        self.red_eye_check.setToolTip("HSV 瞳孔区域分析，识别闪光灯红眼")
        face_form.addRow(self.red_eye_check)

        self.yunet_check = QCheckBox("YuNet 双引擎补检")
        self.yunet_check.setToolTip("OpenCV YuNet 检出 MediaPipe 漏掉的小脸/侧脸/暗光人脸（需 face_detection_yunet_2023mar.onnx 模型文件）")
        face_form.addRow(self.yunet_check)

        layout.addWidget(face_group)

        # ── 默认行为 ──
        behavior_group = QGroupBox("默认行为")
        behavior_form = QFormLayout(behavior_group)

        self.copy_check = QCheckBox("默认复制（而非移动）合格照片")
        behavior_form.addRow(self.copy_check)

        self.raw_check = QCheckBox("重复时优先保留 RAW（NEF/CR2等），标记 JPG")
        self.raw_check.setToolTip("开启后，同一张照片的RAW和JPG版本中保留RAW原始文件")
        behavior_form.addRow(self.raw_check)

        layout.addWidget(behavior_group)

        # ── 关于本软件 ──
        about_group = QGroupBox("关于本软件")
        about_layout = QVBoxLayout(about_group)

        about_text = QTextBrowser()
        about_text.setOpenExternalLinks(True)
        about_text.setHtml("""
            <p><b>照片自动筛选工具 v5.3</b></p>
            <p>自动筛选照片：曝光 + 肤色 + 睁眼 + 构图 + 模糊 + 重复 + 表情 + 红眼</p>
            <p>作者：<b>HZH</b> &nbsp;|&nbsp;
               <a href="https://github.com/hzh3348-sys/photo-filter">GitHub</a></p>
            <hr>

            <p style="font-size:13px; font-weight:bold; color:#16a34a;">v5.3 UI 精细度与性能</p>
            <p style="font-size:12px; line-height:1.6;">
            <span style="font-weight:bold; color:#16a34a;">+</span> <b>圆角对齐与动画</b> — 统一圆角 token、侧边栏/进度/统计/预览动画<br>
            <span style="font-weight:bold; color:#16a34a;">+</span> <b>预览提速</b> — JPEG/PNG 降采样解码 + 低清先显/高清后替换<br>
            <span style="font-weight:bold; color:#16a34a;">+</span> <b>细节修复</b> — 下拉弹出框圆角、开关动画续帧、侧边栏掉帧优化<br>
            <span style="font-weight:bold; color:#16a34a;">+</span> <b>设置可滚动</b> — 设置项超高时滚动显示，按钮固定底部<br>
            </p>

            <p style="font-size:13px; font-weight:bold; color:#6366f1;">v5.2 界面重构</p>
            <p style="font-size:12px; line-height:1.6;">
            <span style="font-weight:bold; color:#6366f1;">+</span> <b>现代简洁界面</b> — 顶部栏 + 左侧控制面板 + 右侧结果区<br>
            <span style="font-weight:bold; color:#6366f1;">+</span> <b>全新双主题</b> — 浅色/深色，一键切换，卡片圆角设计<br>
            <span style="font-weight:bold; color:#6366f1;">+</span> <b>交互细节</b> — 检测项开关行布局、预览卡片、统计卡片<br>
            </p>

            <p style="font-size:13px; font-weight:bold; color:#2e7d32;">v5.1 优化修复</p>
            <p style="font-size:12px; line-height:1.6;">
            <span style="font-weight:bold; color:#2e7d32;">+</span> <b>修复肤色单位错配</b> — 自然肤色不再被误判<br>
            <span style="font-weight:bold; color:#2e7d32;">+</span> <b>重复检测完善</b> — RAW 优先生效、敏感度可调、并行提速<br>
            <span style="font-weight:bold; color:#2e7d32;">+</span> <b>红眼/地平线增强</b> — 瞳孔聚焦 + 连通域过滤、单线地平线检出<br>
            <span style="font-weight:bold; color:#2e7d32;">+</span> <b>性能优化</b> — 肤色 LAB 单次转换、异步预览、默认 4 线程<br>
            <span style="font-weight:bold; color:#2e7d32;">+</span> <b>界面修复</b> — 停止不再误弹评语、欢迎窗只弹一次、构图滑块量程修正<br>
            </p>

            <p style="font-size:13px; font-weight:bold; color:#3949ab;">v5.0 全新升级</p>
            <p style="font-size:12px; line-height:1.6;">
            <span style="font-weight:bold; color:#2e7d32;">+</span> <b>合照模式</b> — 最优人脸 / 所有人脸双模式，会议合照每张脸都需过关<br>
            <span style="font-weight:bold; color:#2e7d32;">+</span> <b>笑容/表情检测</b> — MediaPipe Blendshapes 52 种表情分析，筛选最佳笑容<br>
            <span style="font-weight:bold; color:#2e7d32;">+</span> <b>红眼检测</b> — HSV 瞳孔区域分析，自动识别闪光灯红眼<br>
            <span style="font-weight:bold; color:#2e7d32;">+</span> <b>曝光检测重构</b> — 与人脸完全解耦，极简像素统计，只拦极端情况<br>
            <span style="font-weight:bold; color:#2e7d32;">+</span> <b>肤色检测升级</b> — 全脸区域采样替代逐点采样，抗关键点定位误差<br>
            <span style="font-weight:bold; color:#2e7d32;">+</span> <b>单击预览</b> — 结果列表单击即时预览照片，双击打开原图<br>
            <span style="font-weight:bold; color:#2e7d32;">+</span> <b>界面 3 列重构</b> — 新增表情/红眼控件，检测选项更丰富<br>
            <span style="font-weight:bold; color:#2e7d32;">+</span> <b>重复检测完善</b> — 同名 RAW+JPG 共存、进度条集成、列表回刷<br>
            <span style="font-weight:bold; color:#2e7d32;">+</span> <b>退出确认</b> — 分析中关闭弹窗提示<br>
            </p>

            <p style="font-size:11px; color:#999; line-height:1.5;">
            <b>v3.0 基础：</b>
            多区域模糊检测 · dHash 重复检测 · 地平线检测 · 多线程并行 · 设置持久化 · 拖拽导入 · 双击预览 · 彩蛋评语 · 模块化架构<br>
            <b>v2.0 原始：</b>
            曝光检测 · 肤色检测 (EAR) · 睁眼检测 · 构图检测 · MediaPipe FaceLandmarker · 跨平台 · CI 自动构建
            </p>
        """)
        # v5.3: 设置已放入滚动区，关于区高度收敛，避免过长
        about_text.setMinimumHeight(200)
        about_layout.addWidget(about_text)

        layout.addWidget(about_group)

        layout.addStretch()

        # ── 按钮 ──
        btn_row = QHBoxLayout()

        reset_btn = QPushButton("恢复默认设置")
        reset_btn.clicked.connect(self._reset_defaults)
        btn_row.addWidget(reset_btn)

        btn_row.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        btn_row.addWidget(buttons)

        # 内容进滚动区，按钮固定在底部
        self._scroll.setWidget(_content)
        outer.addWidget(self._scroll, 1)
        outer.addLayout(btn_row)

    def _load_settings(self):
        """从配置中加载当前值。"""
        self.workers_spin.setValue(self._config.max_workers)
        self.copy_check.setChecked(self._config.copy_mode)
        self.raw_check.setChecked(self._config.prefer_raw)

        # 人脸检测子项（v5.3）
        self.eyes_check.setChecked(self._config.enable_eyes)
        self.skin_check.setChecked(self._config.enable_skin)
        self.clarity_check.setChecked(self._config.enable_clarity)
        self.expression_check.setChecked(self._config.enable_expression)
        self.red_eye_check.setChecked(self._config.enable_red_eye)
        self.yunet_check.setChecked(self._config.enable_yunet)

        # 检测阈值（v5.2）
        self.ear_spin.setValue(self._config.ear_threshold)
        self.over_spin.setValue(self._config.over_threshold)
        self.under_spin.setValue(self._config.under_threshold)
        self.smile_spin.setValue(self._config.expression_smile_threshold)
        self.red_eye_spin.setValue(self._config.red_eye_threshold)
        self.blur_spin.setValue(self._config.blur_threshold)
        self.dup_spin.setValue(self._config.duplicate_hamming)
        lidx = self.level_method_combo.findData(self._config.level_method)
        if lidx >= 0:
            self.level_method_combo.setCurrentIndex(lidx)
        self.level_angle_spin.setValue(self._config.level_angle_tolerance)

        # 主题
        current_theme = self._config.theme
        idx = self.theme_combo.findData(current_theme)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)

    def _save_and_accept(self):
        """保存设置并关闭。"""
        self._config.max_workers = self.workers_spin.value()
        self._config.copy_mode = self.copy_check.isChecked()
        self._config.prefer_raw = self.raw_check.isChecked()

        # 人脸检测子项（v5.3）
        self._config.enable_eyes = self.eyes_check.isChecked()
        self._config.enable_skin = self.skin_check.isChecked()
        self._config.enable_clarity = self.clarity_check.isChecked()
        self._config.enable_expression = self.expression_check.isChecked()
        self._config.enable_red_eye = self.red_eye_check.isChecked()
        self._config.enable_yunet = self.yunet_check.isChecked()

        # 检测阈值（v5.2）
        self._config.ear_threshold = self.ear_spin.value()
        self._config.over_threshold = self.over_spin.value()
        self._config.under_threshold = self.under_spin.value()
        self._config.expression_smile_threshold = self.smile_spin.value()
        self._config.red_eye_threshold = self.red_eye_spin.value()
        self._config.blur_threshold = self.blur_spin.value()
        self._config.duplicate_hamming = self.dup_spin.value()
        self._config.level_method = self.level_method_combo.currentData() or "horizon"
        self._config.level_angle_tolerance = self.level_angle_spin.value()

        # 主题
        new_theme = self.theme_combo.currentData()
        if new_theme != self._config.theme:
            self._theme_mgr.apply_theme(new_theme)
            # v5.3: 统一走 refresh_theme_appearance（玻璃背景 + 图标 + 空状态重排）
            parent = self.parent()
            if parent is not None:
                fn = getattr(parent, "refresh_theme_appearance", None)
                if callable(fn):
                    try:
                        fn()
                    except Exception:
                        pass

        self.accept()

    def _reset_defaults(self):
        """恢复默认设置。"""
        from utils.constants import (
            DEFAULT_EAR_THRESHOLD, DEFAULT_OVEREXPOSURE_RATIO, DEFAULT_UNDEREXPOSURE_RATIO,
            DEFAULT_EXPRESSION_SMILE_THRESHOLD, DEFAULT_RED_EYE_THRESHOLD,
            DEFAULT_BLUR_THRESHOLD, DEFAULT_DUPLICATE_HAMMING, DEFAULT_HORIZON_ANGLE_TOLERANCE,
        )
        self.workers_spin.setValue(DEFAULT_MAX_WORKERS)
        self.copy_check.setChecked(True)
        self.raw_check.setChecked(True)  # v5.1: 补上 RAW 优先的默认恢复
        self.eyes_check.setChecked(True)
        self.skin_check.setChecked(True)
        self.clarity_check.setChecked(False)
        self.expression_check.setChecked(False)
        self.red_eye_check.setChecked(False)
        self.yunet_check.setChecked(True)

        # 检测阈值恢复默认（v5.2）
        self.ear_spin.setValue(DEFAULT_EAR_THRESHOLD)
        self.over_spin.setValue(DEFAULT_OVEREXPOSURE_RATIO)
        self.under_spin.setValue(DEFAULT_UNDEREXPOSURE_RATIO)
        self.smile_spin.setValue(DEFAULT_EXPRESSION_SMILE_THRESHOLD)
        self.red_eye_spin.setValue(DEFAULT_RED_EYE_THRESHOLD)
        self.blur_spin.setValue(DEFAULT_BLUR_THRESHOLD)
        self.dup_spin.setValue(DEFAULT_DUPLICATE_HAMMING)
        lidx = self.level_method_combo.findData("horizon")
        if lidx >= 0:
            self.level_method_combo.setCurrentIndex(lidx)
        self.level_angle_spin.setValue(DEFAULT_HORIZON_ANGLE_TOLERANCE)

        idx = self.theme_combo.findData(THEME_AUTO)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)
