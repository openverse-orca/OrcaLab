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
    ):
        super().__init__(parent)

        self._actor = actor
        self._actor_path = actor_path
        self._group = group
        self._struct_group = struct_group

        self._channels: dict[str, ActorProperty] = {}
        for prop in struct_group.properties:
            last_seg = prop.name().rsplit(".", 1)[-1] if "." in prop.name() else prop.name()
            if last_seg in self.COLOR_CHANNEL_NAMES:
                self._channels[last_seg] = prop

        self._channel_keys: dict[str, ActorPropertyKey] = {}
        for ch_name, prop in self._channels.items():
            self._channel_keys[ch_name] = ActorPropertyKey(
                actor_path, group.prefix, prop.name(),
                prop.value_type(),
                entity_id=group.entity_id,
                component_type=group.component_type_id,
            )

        self._build_ui(label_width)
        self.set_value_from_props()

    def _build_ui(self, label_width: int):
        root_layout = QtWidgets.QHBoxLayout(self)
        root_layout.setContentsMargins(0, 2, 4, 2)
        root_layout.setSpacing(6)

        label = self._create_label(label_width)
        root_layout.addWidget(label)

        self._preview_btn = QtWidgets.QPushButton()
        self._preview_btn.setFixedSize(24, 24)
        self._preview_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._preview_btn.clicked.connect(self._on_color_button_clicked)
        root_layout.addWidget(self._preview_btn)

        self._value_label = QtWidgets.QLabel()
        FontService().bind_widget_font(self._value_label, 'property_edit')
        root_layout.addWidget(self._value_label)

        root_layout.addStretch()

    def _create_label(self, label_width: int) -> QtWidgets.QLabel:
        display_name = self._struct_group.display_name
        label = QtWidgets.QLabel(display_name)
        label.setMinimumWidth(label_width)
        label.setMaximumWidth(label_width * 2)
        label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        FontService().bind_widget_font(label, 'property_edit')
        return label

    def _read_current_color(self) -> QtGui.QColor:
        r = self._channels.get("r")
        g = self._channels.get("g")
        b = self._channels.get("b")
        a = self._channels.get("a")
        return QtGui.QColor.fromRgbF(
            r.value() if r else 0.0,
            g.value() if g else 0.0,
            b.value() if b else 0.0,
            a.value() if a else 1.0,
        )

    def _update_preview_button(self, color: QtGui.QColor):
        hex_color = color.name()
        self._preview_btn.setStyleSheet(
            f"QPushButton {{ background-color: {hex_color}; "
            f"border: 1px solid #555; border-radius: 2px; }}"
        )

    def _update_value_label(self, color: QtGui.QColor):
        self._value_label.setText(
            f"R:{color.redF():.2f} G:{color.greenF():.2f} "
            f"B:{color.blueF():.2f} A:{color.alphaF():.2f}"
        )

    def set_value_from_props(self):
        c = self._read_current_color()
        self._update_preview_button(c)
        self._update_value_label(c)

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

        if "r" in self._channels:
            self._channels["r"].set_value(r_val)
        if "g" in self._channels:
            self._channels["g"].set_value(g_val)
        if "b" in self._channels:
            self._channels["b"].set_value(b_val)
        if "a" in self._channels:
            self._channels["a"].set_value(a_val)

        self._commit_color_change(r_val, g_val, b_val, a_val)
        self._update_preview_button(new_color)
        self._update_value_label(new_color)

    def _commit_color_change(
        self, r_val: float, g_val: float, b_val: float, a_val: float
    ):
        asyncio.create_task(
            self._commit_color_change_async(r_val, g_val, b_val, a_val)
        )

    async def _commit_color_change_async(
        self, r_val: float, g_val: float, b_val: float, a_val: float
    ):
        bus = SceneEditRequestBus()

        r_key = self._channel_keys.get("r")
        if r_key:
            bus.start_change_property(r_key)

        channels_in_order = [
            ("r", r_val),
            ("g", g_val),
            ("b", b_val),
            ("a", a_val),
        ]
        last_idx = len(channels_in_order) - 1
        for idx, (ch_name, ch_val) in enumerate(channels_in_order):
            key = self._channel_keys.get(ch_name)
            if key is None:
                continue
            is_last = (idx == last_idx)
            await bus.set_property(key, ch_val, undo=is_last, source="ui")

        if r_key:
            bus.end_change_property(r_key)