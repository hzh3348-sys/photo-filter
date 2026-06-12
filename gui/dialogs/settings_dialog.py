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

        layout.addWidget(behavior_group)

        # ── 关于本软件 ──
        about_group = QGroupBox("关于本软件")
        about_layout = QVBoxLayout(about_group)

        about_text = QTextBrowser()
        about_text.setOpenExternalLinks(True)
        about_text.setHtml("""
            <p><b>照片自动筛选工具 v3.0</b></p>
            <p>自动筛选照片：曝光 + 肤色 + 睁眼 + 构图 + 模糊 + 重复检测</p>
            <p>作者：<b>HZH</b></p>
            <p>GitHub：
               <a href="https://github.com/hzh3348-sys/photo-filter">
               github.com/hzh3348-sys/photo-filter</a></p>
            <hr>
            <p style="font-weight:bold;">v3.0 更新日志</p>
            <p style="font-size:11px; color:#555;">
            <b>新增功能：</b><br>
            + 模糊检测（多区域最清晰判断法 + 宽容度滑块）<br>
            + 重复照片检测（dHash 感知哈希 + 汉明距离）<br>
            + 人脸清晰度评分<br>
            + 合照多人脸优选（取最佳人脸评估）<br>
            + 深色模式 / 跟随系统主题<br>
            + 人脸检测开关（关闭时仅检曝光，大幅提速）<br>
            <br>
            <b>构图检测升级：</b><br>
            + 新增地平线检测法（只找长水平线，复杂场景不误判）<br>
            + 保留通用检测法作为备选<br>
            + 严格度滑块可调<br>
            <br>
            <b>性能与体验：</b><br>
            + 多线程并行处理（2-4 workers）<br>
            + 设置持久化（自动记忆阈值、目录、窗口布局）<br>
            + 拖拽文件夹导入 + 双击查看原图<br>
            + 退出确认（分析中关闭弹窗提示）<br>
            + 小脸检测优化（降低置信度 + 两轮放大检测）<br>
            + 肤色检测大幅放宽（兼容深色皮肤）<br>
            + 模块化架构重构（core / gui / utils 分层）<br>
            <br>
            <b>v2.0 功能：</b><br>
            + 曝光检测 + 肤色检测 + 睁眼检测 (EAR)<br>
            + 构图水平检测 (Canny + Hough + MAD)<br>
            + MediaPipe FaceLandmarker (468关键点)<br>
            + 跨平台支持 (Windows / macOS)<br>
            + GitHub Actions 自动构建发布
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

        # 主题
        current_theme = self._config.theme
        idx = self.theme_combo.findData(current_theme)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)

    def _save_and_accept(self):
        """保存设置并关闭。"""
        self._config.max_workers = self.workers_spin.value()
        self._config.copy_mode = self.copy_check.isChecked()

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
