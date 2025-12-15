from PySide6 import QtCore, QtWidgets, QtGui


class StyledWidget(QtWidgets.QWidget):
    """A QWidget that supports styling via stylesheets."""

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._hovered = False
        self.setMouseTracking(True)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        opt = QtWidgets.QStyleOption()
        opt.initFrom(self)
        painter = QtGui.QPainter(self)
        self.style().drawPrimitive(
            QtWidgets.QStyle.PrimitiveElement.PE_Widget, opt, painter, self
        )
