import asyncio
from typing import Any, Dict, List, Sequence, Tuple, override
import logging
import numpy as np

from orcalab.actor import AssetActor, BaseActor, GroupActor
from orcalab.actor_property import (
    ActorPropertyKey,
)
from orcalab.actor_util import (
    ActorIterator,
    clone_actor_basic,
    make_unique_name1,
)
from orcalab.entity_path import EntityPath
from orcalab.local_scene import LocalScene
from orcalab.post_process_dispatcher import PostProcessDispatcher
from orcalab.remote_scene import RemoteScene
from orcalab.math import Transform
from orcalab.path import Path
from orcalab.perf_log import perf_logger
from orcalab.scene_edit_bus import (
    SceneEditNotificationBus,
    SceneEditRequestBus,
    SceneEditRequest,
)

from orcalab.scene_edit_types import AddActorRequest
from orcalab.selection_data import SelectionData
from orcalab.undo_service.command import (
    ActorReconstructInfo,
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

        self._post_process_dispatcher = PostProcessDispatcher(local_scene, remote_scene)

        # For property change tracking
        self.property_edit_lock = asyncio.Lock()
        self.property_key: ActorPropertyKey | None = None
        self.old_property_value: Any = None

        # 防止多个编辑操作中的异步操作交叉导致状态混乱。
        self._edit_lock = asyncio.Lock()

        self._is_duplicating = False

        self._recursive = False

    def connect_bus(self):
        SceneEditRequestBus.connect(self)

    def disconnect_bus(self):
        SceneEditRequestBus.disconnect(self)

    @override
    async def set_selection(
        self,
        selection: SelectionData,
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
        selection: SelectionData,
        undo: bool = True,
        source: str = "",
    ) -> None:
        normalized_selection = selection.normalized()
        old_selection = self.local_scene.selection()
        if normalized_selection == self.local_scene.selection():
            return

        self.local_scene.set_selection(normalized_selection)

        if source != "remote_scene":
            await self.remote_scene.set_selection(selection)

        await SceneEditNotificationBus().on_selection_changed(
            old_selection, normalized_selection, source
        )

        if undo:
            cmd = SelectionCommand(old_selection, normalized_selection)
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
            if suceess:
                await bus.on_actor_added_batch("")
            else:
                actors_to_delete = []
                for request in requests:
                    actors_to_delete.append(request.actor)
                self.local_scene.delete_actors(actors_to_delete)
                await bus.on_actor_added_failed("")  # TODO: Fix wrong parameter

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

        actor_paths_list: List[List[Path]] = []
        infos: List[ActorReconstructInfo] = []
        for _actor, _actor_path in zip(_actors, _actor_paths):
            parent_actor = _actor.parent
            assert isinstance(parent_actor, GroupActor)
            index = parent_actor.children.index(_actor)
            assert index != -1

            infos.append(
                ActorReconstructInfo(
                    actor=_actor,
                    actor_path=_actor_path,
                    position=index,
                    actor_overrides_dict={},
                )
            )

            actor_paths = [_actor_path]
            for actor in ActorIterator(_actor, include_root=False):
                _, p = self.local_scene.normalize_actor(actor)
                actor_paths.append(p)
            actor_paths_list.append(actor_paths)

        lll = await self.remote_scene.get_actor_overrides_batch_grouped(
            actor_paths_list
        )
        for info, actor_paths, ll in zip(infos, actor_paths_list, lll):
            for actor_path, overrides in zip(actor_paths, ll):
                info.actor_overrides_dict[actor_path] = overrides

        # update selection

        old_selection = self.local_scene.selection()
        new_selection = SelectionData()
        selection_changed = False

        for selected_path in old_selection.selected_actors:
            if selected_path in _actor_paths:
                selection_changed = True
            else:
                new_selection.selected_actors.append(selected_path)

        if old_selection.active_actor_path in _actor_paths:
            new_selection.active_actor_path = None
            new_selection.active_entity_path = EntityPath()
            selection_changed = True
        else:
            new_selection.active_actor_path = old_selection.active_actor_path
            new_selection.active_entity_path = old_selection.active_entity_path

        bus = SceneEditNotificationBus()

        # commit changes

        await bus.before_actors_deleted(_actor_paths, source)

        if selection_changed:
            await self._set_selection(new_selection, undo=False, source=source)

        self.local_scene.delete_actors(_actors)
        await self.remote_scene.delete_actor_batch(_actor_paths)

        await bus.on_actors_deleted(_actor_paths, source)

        # record undo

        if not undo:
            return

        deselect_command = SelectionCommand(old_selection, new_selection)
        delete_command = DeleteActorCommand(actor_reconstruct_info=infos)

        if selection_changed:
            command_group = CommandGroup()
            command_group.commands.append(deselect_command)
            command_group.commands.append(delete_command)
            UndoRequestBus().add_command(command_group)
        else:
            UndoRequestBus().add_command(delete_command)

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
            logger.error("Cannot rename actor: %s", err)
            return

        if new_name == actor.name:
            return

        actor, actor_path = self.local_scene.get_actor_and_path(actor)

        actor_parent = actor_path.parent()
        assert actor_parent is not None
        new_actor_path = actor_parent / new_name

        # update selection

        old_selection = self.local_scene.selection()
        new_selection = SelectionData()
        selection_changed = False

        for selected_path in old_selection.selected_actors:
            if selected_path == actor_path:
                new_selection.selected_actors.append(new_actor_path)
                selection_changed = True
            else:
                new_selection.selected_actors.append(selected_path)

        if old_selection.active_actor_path == actor_path:
            new_selection.active_actor_path = new_actor_path
            # active_entity 不变，因为重命名不影响 active entity
            new_selection.active_entity_path = old_selection.active_entity_path
            selection_changed = True
        else:
            new_selection.active_actor_path = old_selection.active_actor_path
            new_selection.active_entity_path = old_selection.active_entity_path

        # commit changes

        bus = SceneEditNotificationBus()

        await bus.before_actor_renamed(actor_path, new_name, source)

        self.local_scene.rename_actor(actor, new_name)

        await self.remote_scene.rename_actor(actor_path, new_name)

        if selection_changed:
            await self._set_selection(new_selection, False, source)

        await bus.on_actor_renamed(actor_path, new_name, source)

        # record undo

        if not undo:
            return

        empty_selection = SelectionData()
        deselect_command = SelectionCommand(old_selection, empty_selection)
        select_command = SelectionCommand(empty_selection, new_selection)
        rename_command = RenameActorCommand(actor_path, new_actor_path)

        if selection_changed:
            command_group = CommandGroup()
            command_group.commands.append(deselect_command)
            command_group.commands.append(rename_command)
            command_group.commands.append(select_command)
            UndoRequestBus().add_command(command_group)
        else:
            UndoRequestBus().add_command(rename_command)

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
            logger.error("Cannot move actors: %s", err)
            return

        _old_actros, _old_actor_paths = self.local_scene.normalize_actors(old_actors)
        old_positions = []
        for _actor in _old_actros:
            parent = _actor.parent
            assert isinstance(parent, GroupActor)
            index = parent.children.index(_actor)
            old_positions.append(index)

        new_actor_paths: List[Path] = []
        for _actor_path, _new_parent_path in zip(_old_actor_paths, new_parent_paths):
            new_actor_paths.append(_new_parent_path / _actor_path.name())

        # update selection

        empty_selection = SelectionData()
        old_selection = self.local_scene.selection()
        new_selection = SelectionData()
        selection_changed = False

        for old_path, new_path, selected_path in zip(_old_actor_paths, new_actor_paths, old_selection.selected_actors):
            if selected_path == old_path:
                new_selection.selected_actors.append(new_path)
                selection_changed = True
                break
            else:
                new_selection.selected_actors.append(selected_path)

        for old_path, new_path in zip(_old_actor_paths, new_actor_paths):
            if old_selection.active_actor_path == old_path:
                new_selection.active_actor_path = new_path
                # active_entity 不变，因为移动不影响 active entity
                new_selection.active_entity_path = old_selection.active_entity_path
                selection_changed = True
            else:
                new_selection.active_actor_path = old_selection.active_actor_path
                new_selection.active_entity_path = old_selection.active_entity_path

        # commit changes

        bus = SceneEditNotificationBus()

        await bus.before_actor_reparented()

        if selection_changed:
            await self._set_selection(empty_selection, undo=False, source=source)

        self.local_scene.move_actors(old_actors, new_parent_paths, insert_positions)
        await self.remote_scene.move_actor_batch(_old_actor_paths, new_parent_paths)
        for root in _old_actros:
            self.local_scene.refresh_subtree_parent_visibility_lock(root)
        await self._sync_subtrees_visibility_lock_remote(_old_actros)

        if selection_changed:
            await self._set_selection(new_selection, undo=False, source=source)

        await bus.on_actor_reparented()

        # record undo

        if not undo:
            return

        deselect_command = SelectionCommand(old_selection, empty_selection)
        select_command = SelectionCommand(empty_selection, new_selection)
        move_command = MoveActorCommand(
            _old_actor_paths, old_positions, new_parent_paths, insert_positions
        )

        if selection_changed:
            command_group = CommandGroup()
            command_group.commands.append(deselect_command)
            command_group.commands.append(move_command)
            command_group.commands.append(select_command)
            UndoRequestBus().add_command(command_group)
        else:
            UndoRequestBus().add_command(move_command)

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
        template_actor_paths: List[Path],
        root_actor_path: Path,
        existing_names: List[str],
        child_positions: List[int],
    ):
        perf = perf_logger("SERVICE", "duplicate_process_add_request")

        root_actor, root_actor_path = self.local_scene.normalize_actor(root_actor_path)

        perf.start("prepare_parent_and_name")
        root_actor_parent_path = root_actor_path.parent()
        assert root_actor_parent_path is not None

        root_actor_parent, _ = self.local_scene.normalize_actor(root_actor_parent_path)
        assert isinstance(root_actor_parent, GroupActor)

        new_name = make_unique_name1(existing_names, root_actor.name)

        perf.start("compute_insert_pos")
        child_pos = root_actor_parent.children.index(root_actor)
        assert child_pos != -1

        # 计算插入位置时需要考虑之前已经插入的同级别 actor 对原位置的影响
        offset = 1
        for pos in child_positions:
            if pos < child_pos:
                offset += 1
        insert_pos = child_pos + offset
        child_positions.append(child_pos)

        perf.start("clone_root")
        new_root_actor = clone_actor_basic(root_actor)
        new_root_actor.name = new_name
        new_root_actor_path = root_actor_parent_path / new_name
        requests.append(
            AddActorRequest(
                new_root_actor,
                root_actor_parent_path,
                insert_pos,
                [],
            )
        )
        template_actor_paths.append(root_actor_path)

        perf.start("clone_subtree")
        for actor in ActorIterator(root_actor, include_root=False):
            actor, actor_path = self.local_scene.normalize_actor(actor)
            new_actor = clone_actor_basic(actor)
            dst_path = actor_path.replace_parent(root_actor_path, new_root_actor_path)
            new_parent_path = dst_path.parent()
            assert new_parent_path is not None
            requests.append(AddActorRequest(new_actor, new_parent_path, -1, []))
            template_actor_paths.append(actor_path)

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
        if self._is_duplicating:
            logger.debug("Already duplicating actors, skip duplicate_actors call.")
            return
        self._is_duplicating = True

        async with self._edit_lock:
            perf = perf_logger("SERVICE", "duplicate_actors.total")
            perf.start()
            await self._duplicate_actors(actors, undo, source)
            perf.end()

        self._is_duplicating = False

    async def _duplicate_actors(
        self, actors: Sequence[BaseActor | Path], undo: bool = True, source: str = ""
    ):
        perf = perf_logger("SERVICE", "duplicate_actors")

        _, actor_paths = self.normalize_and_clean_actors(actors)

        for path in actor_paths:
            if path.is_root():
                logger.error("Cannot duplicate root actor", path)
                return

        # 同一节点下的 actors 需要避免重名，按照父路径对 actor 进行分组。
        perf.start("group_paths_by_parent")
        parent_dict: Dict[Path, List[Path]] = {}
        for path in actor_paths:
            parent_path = path.parent()
            assert parent_path is not None
            if parent_path not in parent_dict:
                parent_dict[parent_path] = []
            parent_dict[parent_path].append(path)

        perf.start("build_add_requests")
        requests: List[AddActorRequest] = []
        template_actor_paths: List[Path] = []
        new_actor_paths: List[Path] = []
        for parent_path, paths in parent_dict.items():
            # 收集同一父路径下的已有名字，避免重复
            exsiting_names = []
            parent_actor, _ = self.local_scene.normalize_actor(parent_path)
            assert isinstance(parent_actor, GroupActor)
            for child in parent_actor.children:
                exsiting_names.append(child.name)

            child_positions: List[int] = []
            for path in paths:
                new_actor_path = self._duplicate_process_add_request(
                    requests,
                    template_actor_paths,
                    path,
                    exsiting_names,
                    child_positions,
                )
                new_actor_paths.append(new_actor_path)
                exsiting_names.append(new_actor_path.name())

        overrides = await self.remote_scene.get_actor_overrides_batch(
            template_actor_paths
        )
        for req, override in zip(requests, overrides):
            req.property_overrides = override

        # update selection
        # 复制操作后默认选中新的 actor，且保持 active 不变

        old_selection = self.local_scene.selection()
        new_selection = old_selection.clone()
        new_selection.selected_actors = new_actor_paths

        # commit changes

        bus = SceneEditNotificationBus()

        await bus.before_actor_added_batch()

        perf.start("local_scene.add_actor_batch")
        err = self.local_scene.add_actor_batch(requests)
        if err != "":
            # TODO: rollback if add failed
            logger.error("Local add_actor_batch failed: %s", err)
            raise Exception("Local add_actor_batch should not fail here.")

        perf.start("remote_scene.add_actor_batch")
        suceess, errors = await self.remote_scene.add_actor_batch(requests, True)
        if not suceess:
            # TODO: rollback if remote add failed
            logger.error("Remote add_actor_batch failed: %s", errors)
            raise Exception("Remote add_actor_batch failed.")

        perf.start("normalize_new_actors_and_sync_visibility_lock")
        new_actors, new_actor_paths = self.local_scene.normalize_actors(new_actor_paths)
        await self._sync_subtrees_visibility_lock_remote(new_actors)

        perf.start("find_non_overlapping_position")
        await self.remote_scene.custom_command("update_existing_aabbs")
        transform_paths = []
        transform_values = []
        for new_actor, new_actor_path in zip(new_actors, new_actor_paths):
            if isinstance(new_actor, AssetActor):
                pos = []
                await self.remote_scene.find_non_overlapping_position(
                    new_actor_path, pos
                )
                transform_paths.append(new_actor_path)
                transform_values.append(
                    Transform(
                        position=np.array([pos[0], pos[1], pos[2]]),
                        rotation=np.array([1.0, 0.0, 0.0, 0.0]),
                        scale=1.0,
                    )
                )
        perf.end()

        if transform_paths:
            perf.start("local_scene.update_transform_cache")
            await self.remote_scene.set_actor_transform_batch(
                transform_paths, transform_values
            )
            perf.start("local_scene.update_transform_cache")
            for actor_path, transform in zip(transform_paths, transform_values):
                actor = self.local_scene.find_actor_by_path(actor_path)
                if actor is not None:
                    actor._transform = transform
            perf.end()

        await self._set_selection(new_selection, undo=False, source=source)

        await bus.on_actor_added_batch("")

        if not undo:
            perf.end()
            return

        perf.start("record_undo")
        command_group = CommandGroup()
        select_command = SelectionCommand(old_selection, new_selection)
        duplicate_command = DuplicateActorsCommand(actor_paths, new_actor_paths)
        command_group.commands.append(duplicate_command)
        command_group.commands.append(select_command)
        UndoRequestBus().add_command(command_group)
        perf.end()

    @override
    async def set_property(
        self,
        property_key: ActorPropertyKey,
        value: Any,
        undo: bool = True,
        old_value: Any = None,
        source: str = "",
    ):
        bus = SceneEditNotificationBus()

        if undo and old_value is None:
            info = await self.remote_scene.get_property(property_key, True)
            old_value = info.value

        await self.remote_scene.set_property(property_key, value)
        self._post_process_dispatcher.on_property_set(property_key)

        await bus.on_properties_changed([property_key], [value], source)

        if undo:
            clean_key = property_key.clone()
            clean_key.entity_id = 0
            command = PropertyChangeCommand(clean_key, old_value, value)
            UndoRequestBus().add_command(command)

    @override
    async def start_change_property(
        self, property_key: ActorPropertyKey, old_value: Any, timeout: float
    ):
        async with asyncio.timeout(timeout):
            await self.property_edit_lock.acquire()
            logger.debug(
                f"start_change_property, key: {property_key}, old_value: {old_value}"
            )

            assert (
                self.property_key is None
            ), "Another property is already being edited."
            assert (
                self.old_property_value is None
            ), "Old property value should be None when starting a new property edit."

            self.old_property_value = old_value
            self.property_key = property_key

    @override
    async def end_change_property(self, property_key: ActorPropertyKey, new_value: Any):
        self.property_edit_lock.release()
        logger.debug(f"end_change_property, key: {property_key}, new_value:{new_value}")

        assert (
            self.property_key == property_key
        ), "Property key mismatch between start and end change property."
        assert self.old_property_value is not None, "Old property value is not set."
        assert type(new_value) == type(
            self.old_property_value
        ), "New value type does not match old value type."

        clean_key = property_key.clone()
        clean_key.entity_id = 0
        command = PropertyChangeCommand(clean_key, self.old_property_value, new_value)
        UndoRequestBus().add_command(command)

        self.old_property_value = None
        self.property_key = None

    @override
    async def set_transform(self, actor, transform, local, undo=True, source=""):
        """Leave for compatibility. Use set_transform_batch instead."""
        _actor, _actor_path = self.local_scene.get_actor_and_path(actor)
        _transform = transform.clone()

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
                self.local_scene.selected_actors
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
                self.local_scene.selected_actors
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
            out.append(self.local_scene.selected_actors)

    @override
    async def set_actor_visible(
        self,
        actor,
        visible,
        undo: bool = False,
        source: str = "",
    ):
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
    async def set_actor_locked(
        self,
        actor,
        locked,
        undo: bool = False,
        source: str = "",
    ):
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

    @override
    async def set_flycamera_transform(self, transform: Transform) -> None:
        await self.remote_scene.set_flycamera_transform(transform)
