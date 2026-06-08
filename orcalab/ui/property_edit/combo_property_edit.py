from typing import override
from PySide6 import QtWidgets, QtCore

from orcalab.ui.fonts.font_service import FontService
from orcalab.ui.property_edit.base_property_edit import (
    BasePropertyEdit,
    PropertyEditContext,
)


class _PropertyComboBox(QtWidgets.QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

    def showPopup(self):
        self.setFocus()
        super().showPopup()

    def hidePopup(self):
        super().hidePopup()
        self.clearFocus()

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()

class ComboBoxPropertyEdit(BasePropertyEdit[str]):
    """枚举属性编辑器：使用标签文本进行交互，通过 enum_values 或 editor_hint "options:A,B,C" 解析选项。"""

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

        enum_vals = context.prop.enum_values()
        if enum_vals:
            options = enum_vals
        else:
            hint = context.prop.editor_hint()
            options = hint[len("options:"):].split(",") if hint.startswith("options:") else []

        editor = _PropertyComboBox()
        editor.addItems(options)
        current = context.prop.value()
        if isinstance(current, str) and current in options:
            editor.setCurrentIndex(options.index(current))
        elif isinstance(current, int) and 0 <= current < len(options):
            editor.setCurrentIndex(current)
        editor.currentIndexChanged.connect(self._on_index_changed)

        root_layout.addWidget(label)
        root_layout.addWidget(editor)

        FontService().bind_widget_font(editor, 'property_edit')

        self._editor = editor
        self._options = options
        self._block_events = False

    def _on_index_changed(self, index: int):
        if self._block_events:
            return
        text = self._editor.currentText()
        self.context.prop.set_value(text)
        self._do_set_value(text, undo=True)

    @override
    def set_value(self, value: str):
        self._block_events = True
        self.context.prop.set_value(value)
        idx = self._editor.findText(value)
        if idx >= 0:
            self._editor.setCurrentIndex(idx)
        self._block_events = False

    @override
    def set_read_only(self, read_only: bool):
        self._editor.setEnabled(not read_only)
