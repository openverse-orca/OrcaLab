from PySide6 import QtCore, QtWidgets

from orcalab.actor import BaseActor
from orcalab.math import Transform, as_euler
from orcalab.pyside_util import connect
from orcalab.scene_edit_bus import SceneEditRequestBus
from orcalab.ui.edit.float_edit import FloatEdit
from orcalab.ui.fonts.font_service import FontService
from orcalab.ui.property_edit.base_property_edit import get_property_edit_style_sheet
from orcalab.ui.styled_widget import StyledWidget

import numpy as np
from scipy.spatial.transform import Rotation


class TransformContent(StyledWidget):

    value_changed = QtCore.Signal()
    start_drag = QtCore.Signal()
    stop_drag = QtCore.Signal()

    def __init__(
        self,
        parent: QtWidgets.QWidget,
        actor: BaseActor,
        label_width: int,
    ):
        super().__init__(parent)

        self._actor = actor
        self._label_width = label_width
        self._dragging = False
        self._block_signals = False

        self._property_style_sheet = get_property_edit_style_sheet()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._pos_x = self._add_line("Position  X", FloatEdit(), layout)
        self._pos_y = self._add_line("Y", FloatEdit(), layout)
        self._pos_z = self._add_line("Z", FloatEdit(), layout)

        self._rot_x = self._add_line("Rotation  X", FloatEdit(step=1.0), layout)
        self._rot_y = self._add_line("Y", FloatEdit(step=1.0), layout)
        self._rot_z = self._add_line("Z", FloatEdit(step=1.0), layout)

        self._scale_uniform = self._add_line("Uniform Scale", FloatEdit(), layout)

        self._block_signals = True
        self.set_transform(actor.transform)
        self._block_signals = False

    def _add_line(self, label: str, widget: FloatEdit, layout: QtWidgets.QVBoxLayout):
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        layout.addLayout(row)

        label_widget = QtWidgets.QLabel(label)
        label_widget.setFixedWidth(self._label_width)
        label_widget.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        FontService().bind_widget_font(label_widget, 'property_edit')
        row.addWidget(label_widget)
        row.addWidget(widget, 1)

        widget.setStyleSheet(self._property_style_sheet)
        FontService().bind_widget_font(widget, 'property_edit')
        connect(widget.value_changed, self._on_value_changed)
        connect(widget.start_drag, self._on_start_drag)
        connect(widget.stop_drag, self._on_stop_drag)

        return widget

    async def _on_value_changed(self):
        if self._block_signals:
            return
        undo = not self._dragging
        await SceneEditRequestBus().set_transform(
            self._actor,
            self.get_transform(),
            local=True,
            undo=undo,
            source="ui",
        )

    async def _on_start_drag(self):
        if self._dragging:
            raise RuntimeError("A dragging is already in progress")
        self._dragging = True
        await SceneEditRequestBus().start_change_transform_batch([self._actor])

    async def _on_stop_drag(self):
        if not self._dragging:
            raise RuntimeError("No dragging in progress")
        await SceneEditRequestBus().end_change_transform_batch([self._actor])
        self._dragging = False

    def get_transform(self):
        transform = Transform()
        transform.position = np.array(
            [self._pos_x.value(), self._pos_y.value(), self._pos_z.value()],
            dtype=np.float64,
        )
        angles = [self._rot_x.value(), self._rot_y.value(), self._rot_z.value()]
        r = Rotation.from_euler("xyz", angles, degrees=True)
        quat = r.as_quat(scalar_first=True)
        transform.rotation = quat
        transform.scale = self._scale_uniform.value()
        return transform

    def set_transform(self, transform: Transform):
        self._pos_x.set_value(transform.position[0])
        self._pos_y.set_value(transform.position[1])
        self._pos_z.set_value(transform.position[2])
        angles = as_euler(transform.rotation, "xyz", degrees=True)
        self._rot_x.set_value(angles[0])
        self._rot_y.set_value(angles[1])
        self._rot_z.set_value(angles[2])
        self._scale_uniform.set_value(transform.scale)
