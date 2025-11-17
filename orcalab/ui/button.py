from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.ui.theme_service import ThemeService


class Button(QtWidgets.QWidget):
    mouse_released = QtCore.Signal()
    mouse_pressed = QtCore.Signal()

    def __init__(
        self,
        text: str = "",
        icon: QtGui.QIcon | None = None,
        parent: QtWidgets.QWidget | None = None,
    ):
        super().__init__(parent)
        self._icon = icon
        self._text = text
        self.setMouseTracking(True)

        self._hover = False
        self._pressed = False

        theme = ThemeService()

        self.bg_color = theme.get_color("button_bg")
        self.bg_hover_color = theme.get_color("button_bg_hover")
        self.bg_pressed_color = theme.get_color("button_bg_pressed")
        self.text_color = theme.get_color("button_text")
        self.text_hover_color = theme.get_color("button_text_hover")
        self.text_pressed_color = theme.get_color("button_text_pressed")
        self.icon_size = 24
        self.font_size = 10
        self.padding_left = 8
        self.padding_right = 8
        self.padding_top = 4
        self.padding_bottom = 4
        self.padding_between = 4

        self.border_radius = 4

    def mousePressEvent(self, event):
        self._pressed = True
        self.update()
        self.mouse_pressed.emit()

    def mouseReleaseEvent(self, event):
        self._pressed = False
        self.update()
        self.mouse_released.emit()

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

        if self._icon and self._text:
            icon_rect = self._icon_rect()
            text_rect = self._text_rect()
            total_width = icon_rect.width() + self.padding_between + text_rect.width()
            start_x = (self.width() - total_width) // 2
            icon_rect.moveTo(start_x, (self.height() - icon_rect.height()) // 2)
            text_rect.moveTo(
                icon_rect.right() + self.padding_between,
                (self.height() - text_rect.height()) // 2,
            )
            self._draw_icon(painter, icon_rect)
            self._draw_text(painter, text_rect)
        elif self._icon:
            icon_rect = self._icon_rect()
            icon_rect.moveCenter(self.rect().center())
            self._draw_icon(painter, icon_rect)
        elif self._text:
            text_rect = self._text_rect()
            text_rect.moveCenter(self.rect().center())
            self._draw_text(painter, text_rect)

    def _icon_rect(self) -> QtCore.QRect:
        return QtCore.QRect(0, 0, self.icon_size, self.icon_size)

    def _text_rect(self) -> QtCore.QRect:
        font_metrics = QtGui.QFontMetrics(self.font())
        text_width = font_metrics.horizontalAdvance(self._text)
        text_height = font_metrics.height()
        return QtCore.QRect(0, 0, text_width, text_height)

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
        if not self._icon:
            return
        self._icon.paint(painter, rect)

    def _draw_text(self, painter: QtGui.QPainter, rect: QtCore.QRect):
        if self._pressed:
            painter.setPen(self.text_pressed_color)
        elif self._hover:
            painter.setPen(self.text_hover_color)
        else:
            painter.setPen(self.text_color)

        painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, self._text)

    def sizeHint(self):
        w = self.padding_left + self.padding_right
        h = self.padding_top + self.padding_bottom

        if self._icon:
            w = w + self.icon_size
        if self._icon and self._text:
            w = w + self.padding_between
        if self._text:
            font_metrics = QtGui.QFontMetrics(self.font())
            text_width = font_metrics.horizontalAdvance(self._text)
            w = w + text_width

        if self._icon:
            h = max(h, self.icon_size + self.padding_top + self.padding_bottom)
        if self._text:
            font_metrics = QtGui.QFontMetrics(self.font())
            text_height = font_metrics.height()
            h = max(h, text_height + self.padding_top + self.padding_bottom)

        return QtCore.QSize(w, h)

    def minimumSizeHint(self):
        return self.sizeHint()
