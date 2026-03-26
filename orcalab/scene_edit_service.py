from copy import deepcopy
from typing import Any, Dict, List, Sequence, Tuple, override
import logging
import itertools

from orcalab.actor import BaseActor, GroupActor, AssetActor
from orcalab.actor_property import (
    ActorProperty,
    ActorPropertyKey,
)
from orcalab.actor_util import (
    ActorIterator,
    clone_actor_basic,
    collect_properties_duplicate_data,
    make_unique_name1,
)
from orcalab.local_scene import LocalScene
from orcalab.remote_scene import RemoteScene
from orcalab.math import Transform
from orcalab.path import Path
from orcalab.scene_edit_bus import (
    SceneEditNotificationBus,
    SceneEditRequestBus,
    SceneEditRequest,
)

from orcalab.scene_edit_types import AddActorRequest
from orcalab.undo_service.command import (
    CommandGroup,
    AddActorCommand,
    DeleteActorCommand,
    DuplicateActorCommand,
    PropertyChangeCommand,
    RenameActorCommand,
    ReparentActorCommand,
    SelectionCommand,
    TransformCommand,
)

from orcalab.undo_service.undo_service_bus import UndoRequestBus

logger = logging.getLogger(__name__)


class SceneEditService(SceneEditRequest):

    def __init__(self, local_scene: LocalScene, remote_scene: RemoteScene):
        self.local_scene = local_scene
        self.remote_scene = remote_scene

        self.old_transforms: Dict[Path, Transform] = {}

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
        actor_paths = sorted(selection)

        if actor_paths == self.local_scene.selection:
            return

        old_selection = deepcopy(self.local_scene.selection)
        self.local_scene.selection = actor_paths

        await self.remote_scene.set_selection(actor_paths)

        await SceneEditNotificationBus().on_selection_changed(
            old_selection, actor_paths, source
        )

        if undo:
            cmd = SelectionCommand(old_selection, actor_paths)
            UndoRequestBus().add_command(cmd)

    @override
    async def add_actor(
        self,
        actor: BaseActor,
        parent_actor: GroupActor | Path,
        undo: bool = True,
        source: str = "",
    ):
        _, parent_actor_path = self.local_scene.normalize_actor(parent_actor)
        request = AddActorRequest(actor, parent_actor_path, -1)
        await self.add_actors([request], undo, source)

    @override
    async def add_actors(
        self,
        requests: List[AddActorRequest],
        undo: bool = True,
        source: str = "",
    ):

        ok, err = self.local_scene.can_add_actors(requests)
        if not ok:
            raise Exception(err)

        bus = SceneEditNotificationBus()

        await bus.before_actor_added_batch()
        err = self.local_scene.add_actor_batch(requests)
        if err == "":
            suceess, errors = await self.remote_scene.add_actor_batch(requests, True)
        await bus.on_actor_added_batch("")

        # TODO: report errors
        # try:
        #     await bus.on_actor_added(actor, parent_actor_path, source)
        # except Exception as e:
        #     # on_actor_added failed (e.g. remote scene sync failed)
        #     # Need to rollback: delete actor from local scene and notify
        #     self.local_scene.delete_actor(actor)
        #     await bus.on_actor_added_failed(actor, parent_actor_path, source)
        #     raise

        # TODO: set visibility and lock state of actors after adding

        # actor.is_parent_visible = (
        #     parent_actor.is_parent_visible and parent_actor.is_visible
        # )
        # actor.is_parent_locked = parent_actor.is_parent_locked or parent_actor.is_locked

        # if actor.is_parent_visible == False:
        #     await self.set_actor_visible(actor, False, False, "reparent")
        # if actor.is_parent_locked == True:
        #     await self.set_actor_locked(actor, True, False, "reparent")

        if undo:
            command = AddActorCommand(requests)
            UndoRequestBus().add_command(command)

    @override
    async def delete_actor(
        self,
        actor: BaseActor | Path,
        undo: bool = True,
        source: str = "",
    ):
        await self.delete_actors([actor], undo, source)

    def clean_paths(self, paths: List[Path]) -> List[Path]:
        """Remove paths that are dupilicate or descendants of other paths."""
        deduplicated_paths = list(set(paths))
        sorted_paths = sorted(deduplicated_paths)
        cleaned_paths = []

        def has_parent_in_list(path: Path, path_list: List[Path]) -> bool:
            for p in path_list:
                if path.is_descendant_of(p):
                    return True
            return False

        for path in sorted_paths:
            if not has_parent_in_list(path, cleaned_paths):
                cleaned_paths.append(path)

        return cleaned_paths

    @override
    async def delete_actors(
        self,
        actors: Sequence[BaseActor | Path],
        undo: bool = True,
        source: str = "",
    ):

        _, _actor_paths = self.local_scene.normalize_actors(actors)
        clean_actor_paths = self.clean_paths(_actor_paths)
        _actors, _actor_paths = self.local_scene.normalize_actors(clean_actor_paths)

        ok, err = self.local_scene.can_delete_actors(_actor_paths)
        if not ok:
            logger.error("Cannot delete actor: %s", err)
            return

        edit_actor_paths: List[Path] = []
        self.get_editing_actor_path(edit_actor_paths)

        for _actor_path in _actor_paths:
            if _actor_path.is_root():
                logger.error("Cannot delete root actor: %s", _actor_path)
                return

            if _actor_path in edit_actor_paths:
                logger.error("Cannot delete actor in editing: %s", _actor_path)
                return

        parent_paths = []
        indexes = []

        for _actor in _actors:
            parent_actor = _actor.parent
            assert isinstance(parent_actor, GroupActor)
            index = parent_actor.children.index(_actor)
            assert index != -1

            parent_actor_path = self.local_scene.get_actor_path(parent_actor)
            assert parent_actor_path is not None

            parent_paths.append(parent_actor_path)
            indexes.append(index)

        bus = SceneEditNotificationBus()

        await bus.before_actors_deleted(_actor_paths, source)

        command_group = CommandGroup()
        in_selection = False

        for _actor_path in _actor_paths:
            if _actor_path in self.local_scene.selection:
                in_selection = True
                break

        if in_selection:
            old_selection = deepcopy(self.local_scene.selection)
            new_selection = deepcopy(self.local_scene.selection)
            for _actor_path in _actor_paths:
                new_selection.remove(_actor_path)
            deselect_command = SelectionCommand(old_selection, new_selection)

            await self.set_selection(
                deselect_command.new_selection, undo=False, source=source
            )
            command_group.commands.append(deselect_command)

        delete_command = DeleteActorCommand(_actors, parent_paths, indexes)
        command_group.commands.append(delete_command)

        self.local_scene.delete_actors(_actors)
        await self.remote_scene.delete_actor_batch(_actor_paths)

        await bus.on_actors_deleted(_actor_paths, source)

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
            old_selection = deepcopy(self.local_scene.selection)
            new_selection = deepcopy(self.local_scene.selection)
            new_selection.remove(actor_path)
            deselect_command = SelectionCommand(old_selection, new_selection)
            command_group.commands.append(deselect_command)

        await bus.on_actor_renamed(actor_path, new_name, source)

        rename_command = RenameActorCommand()
        rename_command.old_path = actor_path
        rename_command.new_path = new_actor_path
        command_group.commands.append(rename_command)

        if in_selection:
            old_selection = deepcopy(deselect_command.new_selection)
            new_selection = deepcopy(deselect_command.new_selection)
            new_selection.append(new_actor_path)
            select_command = SelectionCommand(old_selection, new_selection)
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

        ### 重新判断隐藏
        # 隐藏->可见
        if actor.is_parent_visible == False:
            if (
                actor.is_visible == True
                and new_parent.is_visible == True
                and new_parent.is_parent_visible == True
            ):
                await self.set_actor_visible(actor, True, False, "reparent")
        # 可见->隐藏
        if actor.is_visible == True and actor.is_parent_visible == True:
            if new_parent.is_visible == False or new_parent.is_parent_visible == False:
                await self.set_actor_visible(actor, False, False, "reparent")

        new_parent_visible = new_parent.is_visible and new_parent.is_parent_visible
        if actor.is_parent_visible != new_parent_visible:
            actor.is_parent_visible = new_parent_visible

        ### 重新判断锁定
        # 解锁
        if actor.is_parent_locked == True:
            if (
                actor.is_locked == False
                and new_parent.is_locked == False
                and new_parent.is_parent_locked == False
            ):
                await self.set_actor_locked(actor, False, False, "reparent")
        # 锁定
        if actor.is_locked == False and actor.is_parent_locked == False:
            if new_parent.is_locked == True or new_parent.is_parent_locked == True:
                await self.set_actor_locked(actor, True, False, "reparent")

        new_parent_locked = new_parent.is_locked or new_parent.is_parent_locked
        if actor.is_parent_locked != new_parent_locked:
            actor.is_parent_locked = new_parent_locked

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

    def _can_duplicate_actors(
        self, actor_pairs: List[Tuple[BaseActor, Path]]
    ) -> Tuple[bool, str]:

        def has_relationship(path1: Path, path2: Path) -> bool:
            return path1.is_descendant_of(path2) or path2.is_descendant_of(path1)

        for pair1, pair2 in itertools.combinations(actor_pairs, 2):
            actor1, actor_path1 = pair1
            actor2, actor_path2 = pair2
            if actor_path1.is_root():
                return False, f"Cannot duplicate root actor: {actor_path1}"
            if actor_path2.is_root():
                return False, f"Cannot duplicate root actor: {actor_path2}"

            if actor_path1 == actor_path2:
                return False, f"Duplicate actors with same path: {actor_path1}"

            if has_relationship(actor_path1, actor_path2):
                return (
                    False,
                    f"Cannot duplicate related actors: {actor_path1} and {actor_path2}",
                )

        return True, ""

    def _split_actor_pairs_by_parent(
        self, actor_pairs: List[Tuple[BaseActor, Path]]
    ) -> Dict[Path, List[Tuple[BaseActor, Path]]]:
        parent_map: Dict[Path, List[Tuple[BaseActor, Path]]] = {}
        for actor, path in actor_pairs:
            parent_path = path.parent()
            assert parent_path is not None
            if parent_path not in parent_map:
                parent_map[parent_path] = []
            parent_map[parent_path].append((actor, path))
        return parent_map

    @override
    async def duplicate_actor(
        self, root_actor: BaseActor | Path, undo: bool = True, source: str = ""
    ):
        root_actor, root_actor_path = self.local_scene.normalize_actor(root_actor)
        assert root_actor_path.is_root() == False, "Cannot duplicate root actor"

        root_actor_parent_path = root_actor_path.parent()
        assert root_actor_parent_path is not None

        root_actor_parent, _ = self.local_scene.normalize_actor(root_actor_parent_path)
        assert isinstance(
            root_actor_parent, GroupActor
        ), "Parent actor must be a GroupActor"

        existing_names = [child.name for child in root_actor_parent.children]
        new_name = make_unique_name1(existing_names, root_actor.name)

        child_pos = root_actor_parent.children.index(root_actor)
        assert child_pos != -1

        bus = SceneEditNotificationBus()

        requests: List[AddActorRequest] = []
        new_root_actor = clone_actor_basic(root_actor)
        new_root_actor.name = new_name
        new_root_actor_path = root_actor_parent_path / new_name
        requests.append(
            AddActorRequest(
                new_root_actor,
                root_actor_parent_path,
                child_pos + 1,
                root_actor,
            )
        )

        command_group = CommandGroup()
        duplicate_command = DuplicateActorCommand(root_actor_path, new_root_actor_path)

        old_selection = deepcopy(self.local_scene.selection)
        new_selection = [new_root_actor_path]
        select_command = SelectionCommand(old_selection, new_selection)

        for actor in ActorIterator(root_actor, include_root=False):
            actor, actor_path = self.local_scene.normalize_actor(actor)
            new_actor = clone_actor_basic(actor)
            dst_path = actor_path.replace_parent(root_actor_path, new_root_actor_path)
            new_parent_path = dst_path.parent()
            assert new_parent_path is not None
            requests.append(AddActorRequest(new_actor, new_parent_path, -1, actor))

        await bus.before_actor_added_batch()
        err = self.local_scene.add_actor_batch(requests)
        if err == "":
            suceess, errors = await self.remote_scene.add_actor_batch(requests, True)
        await bus.on_actor_added_batch("")

        await self.set_selection(new_selection, undo=False, source=source)

        # batch set properties of duplicated actors on backend.

        keys: List[ActorPropertyKey] = []
        props: List[ActorProperty] = []
        values: List[Any] = []

        for request in requests:
            if isinstance(request.actor, AssetActor):
                assert isinstance(request.actor_template, AssetActor)
                dst_path = request.parent_path / request.actor.name
                dst_property_groups = request.actor.property_groups
                src_property_groups = request.actor_template.property_groups
                collect_properties_duplicate_data(
                    keys,
                    props,
                    values,
                    src_property_groups,
                    dst_property_groups,
                    dst_path,
                )

        await self.remote_scene.set_properties(keys, values)
        for key, prop, value in zip(keys, props, values):
            prop.set_value(value)
            await bus.on_property_changed(key, value, source)

        if undo:
            command_group.commands.append(duplicate_command)
            command_group.commands.append(select_command)
            UndoRequestBus().add_command(command_group)

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
    async def set_transform(self, actor, transform, local, undo=True, source=""):
        """Leave for compatibility. Use set_transform_batch instead."""
        _actor, _actor_path = self.local_scene.get_actor_and_path(actor)
        _transform = deepcopy(transform)

        if not local:
            parent = _actor.parent
            if parent is not None:
                parent_world_transform = parent.world_transform
                _transform = parent_world_transform.inverse() * transform

        await self.set_transform_batch([_actor_path], [_transform], undo, source)

    @override
    async def start_change_transform_batch(self, actors: Sequence[BaseActor | Path]):
        if len(actors) == 0:
            _actors, _actor_paths = self.local_scene.normalize_actors(
                self.local_scene.selection
            )
        else:
            _actors, _actor_paths = self.local_scene.normalize_actors(actors)

        self.old_transforms.clear()
        for _actor, _actor_path in zip(_actors, _actor_paths):
            self.old_transforms[_actor_path] = _actor.transform

        logger.debug(f"start_change_transform_batch: {_actor_paths}")

    @override
    async def end_change_transform_batch(self, actors: Sequence[BaseActor | Path]):
        if len(actors) == 0:
            _actors, _actor_paths = self.local_scene.normalize_actors(
                self.local_scene.selection
            )
        else:
            _actors, _actor_paths = self.local_scene.normalize_actors(actors)

        transforms = []
        for _actor, _actor_path in zip(_actors, _actor_paths):
            transforms.append(_actor.transform)

        await self.set_transform_batch(_actors, transforms, undo=True, source="")

        self.old_transforms.clear()

        logger.debug(f"end_change_transform_batch: {_actor_paths}")

    @override
    async def set_transform_batch(
        self,
        actors: Sequence[BaseActor | Path],
        transforms: Sequence[Transform],
        undo: bool = True,
        source: str = "",
    ):
        _actors, _actor_paths = self.local_scene.normalize_actors(actors)
        old_transforms = []
        new_transforms = []

        # update fronend values
        for _actor, _path, _transform in zip(_actors, _actor_paths, transforms):
            if len(self.old_transforms) == 0:
                old_transform = _actor.transform
                new_transform = _transform
                _actor.transform = new_transform

                old_transforms.append(old_transform)
                new_transforms.append(new_transform)
            else:
                # we are in dragging.
                old_transform = self.old_transforms.get(_path)
                if old_transform is None:
                    logger.warning(
                        f"Old transform for actor {_path} not found in old_transforms dict."
                    )
                    continue
                new_transform = _transform
                _actor.transform = new_transform

                old_transforms.append(old_transform)
                new_transforms.append(new_transform)

        # update backend values
        await self.remote_scene.set_actor_transform_batch(_actor_paths, new_transforms)

        # Notify.
        await SceneEditNotificationBus().on_transforms_changed(
            _actor_paths,
            old_transforms,
            new_transforms,
            source,
        )

        if undo:
            command = TransformCommand(
                _actor_paths, old_transforms, new_transforms, local=True
            )
            UndoRequestBus().add_command(command)

        logger.debug(f"set_transform_batch: {_actor_paths}")
        logger.debug(f"set_transform_batch: {new_transforms}")

    @override
    def get_editing_actor_path(self, out: List[Path]):
        if self.old_transforms:
            for path in self.old_transforms.keys():
                out.append(path)

        if self.property_key is not None:
            out.append(self.property_key.actor_path)

    @override
    def get_all_actors(self, out: List[Dict[Path, BaseActor]]):
        if out is not None:
            out.append(self.local_scene.actors)

    @override
    def get_selection(self, out: List[List[Path]]):
        if out is not None:
            out.append(self.local_scene.selection)

    @override
    async def set_actor_visible(self, actor, visible, undo, source):
        _actor, _actor_path = self.local_scene.get_actor_and_path(actor)
        paths_to_update = []

        if source == "layout":
            paths_to_update.append(_actor_path)
            await SceneEditNotificationBus().on_actor_visible_changed(
                _actor_path, paths_to_update, visible, source
            )
        if source == "actor_outline" or source == "reparent":
            # if _actor.is_parent_visible == True:
            if not isinstance(_actor, GroupActor):
                paths_to_update.append(_actor_path)
            else:
                self.local_scene.update_visible_recursive(
                    _actor, paths_to_update, visible
                )
            await SceneEditNotificationBus().on_actor_visible_changed(
                _actor_path, paths_to_update, visible, source
            )

    @override
    async def set_actor_locked(self, actor, locked, undo, source):
        _actor, _actor_path = self.local_scene.get_actor_and_path(actor)
        paths_to_update = []

        if source == "layout":
            paths_to_update.append(_actor_path)
            await SceneEditNotificationBus().on_actor_locked_changed(
                _actor_path, paths_to_update, locked, source
            )
        if source == "actor_outline" or source == "reparent":
            if _actor.is_parent_locked == False:
                paths_to_update.append(_actor_path)
                self.local_scene.update_locked_recursive(
                    _actor, paths_to_update, locked
                )
            for path in paths_to_update:
                actor, _ = self.local_scene.get_actor_and_path(path)
            await SceneEditNotificationBus().on_actor_locked_changed(
                _actor_path, paths_to_update, locked, source
            )
