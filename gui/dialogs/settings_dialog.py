"""
设置对话框 — 管理应用偏好 + 关于信息。
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QSpinBox, QCheckBox, QGroupBox,
    QDialogButtonBox, QTextBrowser, QComboBox,
)
from PySide6.QtCore import Qt

from utils.config import AppConfig
from utils.constants import DEFAULT_MAX_WORKERS
from gui.theme_manager import ThemeManager, THEME_LABELS, THEME_AUTO, THEME_LIGHT, THEME_DARK


class SettingsDialog(QDialog):
    """应用设置对话框。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(420)
        self._config = AppConfig()
        self._theme_mgr = ThemeManager()
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ── 外观 ──
        appearance_group = QGroupBox("外观")
        appearance_form = QFormLayout(appearance_group)

        self.theme_combo = QComboBox()
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
            <p><b>照片自动筛选工具 v5.0</b></p>
            <p>自动筛选照片：曝光 + 肤色 + 睁眼 + 构图 + 模糊 + 重复 + 表情 + 红眼</p>
            <p>作者：<b>HZH</b> &nbsp;|&nbsp;
               <a href="https://github.com/hzh3348-sys/photo-filter">GitHub</a></p>
            <hr>

            <p style="font-size:13px; font-weight:bold; color:#2e7d32;">v5.0 全新升级</p>
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
        about_text.setMinimumHeight(280)
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

        layout.addLayout(btn_row)

    def _load_settings(self):
        """从配置中加载当前值。"""
        self.workers_spin.setValue(self._config.max_workers)
        self.copy_check.setChecked(self._config.copy_mode)
        self.raw_check.setChecked(self._config.prefer_raw)

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

        # 主题
        new_theme = self.theme_combo.currentData()
        if new_theme != self._config.theme:
            self._theme_mgr.apply_theme(new_theme)

        self.accept()

    def _reset_defaults(self):
        """恢复默认设置。"""
        self.workers_spin.setValue(DEFAULT_MAX_WORKERS)
        self.copy_check.setChecked(True)
        idx = self.theme_combo.findData(THEME_AUTO)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)
