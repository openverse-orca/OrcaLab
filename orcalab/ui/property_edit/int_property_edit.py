from typing import override
from PySide6 import QtCore, QtWidgets, QtGui


from orcalab.scene_edit_bus import SceneEditRequestBus
from orcalab.ui.edit.int_edit import IntEdit
from orcalab.ui.fonts.font_service import FontService
from orcalab.ui.property_edit.base_property_edit import (
    BasePropertyEdit,
    PropertyEditContext,
)


class IntegerPropertyEdit(BasePropertyEdit[int]):

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

        editor = IntEdit()
        editor.set_value(context.prop.value())
        editor.on_value_changed = self._on_value_changed
        editor.on_start_drag = self._on_start_drag
        editor.on_stop_drag = self._on_stop_drag
        editor.setStyleSheet(self.base_style)

        root_layout.addWidget(label)
        root_layout.addWidget(editor)

        FontService().bind_widget_font(editor, "property_edit")

        self._editor = editor
        self._block_events = False
        self.in_dragging = False

    @override
    def set_value(self, value: int):
        self._block_events = True

        self.context.prop.set_value(value)
        self._editor.set_value(value)

        self._block_events = False

    @override
    def set_read_only(self, read_only: bool):
        self._editor.setReadOnly(read_only)

    async def _on_start_drag(self):
        old_value = self.context.prop.value()
        await SceneEditRequestBus().start_change_property(
            property_key=self.context.key,
            old_value=old_value,
            timeout=0.5,
        )
        self.in_dragging = True

    async def _on_stop_drag(self):
        new_value = self.context.prop.value()
        await SceneEditRequestBus().end_change_property(
            property_key=self.context.key,
            new_value=new_value,
        )
        self.in_dragging = False

    async def _on_value_changed(self):
        if self._block_events:
            return

        value = self._editor.value()
        old_value = self.context.prop.value()
        self.context.prop.set_value(value)

        undo = not self.in_dragging
        await SceneEditRequestBus().set_property(
            property_key=self.context.key,
            value=value,
            undo=undo,
            old_value=old_value,
            source="ui",
        )
