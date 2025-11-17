from PySide6 import QtCore, QtWidgets, QtGui


class Icon(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)

        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )

        self._icon_size = 24
        self._pixmap: QtGui.QPixmap | None = None

        self.set_icon_size(self._icon_size)

    def paintEvent(self, event: QtGui.QPaintEvent):
        if self._pixmap is None:
            return

        painter = QtGui.QPainter(self)
        painter.drawPixmap(self.rect(), self._pixmap)

        painter.end()

    def icon_size(self) -> int:
        return self._icon_size

    def set_icon_size(self, size: int):
        self._icon_size = size
        self.setFixedSize(self._icon_size, self._icon_size)
        self.update()

    def pixmap(self) -> QtGui.QPixmap | None:
        return self._pixmap

    def set_pixmap(self, pixmap: QtGui.QPixmap):
        self._pixmap = pixmap
        self.update()
