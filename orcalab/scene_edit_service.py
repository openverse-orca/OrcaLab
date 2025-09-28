from copy import deepcopy
from typing import List, override
from orcalab.actor import BaseActor, GroupActor
from orcalab.local_scene import LocalScene
from orcalab.path import Path
from orcalab.scene_edit_bus import (
    SceneEditNotificationBus,
    SceneEditRequestBus,
    SceneEditRequest,
)

from orcalab.undo_service.command import (
    CommandGroup,
    CreateGroupCommand,
    DeleteActorCommand,
    RenameActorCommand,
    ReparentActorCommand,
    SelectionCommand,
    TransformCommand,
)

from orcalab.undo_service.undo_service_bus import UndoRequestBus


class SceneEditService(SceneEditRequest):

    def __init__(self, local_scene: LocalScene):
        self.local_scene = local_scene

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
    async def set_transform(self, actor, transform, local, undo=True, source=""):
        actor, actor_path = self.local_scene.get_actor_and_path(actor)

        if local:
            old_transform = actor.transform
            actor.transform = transform
        else:
            old_transform = actor.world_transform
            actor.world_transform = transform

        await SceneEditNotificationBus().on_transform_changed(
            actor_path, transform, local, source
        )

        if undo:
            command = TransformCommand()
            command.actor_path = actor_path
            command.old_transform = old_transform
            command.new_transform = transform
            command.local = local
            UndoRequestBus().add_command(command)

    @override
    def get_actor_and_path(self, out, actor):
        out.append(self.local_scene.get_actor_and_path(actor))

    @override
    def can_rename_actor(self, out, actor, new_name):
        out.append(self.local_scene.can_rename_actor(actor, new_name))

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

        parent_actor, parent_actor_path = self.local_scene.get_actor_and_path(
            parent_actor
        )

        bus = SceneEditNotificationBus()

        await bus.before_actor_added(actor, parent_actor_path, source)

        self.local_scene.add_actor(actor, parent_actor_path)

        await bus.on_actor_added(actor, parent_actor_path, source)

        if undo:
            command = CreateGroupCommand()
            command.path = parent_actor_path / actor.name
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
            return

        actor, actor_path = self.local_scene.get_actor_and_path(actor)

        parent_actor = actor.parent
        index = parent_actor.children.index(actor)
        assert index != -1

        command = DeleteActorCommand()
        command.actor = actor
        command.path = actor_path
        command.row = index

        bus = SceneEditNotificationBus()

        await bus.before_actor_deleted(actor_path, source)

        self.local_scene.delete_actor(actor)

        await bus.on_actor_deleted(actor_path, source)

        if undo:
            UndoRequestBus().add_command(command)

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
