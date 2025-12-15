from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.ui.icon_util import make_color_svg
from orcalab.ui.theme_service import ThemeService


class Checkbox(QtWidgets.QWidget):
    value_changed = QtCore.Signal()

    def __init__(self,  parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setMouseTracking(True)

        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed
        )

        self._checked = False

        self._hover = False
        self._pressed = False

        theme = ThemeService()

        self.bg_color = theme.get_color("button_bg")
        self.bg_hover_color = theme.get_color("button_bg")
        self.bg_pressed_color = theme.get_color("button_bg")
        self.text_color = theme.get_color("text")
        self.text_hover_color = theme.get_color("text")
        self.text_pressed_color = theme.get_color("text")
        self.icon_size = 20
        self.padding_left = 0
        self.padding_right = 0
        self.padding_top = 0
        self.padding_bottom = 0
        self.padding_between = 0

        self.border_radius = 4

        self._pixmap_checked = make_color_svg(
            ":/icons/checkbox_checked", self.text_color
        )
        self._pixmap_unchecked = make_color_svg(
            ":/icons/checkbox_unchecked", self.text_color
        )

    def checked(self) -> bool:
        return self._checked

    def set_checked(self, checked: bool):
        if self._checked != checked:
            self._checked = checked
            self.value_changed.emit()
            self.update()

    def toggle(self):
        self.set_checked(not self._checked)

    def mousePressEvent(self, event):
        self._pressed = True
        self.toggle()

    def mouseReleaseEvent(self, event):
        self._pressed = False
        self.update()

    def enterEvent(self, event):
        self._hover = True
        self.update()
        return super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        return super().leaveEvent(event)

    def paintEvent(self, event: QtGui.QPaintEvent):
        painter = QtGui.QPainter(self)
        self._draw_background(painter, self.rect())

        icon_rect = self._icon_rect()
        icon_rect.moveCenter(self.rect().center())
        self._draw_icon(painter, icon_rect)

        painter.end()

    def _icon_rect(self) -> QtCore.QRect:
        return QtCore.QRect(0, 0, self.icon_size, self.icon_size)

    def _draw_background(self, painter: QtGui.QPainter, rect: QtCore.QRect):
        if self._pressed:
            bg_color = self.bg_pressed_color
        elif self._hover:
            bg_color = self.bg_hover_color
        else:
            bg_color = self.bg_color

        painter.setBrush(QtGui.QBrush(bg_color))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, self.border_radius, self.border_radius)

    def _draw_icon(self, painter: QtGui.QPainter, rect: QtCore.QRect):
        if self._checked:
            painter.drawPixmap(rect, self._pixmap_checked)
        else:
            painter.drawPixmap(rect, self._pixmap_unchecked)

    def sizeHint(self):
        w = self.padding_left + self.padding_right
        h = self.padding_top + self.padding_bottom

        w = w + self.icon_size
        h = h + self.icon_size

        return QtCore.QSize(w, h)

    def minimumSizeHint(self):
        return self.sizeHint()
