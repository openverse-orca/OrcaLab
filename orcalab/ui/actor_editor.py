from typing import override
from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.actor import BaseActor, GroupActor, AssetActor
from orcalab.application_util import get_local_scene
from orcalab.ui.property_edit.property_group_edit import PropertyGroupEdit
from orcalab.ui.property_edit.transform_edit import TransformEdit

from orcalab.scene_edit_bus import (
    SceneEditNotification,
    SceneEditNotificationBus,
)


class ActorEditor(QtWidgets.QWidget, SceneEditNotification):

    def __init__(self, parent=None):
        super().__init__(parent)

        self._layout = QtWidgets.QVBoxLayout()
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(4)
        self.setLayout(self._layout)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )

        self._actor: BaseActor | None = None
        self._transform_edit: TransformEdit | None = None
        self._property_edits: list[PropertyGroupEdit] = []

        self._refresh()

    def connect_bus(self):
        SceneEditNotificationBus.connect(self)

    def disconnect_bus(self):
        SceneEditNotificationBus.disconnect(self)

    def get_actor(self) -> BaseActor | None:
        return self._actor

    def set_actor(self, actor: BaseActor | None):
        if self._actor == actor:
            return

        self._actor = actor
        self._refresh()

    def _clear_layout(self, layout=None):
        for edit in self._property_edits:
            edit.disconnect_buses()
        self._property_edits.clear()

        if self._transform_edit:
            self._transform_edit.disconnect_buses()
            self._transform_edit = None

        if layout is None:
            layout = self._layout
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                w = item.widget()
                layout.removeWidget(w)
                w.setParent(None)
            elif item.layout():
                self._clear_layout(item.layout())
                layout.removeItem(item)

    def _refresh(self):
        self._clear_layout()

        if self._actor is None:
            label = QtWidgets.QLabel("没有选中任何Actor")
            label.setAlignment(
                QtCore.Qt.AlignmentFlag.AlignCenter
                | QtCore.Qt.AlignmentFlag.AlignVCenter
            )
            self._layout.addWidget(label)
            return

        label = QtWidgets.QLabel(f"Actor: {self._actor.name}")
        label.setContentsMargins(4, 4, 4, 4)
        self._layout.addWidget(label)

        label_width = 120

        self._transform_edit = TransformEdit(self, self._actor, label_width)
        self._transform_edit.connect_buses()
        self._layout.addWidget(self._transform_edit)

        if isinstance(self._actor, AssetActor):
            for property_group in self._actor.property_groups:
                edit = PropertyGroupEdit(self, self._actor, property_group, label_width)
                edit.connect_buses()
                self._property_edits.append(edit)
                self._layout.addWidget(edit)

        self._layout.addStretch(1)

    @override
    async def on_selection_changed(self, old_selection, new_selection, source=""):
        if new_selection == []:
            if self._actor is not None:
                self.set_actor(None)
        else:
            local_scene = get_local_scene()
            actor = local_scene.find_actor_by_path(new_selection[0])
            assert actor is not None
            if actor != self._actor:
                self.set_actor(actor)
