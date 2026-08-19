"""
欢迎对话框 — 首次启动引导 (v3.5)。
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from utils.config import AppConfig


class WelcomeDialog(QDialog):
    """首次启动欢迎引导对话框。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("欢迎")
        self.setMinimumSize(560, 440)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self._config = AppConfig()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(32, 24, 32, 24)

        # 标题（v5.3.1: 颜色走主题 QSS，深色模式不白）
        title = QLabel("欢迎使用照片自动筛选工具")
        title.setObjectName("welcomeTitle")
        title.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(18)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        # 版本
        version = QLabel("v5.3.1")
        version.setObjectName("welcomeVersion")
        version.setAlignment(Qt.AlignCenter)
        version.setStyleSheet("font-size: 12px;")
        layout.addWidget(version)

        layout.addSpacing(8)

        # 功能卡片
        cards = [
            ("📷", "导入照片", "选择文件夹或拖拽导入\n支持 JPG / PNG / RAW 等格式"),
            ("🔍", "自动分析", "检测曝光、肤色、睁眼\n模糊、倾斜、重复照片"),
            ("📁", "输出结果", "合格照片自动复制/移动\n到指定文件夹"),
        ]

        card_row = QHBoxLayout()
        card_row.setSpacing(12)
        for emoji, title_text, desc in cards:
            card = QFrame()
            # v5.3.1: 颜色全部走主题 QSS（palette(base) 在深色主题下仍是白色，会发白）
            card.setObjectName("welcomeCard")
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(4)
            card_layout.setContentsMargins(10, 10, 10, 10)

            emoji_label = QLabel(emoji)
            emoji_label.setAlignment(Qt.AlignCenter)
            emoji_label.setStyleSheet("font-size: 28px; border: none; background: transparent;")
            card_layout.addWidget(emoji_label)

            card_title = QLabel(title_text)
            card_title.setObjectName("welcomeCardTitle")
            card_title.setAlignment(Qt.AlignCenter)
            card_title.setStyleSheet("font-weight: bold; font-size: 13px; border: none; background: transparent;")
            card_layout.addWidget(card_title)

            card_desc = QLabel(desc)
            card_desc.setObjectName("welcomeCardDesc")
            card_desc.setAlignment(Qt.AlignCenter)
            card_desc.setStyleSheet("font-size: 11px; border: none; background: transparent;")
            card_layout.addWidget(card_desc)

            card_row.addWidget(card)
        layout.addLayout(card_row)

        layout.addSpacing(8)

        # 提示
        tip = QLabel("💡 拖拽文件夹可快速导入  |  ⚙ 右上角设置调整偏好  |  双击结果查看原图")
        tip.setObjectName("welcomeTip")
        tip.setAlignment(Qt.AlignCenter)
        tip.setStyleSheet("font-size: 11px;")
        layout.addWidget(tip)

        layout.addStretch()

        # 不再显示 + 按钮
        bottom_row = QHBoxLayout()
        self.skip_check = QCheckBox("下次不再显示")
        self.skip_check.setObjectName("welcomeSkip")
        self.skip_check.setStyleSheet("font-size: 11px;")
        bottom_row.addWidget(self.skip_check)
        bottom_row.addStretch()

        start_btn = QPushButton("开始使用")
        start_btn.setMinimumHeight(38)
        start_btn.setMinimumWidth(120)
        start_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #5c6bc0, stop:1 #3949ab);
                color: white; border: none; border-radius: 8px;
                font-weight: bold; font-size: 14px; padding: 8px 24px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #6f7dd4, stop:1 #4a59c4);
            }
        """)
        start_btn.clicked.connect(self._on_start)
        bottom_row.addWidget(start_btn)
        layout.addLayout(bottom_row)

    def _on_start(self):
        """开始使用。"""
        # v5.1 修复：无论是否勾选"下次不再显示"，点击开始即标记已引导，
        # 避免欢迎窗每次启动都弹出
        self._config.first_run = False
        self.accept()
