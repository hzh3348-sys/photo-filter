"""
苹果风格拨动开关 (ToggleSwitch) — 紧凑 + 平滑动画。
"""

from PySide6.QtWidgets import QCheckBox
from PySide6.QtCore import Qt, QRect, QPoint, Property, QVariantAnimation, QEasingCurve, QSize
from PySide6.QtGui import QPainter, QColor, QPen


class ToggleSwitch(QCheckBox):
    """iOS 风格拨动开关（紧凑 + 动画）。"""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumWidth(self._calc_width())
        self.setFixedHeight(26)
        self._anim_value = 1.0 if self.isChecked() else 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)
        self._anim.valueChanged.connect(self._on_anim)
        self._anim.finished.connect(self.update)

    def _calc_width(self):
        fm = self.fontMetrics()
        return fm.horizontalAdvance(self.text()) + 58

    def setText(self, text):
        super().setText(text)
        self.setMinimumWidth(self._calc_width())

    def _on_anim(self, val):
        self._anim_value = float(val)
        self.update()

    def nextCheckState(self):
        target = 1.0 if not self.isChecked() else 0.0
        self._anim.stop()
        self._anim.setStartValue(self._anim_value)
        self._anim.setEndValue(target)
        self._anim.start()
        super().nextCheckState()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        dark = self.palette().window().color().value() < 100

        # 文字
        painter.setPen(QColor("#d0d4e0") if dark else QColor("#2c3e50"))
        text_rect = QRect(44, 0, self.width() - 48, self.height())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text())

        # 轨道
        checked = self.isChecked()
        running = self._anim.state() == QVariantAnimation.Running
        t = self._anim_value if running else (1.0 if checked else 0.0)
        off_color = QColor("#555") if dark else QColor("#c8cdd3")
        on_color = QColor("#5c6bc0")
        r = int(off_color.red() + (on_color.red() - off_color.red()) * t)
        g = int(off_color.green() + (on_color.green() - off_color.green()) * t)
        b = int(off_color.blue() + (on_color.blue() - off_color.blue()) * t)
        track_color = QColor(r, g, b)

        track = QRect(0, 4, 40, 18)
        painter.setPen(Qt.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track, 9, 9)

        # 手柄
        handle_x = int(2 + t * 18)
        handle = QRect(handle_x, 0, 22, 26)
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QPen(QColor("#bbb") if not dark else QColor("#555"), 1))
        painter.drawEllipse(handle)

    def hitButton(self, pos: QPoint):
        """仅开关轨道区域可点击，文字区域不触发。"""
        return pos.x() >= 0 and pos.x() <= 44

    def sizeHint(self):
        return QSize(self._calc_width(), 26)
