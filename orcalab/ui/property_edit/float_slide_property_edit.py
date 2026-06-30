from typing import Callable
from typing_extensions import override
from PySide6 import QtCore, QtWidgets

from orcalab.scene_edit_bus import SceneEditRequestBus
from orcalab.ui.edit.float_edit import FloatEdit
from orcalab.ui.fonts.font_service import FontService
from orcalab.ui.property_edit.base_property_edit import (
    BasePropertyEdit,
    PropertyEditContext,
)


class FloatSlidePropertyEdit(BasePropertyEdit[float]):

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        context: PropertyEditContext,
        label_width: int,
        min_value: float = 0.0,
        max_value: float = 1.0,
    ):
        super().__init__(parent, context)

        self._min_value = min_value
        self._max_value = max_value
        self._slider_range = 1000

        root_layout = QtWidgets.QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(4)

        label = self._create_label(label_width)

        slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        slider.setMinimum(0)
        slider.setMaximum(self._slider_range)
        slider.setValue(self._value_to_slider(context.prop.value()))
        slider.setTracking(True)
        slider.valueChanged.connect(self._on_slider_changed)

        editor = FloatEdit(is_limited=True, min_value=self._min_value, max_value=self._max_value)
        editor.set_value(context.prop.value())
        editor.on_value_changed = self._on_editor_value_changed
        editor.on_start_drag = self._on_start_drag
        editor.on_stop_drag = self._on_stop_drag
        editor.setStyleSheet(self.base_style)
        editor.setMaximumWidth(80)

        root_layout.addWidget(label)
        root_layout.addWidget(slider, stretch=1)
        root_layout.addWidget(editor)

        FontService().bind_widget_font(editor, "property_edit")

        self._slider = slider
        self._editor = editor
        self._block_events = False
        self.in_dragging = False
        self.on_value_changed: Callable | None = None

    def _slider_to_value(self, slider_pos: int) -> float:
        ratio = slider_pos / self._slider_range
        return self._min_value + ratio * (self._max_value - self._min_value)

    def _value_to_slider(self, value: float) -> int:
        clamped = max(self._min_value, min(value, self._max_value))
        ratio = (clamped - self._min_value) / (self._max_value - self._min_value)
        return int(round(ratio * self._slider_range))

    @override
    def set_value(self, value: float):
        self._block_events = True

        self.context.prop.set_value(value)
        self._editor.set_value(value)
        self._slider.setValue(self._value_to_slider(value))

        self._block_events = False

        if self.on_value_changed is not None:
            self.on_value_changed()

    @override
    def set_read_only(self, read_only: bool):
        self._editor.setReadOnly(read_only)
        self._slider.setEnabled(not read_only)

    def _on_slider_changed(self, slider_pos: int):
        if self._block_events:
            return

        value = self._slider_to_value(slider_pos)

        self._block_events = True
        self.context.prop.set_value(value)
        self._editor.set_value(value)
        self._block_events = False

        undo = not self.in_dragging
        self._do_set_value(value, undo)

        if self.on_value_changed is not None:
            self.on_value_changed()

    async def _on_editor_value_changed(self):
        if self._block_events:
            return

        value = self._editor.value()
        old_value = self.context.prop.value()
        self.context.prop.set_value(value)

        self._block_events = True
        self._slider.setValue(self._value_to_slider(value))
        self._block_events = False

        undo = not self.in_dragging
        await SceneEditRequestBus().set_property(
            property_key=self.context.key,
            value=value,
            undo=undo,
            old_value=old_value,
            source="ui",
        )

        if self.on_value_changed is not None:
            self.on_value_changed()

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
