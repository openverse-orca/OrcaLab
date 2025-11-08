from typing import override
from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.actor import BaseActor, GroupActor, AssetActor
from orcalab.math import Transform
from orcalab.pyside_util import connect
from orcalab.ui.transform_edit import TransformEdit

from orcalab.scene_edit_bus import (
    SceneEditNotification,
    SceneEditNotificationBus,
    SceneEditRequestBus,
    get_actor_and_path,
)
from orcalab.undo_service.command import TransformCommand
from orcalab.undo_service.undo_service_bus import UndoRequestBus


class ActorEditor(QtWidgets.QWidget, SceneEditNotification):
    # transform_changed = QtCore.Signal()
    # start_drag = QtCore.Signal()
    # stop_drag = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._layout = QtWidgets.QVBoxLayout()
        self.setLayout(self._layout)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )

        self._actor: BaseActor | None = None
        self._transform_edit: TransformEdit | None = None

        self._dragging = False
        self._old_transform: Transform | None = None

        self._refresh()

    def connect_bus(self):
        SceneEditNotificationBus.connect(self)

    def disconnect_bus(self):
        SceneEditNotificationBus.disconnect(self)

    @property
    def actor(self) -> BaseActor | None:
        return self._actor

    @actor.setter
    def actor(self, actor: BaseActor | None):
        if self._actor == actor:
            return

        self._actor = actor
        self._refresh()

    def _clear_layout(self, layout=None):
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
            label = QtWidgets.QLabel("No actor selected")
            label.setAlignment(
                QtCore.Qt.AlignmentFlag.AlignCenter
                | QtCore.Qt.AlignmentFlag.AlignVCenter
            )
            self._layout.addWidget(label)
            return

        label = QtWidgets.QLabel(f"Actor: {self._actor.name}")
        self._layout.addWidget(label)

        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self._layout.addWidget(line)

        transform_edit = TransformEdit()
        connect(transform_edit.value_changed, self._on_transform_changed)
        connect(transform_edit.start_drag, self._on_start_drag)
        connect(transform_edit.stop_drag, self._on_stop_drag)

        transform_edit.set_transform(self._actor.transform)

        # transform_edit.set_transform(self._actor.transform)
        self._transform_edit = transform_edit
        self._layout.addWidget(transform_edit)

        self._layout.addSpacing(10)

        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self._layout.addWidget(line)

        if isinstance(self._actor, AssetActor):
            label = QtWidgets.QLabel(f"Asset Name {self._actor.asset_path}")
            self._layout.addWidget(label)

        self._layout.addStretch(1)

    async def _on_transform_changed(self):
        undo = not self._dragging
        await SceneEditRequestBus().set_transform(
            self._actor,
            self._transform_edit.transform,
            local=True,
            undo=undo,
            source="actor_editor",
        )

    async def _on_start_drag(self):
        if self._dragging or self._old_transform is not None:
            raise RuntimeError("A dragging is already in progress")

        self._dragging = True
        self._old_transform = self._actor.transform

    async def _on_stop_drag(self):
        if not self._dragging or self._old_transform is None:
            raise RuntimeError("No dragging in progress")

        actor, actor_path = get_actor_and_path(self._actor)

        command = TransformCommand()
        command.actor_path = actor_path
        command.old_transform = self._old_transform
        command.new_transform = self._actor.transform
        command.local = True
        UndoRequestBus().add_command(command)

        self._dragging = False
        self._old_transform = None

    @property
    def transform(self):
        if self._transform_edit is None:
            return Transform()
        return self._transform_edit.transform

    @override
    async def on_selection_changed(self, old_selection, new_selection, source=""):
        if new_selection == []:
            if self._actor is not None:
                self.actor = None
        else:
            actor, actor_path = get_actor_and_path(new_selection[0])
            if actor != self._actor:
                self.actor = actor

    @override
    async def on_transform_changed(self, actor_path, transform, local, source):
        if self._actor is None:
            return

        if source == "actor_editor":
            return

        current_actor, current_actor_path = get_actor_and_path(self._actor)
        if current_actor_path != actor_path:
            return

        self._transform_edit.set_transform(transform)


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)

    actor = GroupActor("group1")

    editor = ActorEditor()
    editor.resize(400, 50)
    editor.show()

    editor.actor = actor

    def cb():
        print("actor transform changed")
        print(editor.transform)

    editor.transform_changed.connect(cb)

    sys.exit(app.exec())
