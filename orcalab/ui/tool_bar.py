from PySide6 import QtCore, QtWidgets, QtGui
import orcalab.assets.rc_assets


class ToolBar(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._layout = QtWidgets.QHBoxLayout()
        self._layout.setContentsMargins(8, 0, 8, 0)
        self._layout.setSpacing(8)
        self.setLayout(self._layout)

        self.action_start = QtGui.QAction("开始", self)
        self.action_start.setIcon(QtGui.QIcon(":/icons/play"))

        self.action_stop = QtGui.QAction("停止", self)
        self.action_stop.setIcon(QtGui.QIcon(":/icons/stop"))

        button_size = QtCore.QSize(16, 16)
        self.run_button = QtWidgets.QToolButton()
        self.run_button.setDefaultAction(self.action_start)
        self.run_button.setIconSize(button_size)

        self.stop_button = QtWidgets.QToolButton()
        self.stop_button.setDefaultAction(self.action_stop)
        self.stop_button.setIconSize(button_size)

        self._layout.addStretch()
        self._layout.addWidget(self.run_button)
        self._layout.addWidget(self.stop_button)


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    toolbar = ToolBar()
    toolbar.show()
    toolbar.resize(400, 50)

    toolbar.action_start.triggered.connect(lambda: print("Run"))
    toolbar.action_stop.triggered.connect(lambda: print("Stop"))

    sys.exit(app.exec())
