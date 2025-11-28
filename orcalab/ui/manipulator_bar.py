from PySide6 import QtCore, QtWidgets, QtGui
from orcalab.ui.panel_area import PanelButton
from orcalab.ui.button import Button
import orcalab.assets.rc_assets


class ManipulatorBar(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._layout = QtWidgets.QHBoxLayout()
        self._layout.setContentsMargins(8, 0, 8, 0)
        self._layout.setSpacing(8)
        self.setLayout(self._layout)

        self.action_move = QtGui.QAction("移动(快捷键:1)", self)
        self.action_move.setIcon(QtGui.QIcon(":/icons/move"))

        self.action_rotate = QtGui.QAction("旋转(快捷键:2)", self)
        self.action_rotate.setIcon(QtGui.QIcon(":/icons/rotate"))

        self.action_scale = QtGui.QAction("缩放(快捷键:3)", self)
        self.action_scale.setIcon(QtGui.QIcon(":/icons/scale"))

        # 给图标变亮灰色
        self.action_scale.setIcon(self.recolor_icon(self.action_scale.icon(), "#CCCCCC"))
        self.action_move.setIcon(self.recolor_icon(self.action_move.icon(), "#CCCCCC"))
        self.action_rotate.setIcon(self.recolor_icon(self.action_rotate.icon(), "#CCCCCC"))

        button_size = QtCore.QSize(16, 16)

        self.move_button = QtWidgets.QToolButton()
        self.move_button.setDefaultAction(self.action_move)

        self.rotate_button = QtWidgets.QToolButton()
        self.rotate_button.setDefaultAction(self.action_rotate)

        self.scale_button = QtWidgets.QToolButton()
        self.scale_button.setDefaultAction(self.action_scale)

        self._layout.addStretch()
        self._layout.addWidget(self.move_button)
        self._layout.addWidget(self.rotate_button)
        self._layout.addWidget(self.scale_button)

    def recolor_icon(self, icon: QtGui.QIcon, color: str, size=32):
        pixmap = icon.pixmap(size, size)
        tinted = QtGui.QPixmap(size, size)
        tinted.fill(QtCore.Qt.transparent)

        painter = QtGui.QPainter(tinted)
        painter.drawPixmap(0, 0, pixmap)
        painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
        painter.fillRect(tinted.rect(), QtGui.QColor(color))
        painter.end()

        return QtGui.QIcon(tinted)


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    manipulatorbar = ManipulatorBar()
    manipulatorbar.show()
    manipulatorbar.resize(400, 50)

    manipulatorbar.action_move.triggered.connect(lambda: print("M"))
    manipulatorbar.action_rotate.triggered.connect(lambda: print("R"))
    manipulatorbar.action_scale.triggered.connect(lambda: print("S"))

    sys.exit(app.exec())
