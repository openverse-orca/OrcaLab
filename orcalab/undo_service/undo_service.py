import asyncio
from copy import deepcopy
from typing import override, List
import logging
from orcalab.actor import BaseActor, GroupActor, AssetActor
from orcalab.application_util import get_local_scene
from orcalab.path import Path

from orcalab.undo_service.command import (
    BaseCommand,
    CommandGroup,
    CreateActorCommand,
    CreateGroupCommand,
    DeleteActorCommand,
    PropertyChangeCommand,
    RenameActorCommand,
    ReparentActorCommand,
    SelectionCommand,
    TransformCommand,
)

from orcalab.undo_service.undo_service_bus import UndoRequest, UndoRequestBus
from orcalab.scene_edit_bus import SceneEditRequestBus

logger = logging.getLogger(__name__)


class UndoService(UndoRequest):
    def __init__(self):
        self.command_history = []
        self.command_history_index = -1
        self._in_undo_redo = False
        self._lock = asyncio.Lock()

    def connect_bus(self):
        UndoRequestBus.connect(self)

    def disconnect_bus(self):
        UndoRequestBus.disconnect(self)

    @override
    def add_command(self, command):
        if not isinstance(command, BaseCommand):
            raise TypeError("command must be an instance of BaseCommand")

        if self._in_undo_redo:
            raise Exception("Cannot add command during undo/redo operation.")

        # Remove commands after the current index
        self.command_history = self.command_history[: self.command_history_index + 1]
        self.command_history.append(command)

        self.command_history_index = self.command_history_index + 1

        logger.debug("Added command: %s", command)

    @override
    def can_undo(self, out: List[bool]):
        out.append(self.command_history_index >= 0)

    @override
    def can_redo(self, out: List[bool]):
        out.append(self.command_history_index + 1 < len(self.command_history))

    @override
    async def undo(self):
        async with self._lock:
            if self.command_history_index < 0:
                return

            command = self.command_history[self.command_history_index]
            self.command_history_index -= 1

            self._in_undo_redo = True

            await self._undo_command(command)

            self._in_undo_redo = False

    @override
    async def redo(self):
        async with self._lock:
            if self.command_history_index + 1 >= len(self.command_history):
                return

            command = self.command_history[self.command_history_index + 1]
            self.command_history_index += 1

            self._in_undo_redo = True

            await self._redo_command(command)

            self._in_undo_redo = False

    def _get_actor(self, actor_path: Path) -> BaseActor:
        local_scene = get_local_scene()
        actor = local_scene.find_actor_by_path(actor_path)
        assert actor is not None
        return actor

    async def _undo_command(self, command):
        match command:
            case CommandGroup():
                for cmd in reversed(command.commands):
                    await self._undo_command(cmd)
            case SelectionCommand():
                await SceneEditRequestBus().set_selection(
                    command.old_selection, undo=False
                )
            case CreateGroupCommand():
                await SceneEditRequestBus().delete_actor(command.path, undo=False)
            case CreateActorCommand():
                await SceneEditRequestBus().delete_actor(command.path, undo=False)
            case DeleteActorCommand():
                actor = command.actor
                parent_path = command.path.parent()
                await self.undo_delete_recursive(actor, parent_path)
            case RenameActorCommand():
                actor = self._get_actor(command.new_path)
                await SceneEditRequestBus().rename_actor(
                    actor, command.old_path.name(), undo=False
                )
            case ReparentActorCommand():
                actor = self._get_actor(command.new_path)
                old_parent_path = command.old_path.parent()
                await SceneEditRequestBus().reparent_actor(
                    actor, old_parent_path, command.old_row, undo=False
                )
            case TransformCommand():
                await SceneEditRequestBus().set_transform(
                    command.actor_path, command.old_transform, command.local, undo=False
                )
            case PropertyChangeCommand():
                await SceneEditRequestBus().set_property(
                    command.property_key, command.old_value, undo=False
                )
            case _:
                raise Exception("Unknown command type.")

    async def _redo_command(self, command):
        match command:
            case CommandGroup():
                for cmd in command.commands:
                    await self._redo_command(cmd)
            case SelectionCommand():
                await SceneEditRequestBus().set_selection(
                    command.new_selection, undo=False
                )
            case CreateGroupCommand():
                parent = command.path.parent()
                name = command.path.name()
                actor = GroupActor(name=name)
                await SceneEditRequestBus().add_actor(actor, parent, undo=False)
            case CreateActorCommand():
                parent = command.path.parent()
                actor = deepcopy(command.actor)
                await SceneEditRequestBus().add_actor(actor, parent, undo=False)
            case DeleteActorCommand():
                await SceneEditRequestBus().delete_actor(command.path, undo=False)
            case RenameActorCommand():
                actor = self._get_actor(command.old_path)
                name = command.new_path.name()
                await SceneEditRequestBus().rename_actor(actor, name, undo=False)
            case ReparentActorCommand():
                actor = self._get_actor(command.old_path)
                new_parent_path = command.new_path.parent()
                await SceneEditRequestBus().reparent_actor(
                    actor, new_parent_path, command.new_row, undo=False
                )
            case TransformCommand():
                await SceneEditRequestBus().set_transform(
                    command.actor_path, command.new_transform, command.local, undo=False
                )
            case PropertyChangeCommand():
                await SceneEditRequestBus().set_property(
                    command.property_key, command.new_value, undo=False
                )
            case _:
                raise Exception("Unknown command type.")

    # Rebuild actor and its children recursively
    async def undo_delete_recursive(self, actor: BaseActor, parent_path: Path):
        if isinstance(actor, GroupActor):
            new_actor = GroupActor(name=actor.name)
            new_actor.transform = actor.transform

            await SceneEditRequestBus().add_actor(new_actor, parent_path, undo=False)

            this_path = parent_path / actor.name
            for child in actor.children:
                await self.undo_delete_recursive(child, this_path)
        else:
            new_actor = deepcopy(actor)
            await SceneEditRequestBus().add_actor(new_actor, parent_path, undo=False)
