from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.ui.theme_service import ThemeService


class TextLabel(QtWidgets.QWidget):
    def __init__(self, text: str = "", parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._text = text
        self.alignment = (
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.elide_mode = QtCore.Qt.TextElideMode.ElideRight

        theme_service = ThemeService()
        self.text_color = theme_service.get_color("text")

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:

        opt = QtWidgets.QStyleOption()
        opt.initFrom(self)

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        font = self.font()
        painter.setFont(font)

        font_metrics = self.fontMetrics()
        text = font_metrics.elidedText(self._text, self.elide_mode, self.width())

        text_rect = self.rect()
        painter.setPen(QtGui.QPen(self.text_color))
        painter.drawText(text_rect, self.alignment, text)

        painter.end()

    def sizeHint(self) -> QtCore.QSize:
        font_metrics = self.fontMetrics()
        height = font_metrics.height()
        width = font_metrics.horizontalAdvance(self._text)
        return QtCore.QSize(width, height)
