import asyncio
from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.actor import BaseActor
from orcalab.actor_property import (
    ActorProperty,
    ActorPropertyGroup,
    ActorPropertyKey,
    StructPropertyGroup,
)
from orcalab.path import Path
from orcalab.scene_edit_bus import SceneEditRequestBus
from orcalab.ui.property_edit.base_property_edit import BasePropertyEdit, PropertyEditContext
from orcalab.ui.property_edit.float_slide_property_edit import FloatSlidePropertyEdit
from orcalab.ui.fonts.font_service import FontService
from orcalab.ui.styled_widget import StyledWidget


class ColorPropertyEdit(StyledWidget):
    COLOR_CHANNEL_NAMES = {"r", "g", "b", "a"}

    def __init__(
        self,
        parent: QtWidgets.QWidget,
        struct_group: StructPropertyGroup,
        actor: BaseActor,
        actor_path: Path,
        group: ActorPropertyGroup,
        label_width: int,
        property_edits: list[BasePropertyEdit],
    ):
        super().__init__(parent)

        self._actor = actor
        self._actor_path = actor_path
        self._group = group
        self._struct_group = struct_group

        self._channels: dict[str, ActorProperty] = {}
        self._channel_edits: dict[str, FloatSlidePropertyEdit] = {}
        for prop in struct_group.properties:
            last_seg = (
                prop.name().rsplit(".", 1)[-1] if "." in prop.name() else prop.name()
            )
            if last_seg in self.COLOR_CHANNEL_NAMES:
                self._channels[last_seg] = prop

        self._build_ui(label_width, actor, actor_path, group, property_edits)

    def _build_ui(
        self,
        label_width: int,
        actor: BaseActor,
        actor_path: Path,
        group: ActorPropertyGroup,
        property_edits: list[BasePropertyEdit],
    ):
        root_layout = QtWidgets.QHBoxLayout(self)
        root_layout.setContentsMargins(0, 2, 4, 2)
        root_layout.setSpacing(4)

        self._preview_btn = QtWidgets.QPushButton()
        self._preview_btn.setFixedSize(24, 24)
        self._preview_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._preview_btn.clicked.connect(self._on_color_button_clicked)
        root_layout.addWidget(self._preview_btn)

        channels_widget = QtWidgets.QWidget()
        channels_layout = QtWidgets.QVBoxLayout(channels_widget)
        channels_layout.setContentsMargins(0, 0, 0, 0)
        channels_layout.setSpacing(0)

        compact_label_width = FontService().indent_unit_px(14)
        for ch_name in ("r", "g", "b", "a"):
            prop = self._channels.get(ch_name)
            if prop is None:
                continue
            key = ActorPropertyKey(
                actor_path=actor_path,
                entity_id=group.entity_id,
                entity_path=group.entity_path,
                component_type_id=group.component_type_id,
                component_type_index=group.component_type_index,
                property_name=prop.name(),
                property_type=prop.value_type(),
            )
            context = PropertyEditContext(
                actor=actor, actor_path=actor_path, group=group, prop=prop, key=key
            )
            editor = FloatSlidePropertyEdit(
                self, context, compact_label_width, min_value=0.0, max_value=1.0
            )
            editor.on_value_changed = self._update_preview_button
            self._channel_edits[ch_name] = editor
            property_edits.append(editor)
            channels_layout.addWidget(editor)

        root_layout.addWidget(channels_widget, stretch=1)

        self._update_preview_button()

    def _read_current_color(self) -> QtGui.QColor:
        r_edit = self._channel_edits.get("r")
        g_edit = self._channel_edits.get("g")
        b_edit = self._channel_edits.get("b")
        a_edit = self._channel_edits.get("a")
        return QtGui.QColor.fromRgbF(
            r_edit.context.prop.value() if r_edit else 0.0,
            g_edit.context.prop.value() if g_edit else 0.0,
            b_edit.context.prop.value() if b_edit else 0.0,
            a_edit.context.prop.value() if a_edit else 1.0,
        )

    def _update_preview_button(self):
        hex_color = self._read_current_color().name()
        self._preview_btn.setStyleSheet(
            f"QPushButton {{ background-color: {hex_color}; "
            f"border: 1px solid #555; border-radius: 2px; }}"
        )


    def _on_color_button_clicked(self):
        current = self._read_current_color()
        color = QtWidgets.QColorDialog.getColor(
            initial=current,
            parent=self,
            title="Select Color",
            options=QtWidgets.QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if color.isValid():
            self._apply_color(color)

    def _apply_color(self, new_color: QtGui.QColor):
        r_val = new_color.redF()
        g_val = new_color.greenF()
        b_val = new_color.blueF()
        a_val = new_color.alphaF()

        channels_in_order = [
            ("r", r_val),
            ("g", g_val),
            ("b", b_val),
            ("a", a_val),
        ]

        keys: list[ActorPropertyKey] = []
        values: list[float] = []
        old_values: list[float] = []
        for ch_name, ch_val in channels_in_order:
            prop = self._channels.get(ch_name)
            if prop is None:
                continue
            key = ActorPropertyKey(
                actor_path=self._actor_path,
                entity_id=self._group.entity_id,
                entity_path=self._group.entity_path,
                component_type_id=self._group.component_type_id,
                component_type_index=self._group.component_type_index,
                property_name=prop.name(),
                property_type=prop.value_type(),
            )
            old_values.append(prop.value())
            keys.append(key)
            values.append(ch_val)

        for ch_name, ch_val in channels_in_order:
            edit = self._channel_edits.get(ch_name)
            if edit is not None:
                edit.set_value(ch_val)

        asyncio.create_task(SceneEditRequestBus().set_properties(
                property_keys=keys,
                values=values,
                undo=True,
                old_values=old_values,
                source="panel",
            )
        )
