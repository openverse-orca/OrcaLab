from typing import Any, override
from PySide6 import QtCore, QtWidgets, QtGui


from orcalab.ui.edit.float_edit import FloatEdit
from orcalab.ui.property_edit.base_property_edit import (
    BasePropertyEdit,
    PropertyEditContext,
)


class FloatPropertyEdit(BasePropertyEdit[float]):

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

        editor = FloatEdit()
        editor.set_value(context.prop.value())
        editor.value_changed.connect(self._on_value_changed)
        editor.start_drag.connect(self._on_start_drag)
        editor.stop_drag.connect(self._on_end_drag)
        editor.setStyleSheet(self.base_style)

        root_layout.addWidget(label)
        root_layout.addWidget(editor)

        self._editor = editor
        self._block_events = False

    def _on_value_changed(self):
        if self._block_events:
            return
        value = self._editor.value()
        self.context.prop.set_value(value)

        undo = not self.in_dragging
        self._do_set_value(value, undo)

    @override
    def set_value(self, value: Any):
        self._block_events = True

        self.context.prop.set_value(value)
        self._editor.set_value(value)

        self._block_events = False
