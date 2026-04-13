from typing import override
from PySide6 import QtWidgets

from orcalab.ui.property_edit.base_property_edit import (
    BasePropertyEdit,
    PropertyEditContext,
)


class ComboBoxPropertyEdit(BasePropertyEdit[int]):
    """整数枚举属性编辑器：从 editor_hint "options:A,B,C" 解析选项，下拉框选择。"""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        context: PropertyEditContext,
        label_width: int,
    ):
        super().__init__(parent, context)
        root_layout = QtWidgets.QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(4)

        label = self._create_label(label_width)

        hint = context.prop.editor_hint()
        options = hint[len("options:"):].split(",") if hint.startswith("options:") else []

        editor = QtWidgets.QComboBox()
        editor.addItems(options)
        current = context.prop.value()
        if isinstance(current, int) and 0 <= current < len(options):
            editor.setCurrentIndex(current)
        editor.currentIndexChanged.connect(self._on_index_changed)

        root_layout.addWidget(label)
        root_layout.addWidget(editor)

        self._editor = editor
        self._block_events = False

    def _on_index_changed(self, index: int):
        if self._block_events:
            return
        self.context.prop.set_value(index)
        self._do_set_value(index, undo=True)

    @override
    def set_value(self, value: int):
        self._block_events = True
        self.context.prop.set_value(value)
        if 0 <= value < self._editor.count():
            self._editor.setCurrentIndex(value)
        self._block_events = False

    @override
    def set_read_only(self, read_only: bool):
        self._editor.setEnabled(not read_only)
