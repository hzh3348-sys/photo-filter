"""
SVG 图标加载 — 主题感知 + 打包兼容 (v5.2)。
图标为单色 SVG（fill="#6b7688" 占位色），按主题替换颜色渲染。
"""

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer


def _icons_dir() -> Path:
    """获取图标目录，兼容 PyInstaller 打包。"""
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS') and sys._MEIPASS:
            return Path(sys._MEIPASS) / "resources" / "icons"
        return Path(sys.executable).parent / "resources" / "icons"
    return Path(__file__).parent.parent / "resources" / "icons"


_ICON_DIR = _icons_dir()

# 主题图标色（浅色深灰 / 深色浅灰，两种主题下均清晰可见）
_THEME_COLORS = {
    "light": "#6b7688",
    "dark": "#aab2c4",
}


def theme_color(dark: bool = False) -> str:
    """主题中性图标色。"""
    return _THEME_COLORS["dark"] if dark else _THEME_COLORS["light"]


def icon(name: str, color: str = None, size: int = 16) -> QIcon:
    """
    加载 SVG 图标（Lucide 线条风格）。
    默认用占位色 #6b7688；传入 color 可替换 stroke/fill 占位色（主题感知）。
    """
    path = _ICON_DIR / f"{name}.svg"
    if not path.exists():
        return QIcon()

    if color is None:
        return QIcon(str(path))

    # 替换占位色后按指定颜色渲染（QIcon 直接加载 SVG 无法动态换色）
    try:
        svg = path.read_text(encoding="utf-8")
        svg = svg.replace('stroke="#6b7688"', f'stroke="{color}"')
        svg = svg.replace('fill="#6b7688"', f'fill="{color}"')
        renderer = QSvgRenderer()
        if not renderer.load(svg.encode("utf-8")):
            return QIcon(str(path))
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        renderer.render(painter)
        painter.end()
        return QIcon(pix)
    except Exception:
        return QIcon(str(path))
