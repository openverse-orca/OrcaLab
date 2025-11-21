from typing import override
from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.ui.checkbox import Checkbox
from orcalab.ui.property_edit.base_property_edit import (
    BasePropertyEdit,
    PropertyEditContext,
)
from orcalab.ui.theme_service import ThemeService


class BooleanPropertyEdit(BasePropertyEdit[bool]):

    def __init__(self, parent: QtWidgets.QWidget | None, context: PropertyEditContext, label_width: int):
        super().__init__(parent, context)
        root_layout = QtWidgets.QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(4)

        label = self._create_label(label_width)

        theme = ThemeService()
        bg_color = theme.get_color("property_edit_bg")
        parent_bg_color = theme.get_color("property_group_bg")

        editor = Checkbox()
        editor.icon_size = 24
        editor.bg_color = parent_bg_color
        editor.bg_hover_color = bg_color
        editor.bg_pressed_color = bg_color
        editor.set_checked(context.prop.value())
        editor.value_changed.connect(self._on_state_changed)

        root_layout.addWidget(label)
        root_layout.addWidget(editor)
        root_layout.addStretch()

        self._editor = editor
        self._block_events = False

    def _on_state_changed(self):
        if self._block_events:
            return

        value = self._editor.checked()
        self.context.prop.set_value(value)

        undo = not self.in_dragging
        self._do_set_value(value, undo)

    @override
    def set_value(self, value: bool):
        self._block_events = True

        self.context.prop.set_value(value)
        self._editor.set_checked(value)

        self._block_events = False
