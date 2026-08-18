"""
下拉框 — QWidget 自绘 + QMenu 弹出（v5.3 全新实现）。

背景（踩坑记录，勿回退）：
- QComboBox + QSS 在真实 Windows（Qt 6.9）上文本会双绘（"字上下两层"），
  offScreen(Fusion) 不复现，无法在测试中捕获；
- 尝试"自绘文本+覆盖"仍受 QStyleSheetStyle 干扰；
- 彻底方案：不继承 QComboBox。本控件用 QWidget 完全自绘外观
  （圆角背景/边框/单层文本/三角），点击用 QMenu 弹出列表
  （QMenu 为标准菜单渲染，文本单层、圆角可控）。
- 界面任何地方都不再引入 QGraphicsEffect（阴影/透明度都会造成模糊感）。

接口与 QComboBox 兼容：addItem / currentIndex / currentData / findData /
setCurrentIndex / currentIndexChanged / setEnabled / setToolTip / setFont。
"""

from PySide6.QtWidgets import QWidget, QMenu
from PySide6.QtCore import Qt, QPoint, QPointF, QRectF, QSize, Signal
from PySide6.QtGui import QPainter, QColor, QPolygonF, QPen


class ChevronComboBox(QWidget):
    """自绘下拉框：圆角外观 + QMenu 弹出（收起▼ / 展开▲，主题感知）。"""

    # 用户切换选项时发射（与 QComboBox 一致：setCurrentIndex 不发射）
    currentIndexChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self._items = []          # list[(text, data)]
        self._current = -1
        self._menu = QMenu(self)
        # 去掉系统菜单阴影/边框残留，改用 QSS 圆角样式
        self._menu.setWindowFlags(
            self._menu.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self._menu_open = False
        self._menu.aboutToShow.connect(self._on_menu_open_changed)
        self._menu.aboutToHide.connect(self._on_menu_open_changed)
        self.setMinimumSize(80, 27)
        self.setFocusPolicy(Qt.ClickFocus)

    # ── 数据接口（QComboBox 兼容）──────────────────────────

    def addItem(self, text, data=None):
        idx = len(self._items)
        self._items.append((str(text), data))
        act = self._menu.addAction(str(text))
        act.triggered.connect(lambda checked=False, i=idx: self._select(i))
        if self._current < 0:
            self._current = idx
        self.update()

    def setCurrentIndex(self, idx: int):
        if 0 <= idx < len(self._items):
            self._current = idx
            self.update()

    def currentIndex(self) -> int:
        return self._current

    def currentData(self):
        if 0 <= self._current < len(self._items):
            return self._items[self._current][1]
        return None

    def findData(self, data) -> int:
        for i, (_, d) in enumerate(self._items):
            if d == data:
                return i
        return -1

    def currentText(self) -> str:
        if 0 <= self._current < len(self._items):
            return self._items[self._current][0]
        return ""

    # ── 交互 ──────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.isEnabled() and self._items:
            self._show_menu()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter)                 and self.isEnabled() and self._items:
            self._show_menu()
        else:
            super().keyPressEvent(event)

    def _on_menu_open_changed(self):
        """菜单打开/关闭时刷新三角方向。"""
        self._menu_open = self._menu.isVisible()
        self.update()

    def _select(self, idx: int):
        if idx != self._current:
            self._current = idx
            self.currentIndexChanged.emit(idx)
        self.update()

    def _show_menu(self):
        """在控件正下方弹出菜单，当前项默认高亮。"""
        if not self._items:
            return
        acts = self._menu.actions()
        if 0 <= self._current < len(acts):
            self._menu.setActiveAction(acts[self._current])
        pos = self.mapToGlobal(QPoint(0, self.height() + 2))
        # exec 阻塞直到选择/关闭
        self._menu.exec(pos)
        self.update()

    def setEnabled(self, enabled: bool):
        super().setEnabled(enabled)
        self.update()

    # ── 绘制 ──────────────────────────────────────────────

    def sizeHint(self) -> QSize:
        fm = self.fontMetrics()
        w = 40
        if self._items:
            w = max(fm.horizontalAdvance(self.currentText()) + 34, 80)
        return QSize(w, 27)

    def paintEvent(self, event):
        try:
            bg, border, text, arrow = self._colors()
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)

            r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
            painter.setPen(QPen(border, 1))
            painter.setBrush(bg)
            painter.drawRoundedRect(r, 8.0, 8.0)

            # 单层文本（左 9px，右侧留 22px 给三角）
            text_rect = QRectF(9, 0, max(0, self.width() - 31), self.height())
            painter.setFont(self.font())
            painter.setPen(text)
            fm = painter.fontMetrics()
            elided = fm.elidedText(self.currentText(), Qt.ElideRight,
                                   max(0, int(text_rect.width())))
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, elided)

            # 三角箭头（菜单打开时向上，与原生下拉习惯一致）
            cx = self.width() - 16
            cy = self.height() / 2.0
            s, h = 6.0, 5.0
            upward = self._menu_open
            if upward:
                pts = [QPointF(cx, cy - h), QPointF(cx - s, cy + h), QPointF(cx + s, cy + h)]
            else:
                pts = [QPointF(cx, cy + h), QPointF(cx - s, cy - h), QPointF(cx + s, cy - h)]
            painter.setPen(Qt.NoPen)
            painter.setBrush(arrow)
            painter.drawPolygon(QPolygonF(pts))
            painter.end()
        except Exception:
            pass

    def _colors(self):
        """返回 (背景, 边框, 文字, 三角) 四色，随主题与状态变化。"""
        # 注意：不能用 palette().window() 判断主题——QSS 全局
        # background: transparent 会让 QWidget 的 palette Window 变深色，
        # 导致浅色主题被误判为深色。统一走 ThemeManager。
        from gui.theme_manager import ThemeManager, THEME_DARK
        dark = ThemeManager().effective_theme == THEME_DARK
        enabled = self.isEnabled()
        hover = self.underMouse()
        focus = self.hasFocus()

        if dark:
            bg = (QColor("#141821") if not enabled else
                  QColor("#191e28") if focus else
                  QColor("#1a1f2a") if hover else QColor("#171b24"))
            border = (QColor(255, 255, 255, 40) if not enabled else
                      QColor("#4f9cf9") if focus else
                      QColor(255, 255, 255, 40) if hover else QColor(255, 255, 255, 23))
            text = QColor("#4a5160") if not enabled else QColor("#c9cedb")
            arrow = QColor("#4d5568") if not enabled else QColor("#aab2c4")
        else:
            bg = (QColor("#f5f6f9") if not enabled else
                  QColor("#fdfdff") if focus else
                  QColor("#fbfcfe") if hover else QColor("#ffffff"))
            border = (QColor("#eceef4") if not enabled else
                      QColor("#2f6fed") if focus else
                      QColor("#c9cddb") if hover else QColor("#dfe3ec"))
            text = QColor("#b6bdcc") if not enabled else QColor("#3a4155")
            arrow = QColor("#b6bdcc") if not enabled else QColor("#5a6579")
        return bg, border, text, arrow
