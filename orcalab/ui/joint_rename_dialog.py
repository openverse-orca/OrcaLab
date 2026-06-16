from PySide6 import QtWidgets
from typing import Callable, Tuple


class JointRenameDialog(QtWidgets.QDialog):
    def __init__(
        self,
        current_name: str,
        validate: Callable[[str], Tuple[bool, str]],
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("重命名关节")
        self.setModal(True)
        self.setMinimumSize(360, 160)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        self._validate = validate
        self.new_name = None
        self._current_name = current_name
        self._init_ui()

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        self.setLayout(layout)

        info_label = QtWidgets.QLabel(f"当前名称: {self._current_name}")
        layout.addWidget(info_label)

        self.line_edit = QtWidgets.QLineEdit(self)
        self.line_edit.setText(self._current_name)
        self.line_edit.selectAll()
        self.line_edit.setFocus()
        self.line_edit.returnPressed.connect(self._on_accept)
        layout.addWidget(self.line_edit)

        self.error_message = QtWidgets.QLabel()
        self.error_message.setStyleSheet("QLabel { color: red; }")
        self.error_message.setWordWrap(True)
        layout.addWidget(self.error_message)

        ButtonRole = QtWidgets.QDialogButtonBox.ButtonRole
        button_box = QtWidgets.QDialogButtonBox()
        button_box.addButton("确认", ButtonRole.AcceptRole).clicked.connect(
            self._on_accept
        )
        button_box.addButton("取消", ButtonRole.RejectRole).clicked.connect(
            self.reject
        )
        layout.addWidget(button_box)

    def _on_accept(self) -> None:
        new_name = self.line_edit.text().strip()

        if new_name == self._current_name:
            self.reject()
            return

        valid, error = self._validate(new_name)
        if not valid:
            self.error_message.setText(error)
            return

        self.new_name = new_name
        super().accept()
