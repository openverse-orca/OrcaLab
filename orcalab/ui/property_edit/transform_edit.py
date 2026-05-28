from typing import List, override
from PySide6 import QtWidgets

from orcalab.actor import BaseActor
from orcalab.application_util import get_local_scene
from orcalab.path import Path
from orcalab.scene_edit_bus import (
    SceneEditNotification,
    SceneEditNotificationBus,
)
from orcalab.ui.collapsible.collapsible_section import CollapsibleSection
from orcalab.ui.property_edit.transform_content import TransformContent
from orcalab.ui.styled_widget import StyledWidget

from orcalab.math import Transform

from orcalab.perf_log import perf_log


class TransformEdit(StyledWidget, SceneEditNotification):

    def connect_buses(self):
        perf_log(f"TransformEdit.connect_buses: actor={self._actor_path}, id={id(self)}", feature="TRACE_LIFECYCLE")
        SceneEditNotificationBus.connect(self)

    def disconnect_buses(self):
        perf_log(f"TransformEdit.disconnect_buses: actor={self._actor_path}, id={id(self)}", feature="TRACE_LIFECYCLE")
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

        self._transform_content: TransformContent | None = None

        self._section = CollapsibleSection(
            parent=self,
            title="Transform",
            badge=actor_path.string(),
            collapsed=False,
            content_factory=lambda: self._create_content(label_width),
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._section)

    def _create_content(self, label_width: int) -> TransformContent:
        self._transform_content = TransformContent(self, self._actor, label_width)
        return self._transform_content

    def expand(self):
        self._section.expand()

    def collapse(self):
        self._section.collapse()

    def toggle_collapse(self):
        self._section.toggle_collapse()

    def set_transform(self, transform: Transform):
        if self._transform_content is not None:
            self._transform_content.set_transform(transform)

    @override
    async def on_transforms_changed(
        self,
        actor_paths: List[Path],
        old_transforms: List[Transform],
        new_transforms: List[Transform],
        source: str,
    ) -> None:
        perf_log(f"TransformEdit.on_transforms_changed: actor={self._actor_path}, id={id(self)}, source={source}, content={self._transform_content is not None}", feature="TRACE_LIFECYCLE")

        if self._actor is None:
            return

        if source == "ui":
            return

        for path, new_transform in zip(actor_paths, new_transforms):
            if self._actor_path == path:
                perf_log(f"TransformEdit.on_transforms_changed: calling set_transform for actor={self._actor_path}, content_alive={self._transform_content is not None}", feature="TRACE_LIFECYCLE")
                self.set_transform(new_transform)
                break
