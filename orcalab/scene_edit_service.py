from copy import deepcopy
from typing import Any, List, override
import logging


from orcalab.actor import BaseActor, GroupActor, AssetActor
from orcalab.actor_property import ActorPropertyKey
from orcalab.local_scene import LocalScene
from orcalab.math import Transform
from orcalab.path import Path
from orcalab.scene_edit_bus import (
    SceneEditNotificationBus,
    SceneEditRequestBus,
    SceneEditRequest,
)

from orcalab.undo_service.command import (
    CommandGroup,
    CreateGroupCommand,
    CreateActorCommand,
    DeleteActorCommand,
    PropertyChangeCommand,
    RenameActorCommand,
    ReparentActorCommand,
    SelectionCommand,
    TransformCommand,
)

from orcalab.undo_service.undo_service_bus import UndoRequestBus

logger = logging.getLogger(__name__)


class SceneEditService(SceneEditRequest):

    def __init__(self, local_scene: LocalScene):
        self.local_scene = local_scene

        # For transform change tracking
        self.actor_in_editing: Path | None = None
        self.old_local_transform: Transform | None = None
        self.old_world_transform: Transform | None = None

        # For property change tracking
        self.property_key: ActorPropertyKey | None = None
        self.old_property_value: Any = None

    def connect_bus(self):
        SceneEditRequestBus.connect(self)

    def disconnect_bus(self):
        SceneEditRequestBus.disconnect(self)

    @override
    async def set_selection(
        self,
        selection: List[Path],
        undo: bool = True,
        source: str = "",
    ) -> None:

        actors, actor_paths = self.local_scene.get_actor_and_path_list(selection)

        if actor_paths == self.local_scene.selection:
            return

        old_selection = deepcopy(self.local_scene.selection)
        self.local_scene.selection = actor_paths

        await SceneEditNotificationBus().on_selection_changed(
            old_selection, actor_paths, source
        )

        if undo:
            cmd = SelectionCommand()
            cmd.old_selection = old_selection
            cmd.new_selection = actor_paths
            UndoRequestBus().add_command(cmd)

    @override
    async def add_actor(
        self,
        actor: BaseActor,
        parent_actor: GroupActor | Path,
        undo: bool = True,
        source: str = "",
    ):
        ok, err = self.local_scene.can_add_actor(actor, parent_actor)
        if not ok:
            raise Exception(err)

        _, parent_actor_path = self.local_scene.get_actor_and_path(parent_actor)

        bus = SceneEditNotificationBus()

        await bus.before_actor_added(actor, parent_actor_path, source)

        self.local_scene.add_actor(actor, parent_actor_path)

        await bus.on_actor_added(actor, parent_actor_path, source)

        if undo:
            if isinstance(actor, AssetActor):
                command = CreateActorCommand(actor, parent_actor_path / actor.name, -1)
                UndoRequestBus().add_command(command)
            else:
                command = CreateGroupCommand(parent_actor_path / actor.name)
                UndoRequestBus().add_command(command)

    @override
    async def delete_actor(
        self,
        actor: BaseActor | Path,
        undo: bool = True,
        source: str = "",
    ):
        ok, err = self.local_scene.can_delete_actor(actor)
        if not ok:
            logger.error("Cannot delete actor: %s", err)
            return

        _actor, _actor_path = self.local_scene.get_actor_and_path(actor)

        edit_actor_paths: List[Path] = []
        self.get_editing_actor_path(edit_actor_paths)
        if _actor_path in edit_actor_paths:
            logger.error("Cannot delete actor being edited: %s", _actor_path)
            return

        parent_actor = _actor.parent
        assert isinstance(parent_actor, GroupActor)

        index = parent_actor.children.index(_actor)
        assert index != -1

        bus = SceneEditNotificationBus()

        await bus.before_actor_deleted(_actor_path, source)

        command_group = CommandGroup()
        in_selection = _actor_path in self.local_scene.selection

        if in_selection:
            deselect_command = SelectionCommand()
            deselect_command.old_selection = deepcopy(self.local_scene.selection)
            deselect_command.new_selection = deepcopy(self.local_scene.selection)
            deselect_command.new_selection.remove(_actor_path)

            await self.set_selection(deselect_command.new_selection, undo=False, source=source)
            command_group.commands.append(deselect_command)

        delete_command = DeleteActorCommand(_actor, _actor_path, index)
        command_group.commands.append(delete_command)

        self.local_scene.delete_actor(_actor)

        await bus.on_actor_deleted(_actor_path, source)

        if undo:
            UndoRequestBus().add_command(command_group)

    @override
    async def rename_actor(
        self,
        actor: BaseActor,
        new_name: str,
        undo: bool = True,
        source: str = "",
    ):
        ok, err = self.local_scene.can_rename_actor(actor, new_name)
        if not ok:
            raise Exception(err)
        
        if new_name == actor.name:
            return

        actor, actor_path = self.local_scene.get_actor_and_path(actor)

        bus = SceneEditNotificationBus()

        await bus.before_actor_renamed(actor_path, new_name, source)

        self.local_scene.rename_actor(actor, new_name)

        new_actor_path = actor_path.parent() / new_name

        command_group = CommandGroup()
        in_selection = actor_path in self.local_scene.selection

        if in_selection:
            deselect_command = SelectionCommand()
            deselect_command.old_selection = deepcopy(self.local_scene.selection)
            deselect_command.new_selection = deepcopy(self.local_scene.selection)
            deselect_command.new_selection.remove(actor_path)

            command_group.commands.append(deselect_command)

        await bus.on_actor_renamed(actor_path, new_name, source)

        rename_command = RenameActorCommand()
        rename_command.old_path = actor_path
        rename_command.new_path = new_actor_path
        command_group.commands.append(rename_command)

        if in_selection:
            select_command = SelectionCommand()
            select_command.old_selection = deepcopy(deselect_command.new_selection)
            select_command.new_selection = deepcopy(deselect_command.new_selection)
            select_command.new_selection.append(new_actor_path)
            command_group.commands.append(select_command)

        if undo:
            UndoRequestBus().add_command(command_group)

    @override
    async def reparent_actor(
        self,
        actor: BaseActor | Path,
        new_parent: BaseActor | Path,
        row: int,
        undo: bool = True,
        source: str = "",
    ):
        ok, err = self.local_scene.can_reparent_actor(actor, new_parent)
        if not ok:
            raise Exception(err)

        actor, actor_path = self.local_scene.get_actor_and_path(actor)
        new_parent, new_parent_path = self.local_scene.get_actor_and_path(new_parent)

        bus = SceneEditNotificationBus()

        await bus.before_actor_reparented(actor_path, new_parent_path, row, source)

        self.local_scene.reparent_actor(actor, new_parent, row)

        await bus.on_actor_reparented(actor_path, new_parent_path, row, source)

        if undo:
            new_parent, new_parent_path = self.local_scene.get_actor_and_path(
                new_parent
            )
            old_parent = actor.parent
            old_index = old_parent.children.index(actor)
            assert old_index != -1

            command = ReparentActorCommand()
            command.old_path = actor_path
            command.old_row = old_index
            command.new_path = new_parent_path / actor.name
            command.new_row = row

            UndoRequestBus().add_command(command)

    @override
    async def set_property(
        self,
        property_key: ActorPropertyKey,
        value: Any,
        undo: bool = True,
        source: str = "",
    ):
        # Note: Property is already modified by ui before calling this method.
        # Currently, property will not sync from remote to python.

        bus = SceneEditNotificationBus()

        await bus.on_property_changed(property_key, value, source)

        if undo:
            actor, group, prop = self.local_scene.parse_property_key(property_key)
            if self.old_property_value is None:
                old_value = prop.value()
            else:
                old_value = self.old_property_value

            command = PropertyChangeCommand(property_key, old_value, value)
            UndoRequestBus().add_command(command)

    @override
    def start_change_property(self, property_key: ActorPropertyKey):
        assert self.old_property_value is None and self.property_key is None

        actor, group, prop = self.local_scene.parse_property_key(property_key)
        self.old_property_value = prop.value()
        self.property_key = property_key

    @override
    def end_change_property(self, property_key: ActorPropertyKey):
        assert self.old_property_value is not None and self.property_key == property_key

        self.old_property_value = None
        self.property_key = None

    @override
    def start_change_transform(self, actor: BaseActor | Path):
        _actor, _actor_path = self.local_scene.get_actor_and_path(actor)

        assert self.actor_in_editing is None

        self.actor_in_editing = _actor_path
        self.old_local_transform = _actor.transform
        self.old_world_transform = _actor.world_transform

    @override
    def end_change_transform(self, actor: BaseActor | Path):
        _, _actor_path = self.local_scene.get_actor_and_path(actor)

        assert self.actor_in_editing is not None
        assert self.actor_in_editing == _actor_path

        self.actor_in_editing = None
        self.old_local_transform = None
        self.old_world_transform = None

    @override
    async def set_transform(self, actor, transform, local, undo=True, source=""):
        _actor, _actor_path = self.local_scene.get_actor_and_path(actor)
        if local:
            if self.old_local_transform is None:
                old_transform = _actor.transform
            else:
                assert self.actor_in_editing == _actor_path
                old_transform = self.old_local_transform

            _actor.transform = transform
        else:
            if self.old_world_transform is None:
                old_transform = _actor.world_transform
            else:
                assert self.actor_in_editing == _actor_path
                old_transform = self.old_world_transform

            _actor.world_transform = transform

        # Notify.
        await SceneEditNotificationBus().on_transform_changed(
            _actor_path,
            transform,
            local,
            source,
        )

        if undo:
            command = TransformCommand()
            command.actor_path = _actor_path
            command.old_transform = old_transform
            command.new_transform = transform
            command.local = local
            UndoRequestBus().add_command(command)

    @override
    def get_editing_actor_path(self, out: List[Path]):
        if self.actor_in_editing is not None:
            out.append(self.actor_in_editing)

        if self.property_key is not None:
            out.append(self.property_key.actor_path)
