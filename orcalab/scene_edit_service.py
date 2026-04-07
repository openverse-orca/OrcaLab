import asyncio
from copy import deepcopy
from typing import Any, Dict, List, Sequence, Tuple, override
import logging

from orcalab.actor import AssetActor, BaseActor, GroupActor
from orcalab.actor_property import (
    ActorPropertyKey,
)
from orcalab.actor_util import (
    ActorIterator,
    clone_actor_basic,
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
    ActiveActorCommand,
    CommandGroup,
    AddActorCommand,
    DeleteActorCommand,
    DuplicateActorsCommand,
    MoveActorCommand,
    PropertyChangeCommand,
    RenameActorCommand,
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

        # 防止多个编辑操作中的异步操作交叉导致状态混乱。
        self._edit_lock = asyncio.Lock()

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
        # 有些操作中会修改选择状态，会导致额外的历史记录。
        # 这里直接忽略从后端的同步消息
        if self._edit_lock.locked() and source == "remote_scene":
            return

        async with self._edit_lock:
            await self._set_selection(selection, undo, source)

    async def _set_selection(
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

        if source != "remote_scene":
            await self.remote_scene.set_selection(actor_paths)

        await SceneEditNotificationBus().on_selection_changed(
            old_selection, actor_paths, source
        )

        if undo:
            cmd = SelectionCommand(old_selection, actor_paths)
            UndoRequestBus().add_command(cmd)

    @override
    async def set_active_actor(
        self,
        actor: BaseActor | Path | None,
        undo: bool = True,
        source: str = "",
    ) -> None:
        if self._edit_lock.locked() and source == "remote_scene":
            return

        async with self._edit_lock:
            await self._set_active_actor(actor, undo, source)

    async def _set_active_actor(
        self,
        actor: BaseActor | Path | None,
        undo: bool = True,
        source: str = "",
    ) -> None:

        actor_path = None
        if actor is not None:
            _, actor_path = self.local_scene.normalize_actor(actor)

        old_actor_path = self.local_scene.active_actor
        if actor_path == old_actor_path:
            return

        self.local_scene.active_actor = actor_path
        if source != "remote_scene":
            await self.remote_scene.set_active_actor(actor_path)

        bus = SceneEditNotificationBus()
        await bus.on_active_actor_changed(old_actor_path, actor_path, source)

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
        async with self._edit_lock:
            await self._add_actors(requests, undo, source)

    async def _add_actors(
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

        if undo:
            command = AddActorCommand(requests)
            UndoRequestBus().add_command(command)

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

    def normalize_and_clean_actors(
        self, actors: Sequence[BaseActor | Path]
    ) -> Tuple[List[BaseActor], List[Path]]:
        """Remove actors that are dupilicate or descendants of other actors."""
        _, _actor_paths = self.local_scene.normalize_actors(actors)
        clean_actor_paths = self.clean_paths(_actor_paths)
        return self.local_scene.normalize_actors(clean_actor_paths)

    @override
    async def delete_actor(
        self,
        actor: BaseActor | Path,
        undo: bool = True,
        source: str = "",
    ):
        await self.delete_actors([actor], undo, source)

    @override
    async def delete_actors(
        self,
        actors: Sequence[BaseActor | Path],
        undo: bool = True,
        source: str = "",
    ):
        async with self._edit_lock:
            await self._delete_actors(actors, undo, source)

    async def _delete_actors(
        self,
        actors: Sequence[BaseActor | Path],
        undo: bool = True,
        source: str = "",
    ):
        _actors, _actor_paths = self.normalize_and_clean_actors(actors)

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

            await self._set_selection(
                deselect_command.new_selection, undo=False, source=source
            )
            command_group.commands.append(deselect_command)

        if self.local_scene.active_actor in _actor_paths:
            old_active_actor = self.local_scene.active_actor
            new_active_actor = None
            active_actor_command = ActiveActorCommand(
                old_active_actor, new_active_actor
            )
            command_group.commands.append(active_actor_command)
            await self._set_active_actor(new_active_actor, undo=False, source=source)

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
        async with self._edit_lock:
            await self._rename_actor(actor, new_name, undo, source)

    async def _rename_actor(
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

        actor_parent = actor_path.parent()
        assert actor_parent is not None
        new_actor_path = actor_parent / new_name

        command_group = CommandGroup()
        deselect_command: SelectionCommand | None = None
        select_command: SelectionCommand | None = None
        deactive_command: ActiveActorCommand | None = None
        active_command: ActiveActorCommand | None = None

        if actor_path in self.local_scene.selection:
            old_selection = deepcopy(self.local_scene.selection)
            new_selection = deepcopy(self.local_scene.selection)
            new_selection.remove(actor_path)
            new_selection.append(new_actor_path)
            deselect_command = SelectionCommand(old_selection, [])
            select_command = SelectionCommand([], new_selection)

        if actor_path == self.local_scene.active_actor:
            old_active_actor = self.local_scene.active_actor
            new_active_actor = new_actor_path
            deactive_command = ActiveActorCommand(old_active_actor, None)
            active_command = ActiveActorCommand(None, new_active_actor)

        await bus.on_actor_renamed(actor_path, new_name, source)

        if deselect_command is not None:
            await self._set_selection(deselect_command.new_selection, False, source)

        if deactive_command is not None:
            await self._set_active_actor(
                deactive_command.new_active_actor, False, source
            )

        rename_command = RenameActorCommand()
        rename_command.old_path = actor_path
        rename_command.new_path = new_actor_path

        if active_command is not None:
            await self._set_active_actor(active_command.new_active_actor, False, source)

        if select_command is not None:
            await self._set_selection(select_command.new_selection, False, source)

        if undo:
            if deselect_command is not None:
                command_group.commands.append(deselect_command)

            if deactive_command is not None:
                command_group.commands.append(deactive_command)

            command_group.commands.append(rename_command)

            if active_command is not None:
                command_group.commands.append(active_command)

            if select_command is not None:
                command_group.commands.append(select_command)

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
        _actor, _actor_path = self.local_scene.normalize_actor(actor)
        _new_parent, _new_parent_path = self.local_scene.normalize_actor(new_parent)

        old_parent = _actor.parent
        assert isinstance(old_parent, GroupActor)
        index = old_parent.children.index(_actor)

        async with self._edit_lock:
            await self._move_actors([actor], [_new_parent_path], [row], undo, source)

    @override
    async def move_actors(
        self,
        old_actors: Sequence[BaseActor | Path],
        new_parent_paths: List[Path],
        insert_positions: List[int],
        undo: bool = True,
        source: str = "",
    ):
        async with self._edit_lock:
            await self._move_actors(
                old_actors, new_parent_paths, insert_positions, undo, source
            )

    async def _move_actors(
        self,
        old_actors: Sequence[BaseActor | Path],
        new_parent_paths: List[Path],
        insert_positions: List[int],
        undo: bool = True,
        source: str = "",
    ):
        ok, err = self.local_scene.can_move_actors(
            old_actors, new_parent_paths, insert_positions
        )
        if not ok:
            raise Exception(err)

        _old_actros, _old_actor_paths = self.normalize_and_clean_actors(old_actors)
        old_positions = []
        for _actor in _old_actros:
            parent = _actor.parent
            assert isinstance(parent, GroupActor)
            index = parent.children.index(_actor)
            old_positions.append(index)

        command_group = CommandGroup()

        active_command: ActiveActorCommand | None = None

        old_selection = self.local_scene.selection
        new_selection = deepcopy(old_selection)

        for _actor_path, _new_parent_path in zip(_old_actor_paths, new_parent_paths):
            if _actor_path in self.local_scene.selection:
                new_selection.remove(_actor_path)
                new_selection.append(_new_parent_path.append(_actor_path.name()))

            if self.local_scene.active_actor in _old_actor_paths:
                old_active_actor = self.local_scene.active_actor
                new_active_actor = _new_parent_path / _actor_path.name()
                active_command = ActiveActorCommand(old_active_actor, new_active_actor)

        deselect_command = SelectionCommand(old_selection, [])
        select_command = SelectionCommand([], new_selection)

        move_command = MoveActorCommand(
            _old_actor_paths, old_positions, new_parent_paths, insert_positions
        )

        command_group.commands.append(deselect_command)

        bus = SceneEditNotificationBus()

        # Clear selection
        await self._set_selection([], undo=False, source=source)

        # Move
        await bus.before_actor_reparented()
        self.local_scene.move_actors(old_actors, new_parent_paths, insert_positions)
        await self.remote_scene.move_actor_batch(_old_actor_paths, new_parent_paths)
        for root in _old_actros:
            self.local_scene.refresh_subtree_parent_visibility_lock(root)
        await self._sync_subtrees_visibility_lock_remote(_old_actros)
        await bus.on_actor_reparented()
        # Set selection to new paths
        await self._set_selection(new_selection, undo=False, source=source)
        # Set active to new paths
        if active_command is not None:
            await self._set_active_actor(
                active_command.new_active_actor, undo=False, source=source
            )

        if undo:
            command_group.commands.append(deselect_command)
            if active_command is not None:
                command_group.commands.append(active_command)
            command_group.commands.append(move_command)
            command_group.commands.append(select_command)
            UndoRequestBus().add_command(command_group)

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

    def _duplicate_process_add_request(
        self,
        requests: List[AddActorRequest],
        root_actor_path: Path,
        existing_names: List[str],
        child_positions: List[int],
    ):
        root_actor, root_actor_path = self.local_scene.normalize_actor(root_actor_path)

        root_actor_parent_path = root_actor_path.parent()
        assert root_actor_parent_path is not None

        root_actor_parent, _ = self.local_scene.normalize_actor(root_actor_parent_path)
        assert isinstance(root_actor_parent, GroupActor)

        new_name = make_unique_name1(existing_names, root_actor.name)

        child_pos = root_actor_parent.children.index(root_actor)
        assert child_pos != -1

        # 计算插入位置时需要考虑之前已经插入的同级别 actor 对原位置的影响
        offset = 1
        for pos in child_positions:
            if pos < child_pos:
                offset += 1
        insert_pos = child_pos + offset
        child_positions.append(child_pos)

        new_root_actor = clone_actor_basic(root_actor)
        new_root_actor.name = new_name
        new_root_actor_path = root_actor_parent_path / new_name
        requests.append(
            AddActorRequest(
                new_root_actor,
                root_actor_parent_path,
                insert_pos,
                root_actor,
            )
        )

        for actor in ActorIterator(root_actor, include_root=False):
            actor, actor_path = self.local_scene.normalize_actor(actor)
            new_actor = clone_actor_basic(actor)
            dst_path = actor_path.replace_parent(root_actor_path, new_root_actor_path)
            new_parent_path = dst_path.parent()
            assert new_parent_path is not None
            requests.append(AddActorRequest(new_actor, new_parent_path, -1, actor))

        return new_root_actor_path

    async def _sync_subtrees_visibility_lock_remote(
        self, root_actors: Sequence[BaseActor]
    ):
        """按本地 effective 显隐/锁定批量同步远端（复制、reparent 等 subtree 变更后）。"""
        vis_show: List[Path] = []
        vis_hide: List[Path] = []
        lock_on: List[Path] = []
        lock_off: List[Path] = []

        for root_actor in root_actors:
            for actor in ActorIterator(root_actor, include_root=True):
                a, p = self.local_scene.normalize_actor(actor)
                eff_visible = a.is_visible and a.is_parent_visible
                if isinstance(a, AssetActor):
                    if eff_visible:
                        vis_show.append(p)
                    else:
                        vis_hide.append(p)
                eff_locked = a.is_locked or a.is_parent_locked
                if eff_locked:
                    lock_on.append(p)
                else:
                    lock_off.append(p)

        if vis_hide:
            await self.remote_scene.actor_visible_change(False, vis_hide)
        if vis_show:
            await self.remote_scene.actor_visible_change(True, vis_show)
        if lock_on:
            await self.remote_scene.actor_locked_change(True, lock_on)
        if lock_off:
            await self.remote_scene.actor_locked_change(False, lock_off)

    @override
    async def duplicate_actors(
        self, actors: Sequence[BaseActor | Path], undo: bool = True, source: str = ""
    ):
        async with self._edit_lock:
            await self._duplicate_actors(actors, undo, source)

    async def _duplicate_actors(
        self, actors: Sequence[BaseActor | Path], undo: bool = True, source: str = ""
    ):
        _, actor_paths = self.normalize_and_clean_actors(actors)

        for path in actor_paths:
            if path.is_root():
                logger.error("Cannot duplicate root actor", path)
                return

        # 按照父路径对 actor 进行分组
        parent_dict: Dict[Path, List[Path]] = {}
        for path in actor_paths:
            parent_path = path.parent()
            assert parent_path is not None
            if parent_path not in parent_dict:
                parent_dict[parent_path] = []
            parent_dict[parent_path].append(path)

        requests: List[AddActorRequest] = []
        new_actor_paths: List[Path] = []
        for parent_path, paths in parent_dict.items():
            exsiting_names = []
            parent_actor, _ = self.local_scene.normalize_actor(parent_path)
            assert isinstance(parent_actor, GroupActor)
            for child in parent_actor.children:
                exsiting_names.append(child.name)

            child_positions: List[int] = []
            for path in paths:
                new_actor_path = self._duplicate_process_add_request(
                    requests, path, exsiting_names, child_positions
                )
                new_actor_paths.append(new_actor_path)
                exsiting_names.append(new_actor_path.name())

        bus = SceneEditNotificationBus()

        command_group = CommandGroup()
        duplicate_command = DuplicateActorsCommand(actor_paths, new_actor_paths)

        old_selection = deepcopy(self.local_scene.selection)
        new_selection = new_actor_paths
        select_command = SelectionCommand(old_selection, new_selection)

        await bus.before_actor_added_batch()
        err = self.local_scene.add_actor_batch(requests)
        if err == "":
            suceess, errors = await self.remote_scene.add_actor_batch(requests, True)
            new_roots = [
                self.local_scene.normalize_actor(p)[0] for p in new_actor_paths
            ]
            await self._sync_subtrees_visibility_lock_remote(new_roots)
        await bus.on_actor_added_batch("")

        await self._set_selection(new_selection, undo=False, source=source)

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
