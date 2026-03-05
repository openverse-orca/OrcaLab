from PySide6 import QtCore, QtWidgets, QtGui


class AskStatisticsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("收集统计数据?")
        self.setWindowFlag(QtCore.Qt.WindowType.WindowContextHelpButtonHint, False)

        layout = QtWidgets.QVBoxLayout(self)

        label = QtWidgets.QLabel(
            "收集匿名使用统计数据可以帮助改进OrcaLab，OrcaLab不会收集任何个人或项目数据。"
        )
        label.setWordWrap(True)
        layout.addWidget(label)

        btns = QtWidgets.QDialogButtonBox()
        allow_btn = QtWidgets.QPushButton("允许")
        deny_btn = QtWidgets.QPushButton("拒绝")
        btns.addButton(allow_btn, QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole)
        btns.addButton(deny_btn, QtWidgets.QDialogButtonBox.ButtonRole.RejectRole)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        layout.addWidget(btns)
        self.setMinimumWidth(420)

    @staticmethod
    def ask(parent=None) -> bool:
        dlg = AskStatisticsDialog(parent)
        accepted = dlg.exec()
        return accepted == QtWidgets.QDialog.DialogCode.Accepted
