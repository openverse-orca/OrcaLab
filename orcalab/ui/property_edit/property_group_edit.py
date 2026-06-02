from typing import Any, List, override
from PySide6 import QtWidgets

from orcalab.actor import BaseActor
from orcalab.actor_property import (
    ActorPropertyKey,
    ActorPropertyGroup,
)
from orcalab.application_util import get_local_scene
from orcalab.path import Path
from orcalab.perf_log import perf_timer
from orcalab.scene_edit_bus import (
    SceneEditNotification,
    SceneEditNotificationBus,
)
from orcalab.ui.collapsible.collapsible_section import CollapsibleSection
from orcalab.ui.property_edit.base_property_edit import BasePropertyEdit
from orcalab.ui.property_edit.physical_material_edit import PhysicalMaterialEdit
from orcalab.ui.property_edit.property_group_content import create_property_group_content
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

        self._property_edits: List[BasePropertyEdit] = []
        self._physical_material_edit: PhysicalMaterialEdit | None = None

        with perf_timer(f"property_group_edit.init({group.name})", feature="PROPERTY"):
            self._section = CollapsibleSection(
                parent=self,
                title=group.display_name or group.name,
                badge=group.hint,
                collapsed=collapsed,
                content_factory=lambda: self._create_content(),
            )

            layout = QtWidgets.QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            layout.addWidget(self._section)

    def _create_content(self) -> QtWidgets.QWidget:
        with perf_timer(f"PropertyGroupEdit._create_content({self._group.name})", feature="PROPERTY"):
            content = create_property_group_content(
                parent=self,
                actor=self._actor,
                actor_path=self._actor_path,
                group=self._group,
                label_width=self._label_width,
                property_edits=self._property_edits,
                collapsed=False,
            )
            self._physical_material_edit = getattr(content, "_physical_material_edit", None)
            if self._physical_material_edit is not None:
                self._physical_material_edit.set_property_edits(self._property_edits)
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
            suffix = self._actor_path.string()[len(renamed_path.string()):]
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
    async def on_property_changed(
        self,
        property_key: ActorPropertyKey,
        value: Any,
        source: str,
    ):
        if property_key.actor_path != self._actor_path:
            return

        if property_key.group_prefix != self._group.prefix:
            return

        if source == "ui":
            return

        for edit in self._property_edits:
            if edit.context.prop.name() == property_key.property_name:
                edit.set_value(value)

        if self._physical_material_edit is not None:
            self._physical_material_edit.on_controlled_property_changed(
                property_key.property_name, value
            )

    @override
    async def on_properties_changed(
        self,
        property_keys: list,
        values: list,
        source: str,
    ):
        if source == "ui":
            return

        for key, value in zip(property_keys, values):
            if key.actor_path != self._actor_path:
                continue
            if key.group_prefix != self._group.prefix:
                continue

            for edit in self._property_edits:
                if edit.context.prop.name() == key.property_name:
                    edit.set_value(value)

        if self._physical_material_edit is not None:
            for key, value in zip(property_keys, values):
                self._physical_material_edit.on_controlled_property_changed(
                    key.property_name, value
                )

    @override
    async def on_property_read_only_changed(
        self,
        actor_path,
        group_prefix: str,
        property_name: str,
        read_only: bool,
    ):
        if actor_path != self._actor_path:
            return

        if group_prefix != self._group.prefix:
            return

        for edit in self._property_edits:
            if edit.context.prop.name() == property_name:
                edit.set_read_only(read_only)
                return

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
