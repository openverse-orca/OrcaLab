from PySide6 import QtCore, QtWidgets, QtGui


class AskStatisticsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("用户体验改进计划")
        self.setWindowFlag(QtCore.Qt.WindowType.WindowContextHelpButtonHint, False)

        layout = QtWidgets.QVBoxLayout(self)

        label = QtWidgets.QLabel(
            '允许 OrcaLab 收集匿名使用数据以优化产品性能与用户体验？我们不会收集代码内容、文件路径或个人身份信息。所有数据均经脱敏处理并遵循<a href="https://datalink.orca3d.cn/privacy">《隐私政策》</a>进行存储。'
        )
        label.setWordWrap(True)
        label.setOpenExternalLinks(True)
        layout.addWidget(label)

        btns = QtWidgets.QDialogButtonBox()
        allow_btn = QtWidgets.QPushButton("同意参与")
        deny_btn = QtWidgets.QPushButton("暂不参与")
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
