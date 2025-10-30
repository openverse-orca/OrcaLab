from PySide6 import QtCore, QtWidgets

class SceneSelectDialog(QtWidgets.QDialog):
    def __init__(self, levels, current_level=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择场景")
        self.setModal(True)
        self.resize(350, 250)
        self.levels = levels
        self.selected_level = current_level or (levels[0] if levels else None)
        self._init_ui()

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        self.setLayout(layout)

        label = QtWidgets.QLabel("请选择场景：")
        layout.addWidget(label)

        # 滚动区包裹单选框组（单列，至多显示5项）
        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        container = QtWidgets.QWidget()
        vbox = QtWidgets.QVBoxLayout(container)
        vbox.setContentsMargins(0,0,0,0)
        vbox.setSpacing(8)
        self.radio_buttons = []
        group = QtWidgets.QButtonGroup(self)
        for idx, level in enumerate(self.levels):
            radio = QtWidgets.QRadioButton(level, self)
            if level == self.selected_level:
                radio.setChecked(True)
            group.addButton(radio)
            self.radio_buttons.append(radio)
            vbox.addWidget(radio)
        vbox.addStretch(1)
        container.setLayout(vbox)
        scroll.setWidget(container)
        scroll.setMaximumHeight(5 * 28 + 8)  # 单项大约28px，加空隙
        layout.addWidget(scroll)

        button_box = QtWidgets.QDialogButtonBox()
        ok_btn = button_box.addButton("打开", QtWidgets.QDialogButtonBox.AcceptRole)
        cancel_btn = button_box.addButton("取消", QtWidgets.QDialogButtonBox.RejectRole)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_selected_level(self):
        for btn in self.radio_buttons:
            if btn.isChecked():
                return btn.text()
        return None

    @staticmethod
    def get_level(levels, current_level=None, parent=None):
        dlg = SceneSelectDialog(levels, current_level, parent)
        result = dlg.exec()
        return (dlg.get_selected_level(), result == QtWidgets.QDialog.Accepted)
