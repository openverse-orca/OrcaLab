from typing import Any, List
from typing_extensions import override
from PySide6 import QtWidgets

from orcalab.actor import BaseActor
from orcalab.actor_property import (
    ActorPropertyKey,
    ActorPropertyGroup,
    PropertyData,
)
from orcalab.application_util import get_local_scene
from orcalab.transform import Transform, as_euler
from orcalab.path import Path
from orcalab.perf_log import perf_timer
from orcalab.scene_edit_bus import (
    SceneEditNotification,
    SceneEditNotificationBus,
)
from orcalab.ui.collapsible.collapsible_section import CollapsibleSection
from orcalab.ui.property_edit.base_property_edit import BasePropertyEdit
from orcalab.ui.property_edit.property_group_content import (
    create_property_group_content,
)
from orcalab.ui.styled_widget import StyledWidget


class PropertyGroupEdit(StyledWidget, SceneEditNotification):

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        actor: BaseActor,
        group: ActorPropertyGroup,
        label_width: int,
        collapsed: bool = False,
    ):
        super().__init__(parent)

        self._actor = actor
        self._group = group
        self._label_width = label_width

        scene = get_local_scene()
        actor_path = scene.get_actor_path(actor)
        assert actor_path is not None
        self._actor_path = actor_path

        root_entity_path = self._actor.entity_root.root_entity_info.entity_path
        self._is_actor_root_entity = group.entity_path == root_entity_path

        self._property_edits: List[BasePropertyEdit] = []

        with perf_timer(f"property_group_edit.init({group.name})", feature="PROPERTY"):
            self._section = CollapsibleSection(
                parent=self,
                title=group.name,
                badge=group.hint,
                collapsed=collapsed,
                content_factory=lambda: self._create_content(),
            )

            layout = QtWidgets.QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            layout.addWidget(self._section)

    def _create_content(self) -> QtWidgets.QWidget:
        with perf_timer(
            f"PropertyGroupEdit._create_content({self._group.name})", feature="PROPERTY"
        ):
            content = create_property_group_content(
                parent=self,
                actor=self._actor,
                actor_path=self._actor_path,
                group=self._group,
                label_width=self._label_width,
                property_edits=self._property_edits,
                collapsed=False,
            )
            return content

    def connect_buses(self):
        SceneEditNotificationBus.connect(self)

    def disconnect_buses(self):
        SceneEditNotificationBus.disconnect(self)

    #
    # SceneEditNotificationBus overrides
    #

    def _compute_new_path(self, renamed_path: Path, new_name: str) -> Path | None:
        parent = renamed_path.parent()
        if parent is None:
            return None
        new_renamed = parent / new_name
        if self._actor_path == renamed_path:
            return new_renamed
        if self._actor_path.is_descendant_of(renamed_path):
            suffix = self._actor_path.string()[len(renamed_path.string()) :]
            return Path(new_renamed.string() + suffix)
        return None

    @override
    async def on_actor_renamed(self, actor_path: Path, new_name: str, source: str):
        new_path = self._compute_new_path(actor_path, new_name)
        if new_path is None:
            return

        self._actor_path = new_path
        for edit in self._property_edits:
            edit.context.actor_path = new_path
            edit.context.key.actor_path = new_path

    @override
    async def on_properties_changed(
        self,
        property_keys: list[ActorPropertyKey],
        values: list[Any | PropertyData],
        source: str,
    ):
        if source == "ui":
            return

        for key, value in zip(property_keys, values):
            if key.actor_path != self._actor_path:
                continue
            if key.entity_path != self._group.entity_path:
                continue
            if key.component_type_id != self._group.component_type_id:
                continue
            if key.component_type_index != self._group.component_type_index:
                continue

            for edit in self._property_edits:
                if edit.context.prop.name() == key.property_name:
                    if isinstance(value, PropertyData):
                        edit.set_value(value.value)
                        edit.set_base_value(value.base_value)
                        edit.set_read_only(value.read_only)
                    else:
                        edit.set_value(value)

    @override
    async def on_transforms_changed(
        self,
        actor_paths: List[Path],
        old_transforms: List[Transform],
        new_transforms: List[Transform],
        source: str,
    ) -> None:
        if source == "ui":
            return

        if self._group.component_type_id != "{22B10178-39B6-4C12-BB37-77DB45FDD3B6}":
            return

        if not self._is_actor_root_entity:
            return

        for actor_path, new_transform in zip(actor_paths, new_transforms):
            if actor_path != self._actor_path:
                continue

            self._set_named_property_value("translate.x", new_transform.position[0])
            self._set_named_property_value("translate.y", new_transform.position[1])
            self._set_named_property_value("translate.z", new_transform.position[2])
            angles = as_euler(new_transform.rotation, "xyz", degrees=True)
            self._set_named_property_value("rotate.x", angles[0])
            self._set_named_property_value("rotate.y", angles[1])
            self._set_named_property_value("rotate.z", angles[2])
            self._set_named_property_value("uniformScale", new_transform.scale)

    def _set_named_property_value(self, name: str, value: Any):
        for edit in self._property_edits:
            if edit.context.prop.name() == name:
                edit.set_value(value)

    def expand(self):
        self._section.expand()

    def collapse(self):
        self._section.collapse()

    def toggle_collapse(self):
        self._section.toggle_collapse()

    def set_read_only(self, read_only: bool):
        for prop in self._group.properties:
            prop.set_read_only(read_only)
        for edit in self._property_edits:
            edit.set_read_only(read_only)
