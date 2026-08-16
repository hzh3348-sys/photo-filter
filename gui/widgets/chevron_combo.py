"""
自定义下拉框 — QPainter 直接绘制矢量三角箭头 (v5.2)。

背景：Qt QSS 的 ::down-arrow border 三角技巧在部分 Qt 版本会渲染成
方形色块。此组件在 paintEvent 里用 QPainter.drawPolygon 画实心三角：
- 收起状态：向下三角（提示可展开）
- 展开状态：向上三角（提示可收起）
主题感知配色 + 禁用态置灰。
"""

from PySide6.QtWidgets import QComboBox
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QColor, QPolygonF


class ChevronComboBox(QComboBox):
    """带自绘三角箭头的下拉框（收起向下 / 展开向上）。"""

    def __init__(self, parent=None):
        super().__init__(parent)

    def _is_expanded(self) -> bool:
        view = self.view()
        return view is not None and view.isVisible()

    def paintEvent(self, event):
        super().paintEvent(event)
        try:
            dark = self.palette().window().color().value() < 100
            if not self.isEnabled():
                color = QColor("#4d5568") if dark else QColor("#b6bdcc")
            elif dark:
                color = QColor("#aab2c4")
            else:
                color = QColor("#5a6579")

            expanded = self._is_expanded()
            r = self.rect()
            cx = r.right() - 16
            cy = r.center().y()
            s = 6.0   # 半宽
            h = 5.0   # 半高

            if expanded:
                pts = [QPointF(cx, cy - h), QPointF(cx - s, cy + h), QPointF(cx + s, cy + h)]
            else:
                pts = [QPointF(cx, cy + h), QPointF(cx - s, cy - h), QPointF(cx + s, cy - h)]

            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawPolygon(QPolygonF(pts))
            painter.end()
        except Exception:
            pass  # 绘制失败不影响功能
