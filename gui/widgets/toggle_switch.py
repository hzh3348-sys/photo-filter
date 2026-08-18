"""
苹果风格拨动开关 (ToggleSwitch) — 现代圆润外观 + 平滑动画 (v5.2)。
自绘渲染（不走 QSS），自动适配浅色/深色主题。
"""

from PySide6.QtWidgets import QCheckBox
from PySide6.QtCore import Qt, QRect, QRectF, QPoint, Property, QVariantAnimation, QEasingCurve, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QRadialGradient


class ToggleSwitch(QCheckBox):
    """iOS 风格拨动开关（紧凑 + 动画 + 主题适配）。"""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumWidth(self._calc_width())
        self.setFixedHeight(26)
        self._anim_value = 1.0 if self.isChecked() else 0.0
        self._target = self._anim_value   # 当前目标位置（0/1）
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)
        self._anim.finished.connect(self._on_anim_finished)

    def _calc_width(self):
        fm = self.fontMetrics()
        return fm.horizontalAdvance(self.text()) + 58

    def setText(self, text):
        super().setText(text)
        self.setMinimumWidth(self._calc_width())

    def _on_anim(self, val):
        self._anim_value = float(val)
        self.update()

    def _on_anim_finished(self):
        # 动画结束：把位置钉在目标值，避免中断后回跳
        self._anim_value = self._target
        self.update()

    def _animate_to(self, target: float):
        """从当前视觉位置平滑过渡到 target（0/1），中断后续接当前值。"""
        self._target = target
        self._anim.stop()
        self._anim.setStartValue(self._anim_value)
        self._anim.setEndValue(target)
        self._anim.start()

    def setChecked(self, checked):
        """覆盖：代码路径的 setChecked 也走动画（修复动画丢失）。"""
        if self.isChecked() == bool(checked):
            return
        self._animate_to(1.0 if checked else 0.0)
        super().setChecked(checked)

    def nextCheckState(self):
        target = 1.0 if not self.isChecked() else 0.0
        self._animate_to(target)
        super().nextCheckState()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 主题检测（浅/深）
        dark = self.palette().window().color().value() < 100

        # 文字（颜色随主题；disabled 变灰）
        if self.isEnabled():
            text_color = QColor("#c3c8d6") if dark else QColor("#3a4155")
        else:
            text_color = QColor("#4d5466") if dark else QColor("#b4b9c9")
        painter.setPen(text_color)
        text_rect = QRect(44, 0, self.width() - 48, self.height())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text())

        # 轨道状态：动画中取插值，动画外取目标值（不再回跳/丢失动画）
        running = self._anim.state() == QVariantAnimation.Running
        t = self._anim_value if running else self._target

        # 颜色
        if dark:
            off_color = QColor("#333a48")
            on_color = QColor("#818cf8")
            off_border = QColor("#3a4150")
        else:
            off_color = QColor("#dfe2ec")
            on_color = QColor("#6366f1")
            off_border = QColor("#d0d4e0")

        # 过渡色
        r = int(off_color.red() + (on_color.red() - off_color.red()) * t)
        g = int(off_color.green() + (on_color.green() - off_color.green()) * t)
        b = int(off_color.blue() + (on_color.blue() - off_color.blue()) * t)
        track_color = QColor(r, g, b)

        # 轨道（更大圆角）
        track = QRectF(0, 4, 40, 18)
        painter.setPen(Qt.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track, 9, 9)

        # 手柄（白底 + 细描边 + 阴影感）
        handle_d = 20.0
        handle_x = 1.5 + t * (40.0 - handle_d)
        handle_rect = QRectF(handle_x, 3.0, handle_d, handle_d)
        painter.setPen(QPen(QColor("#00000018"), 1))
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(handle_rect)

        # 手柄内的高光点（微立体感）
        hi = QRectF(handle_x + 4.5, 5.5, 6, 6)
        grad = QRadialGradient(hi.center(), 4)
        grad.setColorAt(0, QColor("#ffffff"))
        grad.setColorAt(1, QColor("#f2f3f7"))
        painter.setPen(Qt.NoPen)
        painter.setBrush(grad)
        painter.drawEllipse(hi)

    def hitButton(self, pos: QPoint):
        """仅开关轨道区域可点击，文字区域不触发。"""
        return pos.x() >= 0 and pos.x() <= 44

    def sizeHint(self):
        return QSize(self._calc_width(), 26)


# 保持 Property 导入兼容（某些引用场景）
__all__ = ["ToggleSwitch"]
