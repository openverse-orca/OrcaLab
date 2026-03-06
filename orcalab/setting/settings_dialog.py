from PySide6 import QtCore, QtWidgets, QtGui
from orcalab.config_service import ConfigService
from orcalab.ui.checkbox import CheckBox
from orcalab.ui.text_label import TextLabel
from orcalab.pyside_util import connect


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)

        root_layout = QtWidgets.QVBoxLayout(self)

        desc = TextLabel("发送用统计数据可以帮助改进OrcaLab。")
        checkbox = CheckBox()

        row_layout = QtWidgets.QHBoxLayout()
        row_layout.addWidget(checkbox, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        row_layout.addWidget(desc, 1, QtCore.Qt.AlignmentFlag.AlignVCenter)
        row_layout.addStretch()

        self.checkbox = checkbox

        connect(checkbox.value_changed, self.on_checkbox_toggled)

        root_layout.addLayout(row_layout)
        root_layout.addStretch()

        self.resize(800, 600)

    def on_checkbox_toggled(self):
        config = ConfigService()
        config.set_send_statistics("true" if self.checkbox.checked() else "false")


