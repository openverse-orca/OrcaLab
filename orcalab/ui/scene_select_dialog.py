from PySide6 import QtCore, QtWidgets


class SceneSelectDialog(QtWidgets.QDialog):
    def __init__(self, levels, current_level=None, layout_mode: str = "default", parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择场景")
        self.setModal(True)
        self.setMinimumSize(420, 360)
        self.resize(480, 380)
        self.levels = self._normalize_levels(levels)
        self.selected_level = current_level or (
            self.levels[0]["path"] if self.levels else None
        )
        self._initial_layout_mode = layout_mode if layout_mode in {"default", "blank"} else "default"
        self._init_ui()

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        self.setLayout(layout)

        label = QtWidgets.QLabel("请选择场景：")
        layout.addWidget(label)

        # 滚动区包裹单选框组（单列，至少显示 5 项）
        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        container = QtWidgets.QWidget()
        vbox = QtWidgets.QVBoxLayout(container)
        vbox.setContentsMargins(0,0,0,0)
        vbox.setSpacing(8)
        self.radio_buttons = []
        group = QtWidgets.QButtonGroup(self)
        for idx, level in enumerate(self.levels):
            radio = QtWidgets.QRadioButton(level["name"], self)
            radio.setProperty("level_path", level["path"])
            if level["path"] == self.selected_level:
                radio.setChecked(True)
            group.addButton(radio)
            self.radio_buttons.append(radio)
            vbox.addWidget(radio)
        vbox.addStretch(1)
        container.setLayout(vbox)
        scroll.setWidget(container)
        scroll.setMinimumHeight(5 * 32 + 16)  # 保证至少显示 5 项
        layout.addWidget(scroll)

        option_group = QtWidgets.QGroupBox("布局选项")
        option_layout = QtWidgets.QVBoxLayout(option_group)
        option_layout.setContentsMargins(12, 8, 12, 8)
        option_layout.setSpacing(6)
        self.radio_load_default = QtWidgets.QRadioButton("加载默认布局", self)
        self.radio_blank_layout = QtWidgets.QRadioButton("空白布局", self)
        if self._initial_layout_mode == "blank":
            self.radio_blank_layout.setChecked(True)
        else:
            self.radio_load_default.setChecked(True)
        option_layout.addWidget(self.radio_load_default)
        option_layout.addWidget(self.radio_blank_layout)
        layout.addWidget(option_group)

        button_box = QtWidgets.QDialogButtonBox()
        ok_btn = button_box.addButton("打开", QtWidgets.QDialogButtonBox.AcceptRole)
        cancel_btn = button_box.addButton("取消", QtWidgets.QDialogButtonBox.RejectRole)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_selected_level(self):
        for btn in self.radio_buttons:
            if btn.isChecked():
                path = btn.property("level_path")
                return self._get_level_by_path(path)
        return None

    @staticmethod
    def _normalize_levels(levels):
        normalized = []
        for item in levels or []:
            if isinstance(item, dict):
                path = item.get("path") or item.get("name")
                if not path:
                    continue
                name = item.get("name") or path
                normalized_item = dict(item)
                normalized_item["name"] = name
                normalized_item["path"] = path
                normalized.append(normalized_item)
            else:
                path = str(item)
                name = path
                normalized.append({"name": name, "path": path})
        return normalized

    def _get_level_by_path(self, path):
        if not path:
            return None
        for item in self.levels:
            if item["path"] == path:
                return item
        return None

    def get_layout_mode(self) -> str:
        return "blank" if self.radio_blank_layout.isChecked() else "default"

    @staticmethod
    def get_level(levels, current_level=None, layout_mode: str = "default", parent=None):
        dlg = SceneSelectDialog(levels, current_level, layout_mode, parent)
        result = dlg.exec()
        return (
            dlg.get_selected_level(),
            dlg.get_layout_mode(),
            result == QtWidgets.QDialog.Accepted,
        )
