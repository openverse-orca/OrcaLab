import asyncio
from typing import override
from PySide6 import QtCore, QtWidgets, QtGui

import numpy as np

from orcalab.actor import BaseActor
from orcalab.application_util import get_local_scene
from orcalab.pyside_util import connect
from orcalab.scene_edit_bus import (
    SceneEditNotification,
    SceneEditNotificationBus,
    SceneEditRequestBus,
)
from orcalab.ui.edit.float_edit import FloatEdit
from orcalab.math import Transform, as_euler

from scipy.spatial.transform import Rotation

from orcalab.ui.icon import Icon
from orcalab.ui.icon_util import make_color_svg
from orcalab.ui.property_edit.base_property_edit import get_property_edit_style_sheet
from orcalab.ui.styled_widget import StyledWidget
from orcalab.ui.theme_service import ThemeService


class TransformEditTitle(QtWidgets.QWidget):

    toggle_collapse = QtCore.Signal()

    def __init__(self, parent):
        super().__init__(parent)
        root_layout = QtWidgets.QHBoxLayout(self)
        root_layout.setContentsMargins(4, 0, 4, 0)
        root_layout.setSpacing(4)

        self.l_indicator = Icon()
        self.l_indicator.set_icon_size(16)

        l_name = QtWidgets.QLabel("Transform")

        root_layout.addWidget(
            self.l_indicator, alignment=QtCore.Qt.AlignmentFlag.AlignCenter
        )
        root_layout.addWidget(l_name)
        root_layout.addStretch()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.toggle_collapse.emit()


class TransformEdit(StyledWidget, SceneEditNotification):
    value_changed = QtCore.Signal()
    start_drag = QtCore.Signal()
    stop_drag = QtCore.Signal()

    def connect_buses(self):
        SceneEditNotificationBus.connect(self)

    def disconnect_buses(self):
        SceneEditNotificationBus.disconnect(self)

    def __init__(
        self, parent: QtWidgets.QWidget | None, actor: BaseActor, label_width: int
    ):
        super().__init__(parent)

        self._actor = actor
        local_scene = get_local_scene()
        actor_path = local_scene.get_actor_path(actor)
        assert actor_path is not None
        self._actor_path = actor_path

        self._dragging = False
        self._block_signals = False

        theme = ThemeService()
        bg_color = theme.get_color_hex("property_group_bg")
        text_color = theme.get_color("text")

        self._property_style_sheet = get_property_edit_style_sheet()
        style_sheet = f"""
            QWidget {{
                background-color: {bg_color};
                border-radius: 4px;
            }}
            """
        self.setStyleSheet(style_sheet)

        self._expand_icon = make_color_svg(":/icons/chevron_down", text_color)
        self._collapse_icon = make_color_svg(":/icons/chevron_right", text_color)

        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(4, 4, 4, 4)
        root_layout.setSpacing(4)

        self._label_width = label_width

        self._title_area = TransformEditTitle(self)
        self._title_area.setFixedHeight(24)
        self._title_area.l_indicator.set_pixmap(self._expand_icon)
        self._title_area.toggle_collapse.connect(self.toggle_collapse)

        self._content_area = QtWidgets.QWidget()
        root_layout.addWidget(self._title_area)
        root_layout.addWidget(self._content_area)

        self._content_layout = QtWidgets.QVBoxLayout(self._content_area)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(4)

        self._pos_x = self._add_line("Position  X", FloatEdit())
        self._pos_y = self._add_line("Y", FloatEdit())
        self._pos_z = self._add_line("Z", FloatEdit())

        self._rot_x = self._add_line("Rotation  X", FloatEdit(step=1.0))
        self._rot_y = self._add_line("Y", FloatEdit(step=1.0))
        self._rot_z = self._add_line("Z", FloatEdit(step=1.0))

        self._scale_uniform = self._add_line("Uniform Scale", FloatEdit())

        self._block_signals = True
        self.set_transform(actor.transform)
        self._block_signals = False

    def _add_line(self, label, widget: FloatEdit):
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._content_layout.addLayout(layout)

        label_widget = QtWidgets.QLabel(label)
        label_widget.setFixedWidth(self._label_width)
        label_widget.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(label_widget)
        layout.addWidget(widget, 1)

        widget.setStyleSheet(self._property_style_sheet)
        connect(widget.value_changed, self._on_value_changed)
        connect(widget.start_drag, self._on_start_drag)
        connect(widget.stop_drag, self._on_stop_drag)

        return widget

    async def _do_set_transform_async(self, transform: Transform, undo: bool):
        # print("Set transform:", transform, "undo =", undo)
        await SceneEditRequestBus().set_transform(
            self._actor,
            self.get_transform(),
            local=True,
            undo=undo,
            source="ui",
        )

    async def _on_value_changed(self):
        if self._block_signals:
            return

        undo = not self._dragging
        await self._do_set_transform_async(self.get_transform(), undo)

    def _on_start_drag(self):
        if self._dragging:
            raise RuntimeError("A dragging is already in progress")

        self._dragging = True
        SceneEditRequestBus().start_change_transform(self._actor)

    async def _on_stop_drag(self):
        if not self._dragging:
            raise RuntimeError("No dragging in progress")

        await self._do_set_transform_async(self.get_transform(), undo=True)
        SceneEditRequestBus().end_change_transform(self._actor)
        self._dragging = False

    def get_transform(self):
        transform = Transform()

        transform.position = np.array(
            [self._pos_x.value(), self._pos_y.value(), self._pos_z.value()],
            dtype=np.float64,
        )

        angles = [self._rot_x.value(), self._rot_y.value(), self._rot_z.value()]
        r = Rotation.from_euler(
            "xyz",
            angles,
            degrees=True,
        )
        quat = r.as_quat(scalar_first=True)
        transform.rotation = quat

        transform.scale = self._scale_uniform.value()
        return transform

    def set_transform(self, transform: Transform):

        self._pos_x.set_value(transform.position[0])
        self._pos_y.set_value(transform.position[1])
        self._pos_z.set_value(transform.position[2])

        # r = Rotation.from_quat(transform.rotation.tolist(), scalar_first=True)
        # angles = r.as_euler("xyz", degrees=True)
        angles = as_euler(transform.rotation, "xyz", degrees=True)

        self._rot_x.set_value(angles[0])
        self._rot_y.set_value(angles[1])
        self._rot_z.set_value(angles[2])

        self._scale_uniform.set_value(transform.scale)

    def expand(self):
        self._content_area.show()
        self._title_area.l_indicator.set_pixmap(self._expand_icon)

    def collapse(self):
        self._content_area.hide()
        self._title_area.l_indicator.set_pixmap(self._collapse_icon)

    def toggle_collapse(self):
        if self._content_area.isVisible():
            self.collapse()
        else:
            self.expand()

    @override
    async def on_transform_changed(self, actor_path, transform, local, source):
        if self._actor is None:
            return

        if source == "ui":
            return

        if self._actor_path != actor_path:
            return

        self.set_transform(transform)
