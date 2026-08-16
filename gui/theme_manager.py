"""
主题管理器 — 支持跟随系统、浅色、深色三种模式。
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from utils.config import AppConfig


def _get_themes_dir() -> Path:
    """获取主题文件目录，兼容 PyInstaller 打包和直接运行。"""
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS') and sys._MEIPASS:
            return Path(sys._MEIPASS) / "resources" / "themes"
        else:
            return Path(sys.executable).parent / "resources" / "themes"
    return Path(__file__).parent.parent / "resources" / "themes"


_THEMES_DIR = _get_themes_dir()

# 支持的主题键
THEME_AUTO = "auto"
THEME_LIGHT = "light"
THEME_DARK = "dark"

THEME_LABELS = {
    THEME_AUTO: "跟随系统",
    THEME_LIGHT: "浅色",
    THEME_DARK: "深色",
}


def _detect_system_theme() -> str:
    """检测操作系统当前主题模式。"""
    try:
        app = QApplication.instance()
        if app:
            scheme = app.styleHints().colorScheme()
            if scheme == Qt.ColorScheme.Dark:
                return THEME_DARK
    except (AttributeError, Exception):
        pass
    return THEME_LIGHT


class ThemeManager:
    """主题管理器单例。"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._config = AppConfig()
            cls._instance._current = cls._instance._config.theme
            # 兼容旧配置：如果之前存的不是有效值，默认 auto
            if cls._instance._current not in (THEME_AUTO, THEME_LIGHT, THEME_DARK):
                cls._instance._current = THEME_AUTO
        return cls._instance

    @property
    def current(self) -> str:
        return self._current

    @property
    def effective_theme(self) -> str:
        """实际生效的主题（auto 时返回系统检测结果）。"""
        if self._current == THEME_AUTO:
            return _detect_system_theme()
        return self._current

    @property
    def current_label(self) -> str:
        return THEME_LABELS.get(self._current, self._current)

    def apply_theme(self, name: str):
        """应用指定主题（light/dark），根据 name 或自动检测。"""
        if name not in (THEME_AUTO, THEME_LIGHT, THEME_DARK):
            raise ValueError(f"Unknown theme: {name}")

        self._current = name
        self._config.theme = name
        self._apply_effective()

    def _apply_effective(self):
        """将生效的主题 QSS 应用到 QApplication。"""
        effective = self.effective_theme
        qss_path = _THEMES_DIR / f"{effective}.qss"
        if qss_path.exists():
            with open(qss_path, 'r', encoding='utf-8') as f:
                qss = f.read()
        else:
            qss = ""

        app = QApplication.instance()
        if app:
            app.setStyleSheet(qss)

    def restore(self):
        """启动时恢复保存的主题。
        v5.2: 旧配置（浅色/跟随系统）首次启动切到深色（Harness 开发者工具风格），
        迁移后写入标记，之后尊重用户选择。"""
        cfg = AppConfig()
        if not cfg.theme_migrated_v52:
            self._current = THEME_DARK
            cfg.theme = THEME_DARK
            cfg.theme_migrated_v52 = True
        else:
            saved = cfg.theme
            if saved in (THEME_AUTO, THEME_LIGHT, THEME_DARK):
                self._current = saved
            else:
                self._current = THEME_AUTO
        self._apply_effective()
