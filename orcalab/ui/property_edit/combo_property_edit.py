import asyncio

from PySide6 import QtCore, QtWidgets
from typing_extensions import override

from orcalab.actor_property import ActorPropertyType
from orcalab.i18n import tr
from orcalab.scene_edit_bus import SceneEditRequestBus
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


class ComboBoxPropertyEdit(BasePropertyEdit[str | int]):
    """枚举属性编辑器：显示本地化标签，并用 itemData 保留后端原始值。"""

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
            options = (
                hint[len("options:") :].split(",")
                if hint.startswith("options:")
                else []
            )

        editor = _PropertyComboBox()
        if context.prop.value_type() == ActorPropertyType.INTEGER:
            raw_values: list[str | int] = list(range(len(options)))
        else:
            raw_values = options

        for option_label, raw_value in zip(options, raw_values):
            editor.addItem(tr(option_label), raw_value)

        current = context.prop.value()
        current_index = editor.findData(current)
        editor.setCurrentIndex(current_index)
        editor.currentIndexChanged.connect(self._on_index_changed)

        root_layout.addWidget(label)
        root_layout.addWidget(editor)

        FontService().bind_widget_font(editor, "property_edit")

        self._editor = editor
        self._block_events = False

    def _on_index_changed(self, index: int):
        if self._block_events or index < 0:
            return
        value = self._editor.itemData(index)
        old_value = self.context.prop.value()
        self.context.prop.set_value(value)

        task = SceneEditRequestBus().set_property(
            property_key=self.context.key,
            value=value,
            undo=True,
            old_value=old_value,
            source="ui",
        )
        asyncio.create_task(task)

    @override
    def set_value(self, value: str | int):
        self._block_events = True
        try:
            self.context.prop.set_value(value)
            idx = self._editor.findData(value)
            self._editor.setCurrentIndex(idx)
        finally:
            self._block_events = False

    @override
    def set_read_only(self, read_only: bool):
        self._editor.setEnabled(not read_only)
