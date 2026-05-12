from PySide6 import QtCore, QtWidgets

from orcalab.actor import BaseActor
from orcalab.math import Transform, as_euler
from orcalab.pyside_util import connect
from orcalab.scene_edit_bus import SceneEditRequestBus
from orcalab.ui.collapsible.collapsible_section import CollapsibleSection
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
        indent_unit = FontService().indent_unit_px(20)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Position section
        self._pos_x = FloatEdit()
        self._pos_y = FloatEdit()
        self._pos_z = FloatEdit()
        self._connect_edits([self._pos_x, self._pos_y, self._pos_z])
        pos_indent = 2 * indent_unit
        pos_section = CollapsibleSection(
            parent=self, title="Position", collapsed=False, indent_level=1,
            content_factory=lambda: self._create_horizontal_row([
                ("X", self._pos_x), ("Y", self._pos_y), ("Z", self._pos_z),
            ], indent=pos_indent),
        )
        layout.addWidget(pos_section)

        # Rotation section
        self._rot_x = FloatEdit(step=1.0)
        self._rot_y = FloatEdit(step=1.0)
        self._rot_z = FloatEdit(step=1.0)
        self._connect_edits([self._rot_x, self._rot_y, self._rot_z])
        rot_indent = 2 * indent_unit
        rot_section = CollapsibleSection(
            parent=self, title="Rotation", collapsed=False, indent_level=1,
            content_factory=lambda: self._create_horizontal_row([
                ("X", self._rot_x), ("Y", self._rot_y), ("Z", self._rot_z),
            ], indent=rot_indent),
        )
        layout.addWidget(rot_section)

        # Scale row
        self._scale_uniform = FloatEdit()
        self._connect_edits([self._scale_uniform])
        scale_row = self._create_scale_row(indent_unit)
        layout.addWidget(scale_row)

        self._block_signals = True
        self.set_transform(actor.transform)
        self._block_signals = False

    def _connect_edits(self, edits):
        for edit in edits:
            edit.setStyleSheet(self._property_style_sheet)
            FontService().bind_widget_font(edit, 'property_edit')
            connect(edit.value_changed, self._on_value_changed)
            connect(edit.start_drag, self._on_start_drag)
            connect(edit.stop_drag, self._on_stop_drag)

    def _create_horizontal_row(self, items, indent=0):
        row = QtWidgets.QWidget()
        row_layout = QtWidgets.QHBoxLayout(row)
        row_layout.setContentsMargins(indent, 0, 0, 0)
        row_layout.setSpacing(8)
        for label_text, edit in items:
            sub_layout = QtWidgets.QHBoxLayout()
            sub_layout.setContentsMargins(0, 0, 0, 0)
            sub_layout.setSpacing(4)
            label = QtWidgets.QLabel(label_text)
            label.setFixedWidth(20)
            label.setAlignment(
                QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
            )
            FontService().bind_widget_font(label, 'property_edit')
            sub_layout.addWidget(label)
            sub_layout.addWidget(edit, 1)
            row_layout.addLayout(sub_layout)
        row_layout.addStretch()
        return row

    def _create_scale_row(self, indent_unit):
        row = QtWidgets.QWidget()
        row_layout = QtWidgets.QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)
        row_layout.addSpacing(indent_unit)
        label = QtWidgets.QLabel("Uniform Scale")
        label.setFixedWidth(self._label_width)
        label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        FontService().bind_widget_font(label, 'property_edit')
        row_layout.addWidget(label)
        row_layout.addWidget(self._scale_uniform, 1)
        return row

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