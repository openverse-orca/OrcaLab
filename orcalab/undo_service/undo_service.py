import asyncio
from copy import deepcopy
from typing import override, List
import logging
from orcalab.actor import BaseActor, GroupActor, AssetActor
from orcalab.actor_util import clone_actor_basic
from orcalab.application_util import get_local_scene
from orcalab.path import Path

from orcalab.scene_edit_types import AddActorRequest
from orcalab.undo_service.command import (
    ActiveActorCommand,
    BaseCommand,
    CommandGroup,
    AddActorCommand,
    DeleteActorCommand,
    MoveActorCommand,
    PropertyChangeCommand,
    RenameActorCommand,
    SelectionCommand,
    TransformCommand,
    DuplicateActorsCommand,
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
                logger.debug("No command to undo.")
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
                logger.debug("No command to redo.")
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
            case ActiveActorCommand():
                await SceneEditRequestBus().set_active_actor(
                    command.old_active_actor, undo=False
                )
            case AddActorCommand():
                paths: List[Path] = []
                for request in command.requests:
                    paths.append(request.parent_path / request.actor.name)
                await SceneEditRequestBus().delete_actors(paths, undo=False)
            case DeleteActorCommand():
                await self.undo_delete_actors(
                    command.actors, command.parent_paths, command.rows
                )
            case RenameActorCommand():
                actor = self._get_actor(command.new_path)
                await SceneEditRequestBus().rename_actor(
                    actor, command.old_path.name(), undo=False
                )
            case MoveActorCommand():
                actor_paths: List[Path] = []
                new_parent_paths: List[Path] = []
                for actor_path, new_parent_path in zip(
                    command.actor_paths, command.new_parent_paths
                ):
                    actor_paths.append(new_parent_path / actor_path.name())
                    new_parent_path = actor_path.parent()
                    assert new_parent_path is not None
                    new_parent_paths.append(new_parent_path)

                await SceneEditRequestBus().move_actors(
                    actor_paths, new_parent_paths, command.old_rows, undo=False
                )

            case TransformCommand():
                await SceneEditRequestBus().set_transform_batch(
                    command.actor_paths,
                    command.old_transforms,
                    undo=False,
                )
            case PropertyChangeCommand():
                await SceneEditRequestBus().set_property(
                    command.property_key, command.old_value, undo=False
                )
            case DuplicateActorsCommand():
                await SceneEditRequestBus().delete_actors(command.new_paths, undo=False)
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
            case ActiveActorCommand():
                await SceneEditRequestBus().set_active_actor(
                    command.new_active_actor, undo=False
                )
            case AddActorCommand():
                await SceneEditRequestBus().add_actors(command.requests, undo=False)
            case DeleteActorCommand():
                actor_paths: List[Path] = []
                for actor, parent_path, row in zip(
                    command.actors, command.parent_paths, command.rows
                ):
                    actor_paths.append(parent_path / actor.name)
                await SceneEditRequestBus().delete_actors(actor_paths, undo=False)
            case RenameActorCommand():
                actor = self._get_actor(command.old_path)
                name = command.new_path.name()
                await SceneEditRequestBus().rename_actor(actor, name, undo=False)
            case MoveActorCommand():
                await SceneEditRequestBus().move_actors(
                    command.actor_paths,
                    command.new_parent_paths,
                    command.new_rows,
                    undo=False,
                )
            case TransformCommand():
                await SceneEditRequestBus().set_transform_batch(
                    command.actor_paths,
                    command.new_transforms,
                    undo=False,
                )
            case PropertyChangeCommand():
                await SceneEditRequestBus().set_property(
                    command.property_key, command.new_value, undo=False
                )
            case DuplicateActorsCommand():
                await SceneEditRequestBus().duplicate_actors(
                    command.source_paths, undo=False
                )
            case _:
                raise Exception("Unknown command type.")

    async def undo_delete_actors(
        self, actors: List[BaseActor], parent_paths: List[Path], rows: List[int]
    ):
        request: List[AddActorRequest] = []

        for actor, parent_path, row in zip(actors, parent_paths, rows):
            self.undo_delete_actor(request, actor, parent_path, row)

        await SceneEditRequestBus().add_actors(request, undo=False)

    def undo_delete_actor(
        self,
        request: List[AddActorRequest],
        actor: BaseActor,
        parent_path: Path,
        row: int,
    ):
        """Recursively add actor and its children."""
        new_actor = clone_actor_basic(actor)
        request.append(AddActorRequest(new_actor, parent_path, row, actor))

        if isinstance(actor, GroupActor):
            this_path = parent_path / new_actor.name
            for child in actor.children:
                self.undo_delete_actor(request, child, this_path, -1)
