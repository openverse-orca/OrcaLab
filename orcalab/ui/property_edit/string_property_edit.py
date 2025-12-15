from typing import override
from PySide6 import QtCore, QtWidgets, QtGui


from orcalab.ui.property_edit.base_property_edit import (
    BasePropertyEdit,
    PropertyEditContext,
)
from orcalab.ui.edit.string_edit import StringEdit


class StringPropertyEdit(BasePropertyEdit[str]):

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

        editor = StringEdit()
        editor.setText(context.prop.value())
        editor.value_changed.connect(self._on_text_changed)
        editor.setStyleSheet(self.base_style)
        editor.setFocusPolicy(QtCore.Qt.FocusPolicy.ClickFocus)

        root_layout.addWidget(label)
        root_layout.addWidget(editor)

        self._editor = editor
        self._block_events = False

    def _on_text_changed(self):
        if self._block_events:
            return

        text = self._editor.text()
        self.context.prop.set_value(text)

        undo = not self.in_dragging
        self._do_set_value(text, undo)

    @override
    def set_value(self, value: str):
        self._block_events = True

        self.context.prop.set_value(value)
        self._editor.setText(value)

        self._block_events = False
