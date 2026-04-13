import asyncio
from typing import Any, List, Tuple, override

import logging


from orcalab.actor_property import (
    ActorProperty,
    ActorPropertyGroup,
    ActorPropertyKey,
)
from orcalab.actor_util import (
    collect_properties,
    collect_properties_duplicate_data,
    make_unique_name,
)
from orcalab.application_util import get_local_scene
from orcalab.config_service import ConfigService
from orcalab.math import Transform
from orcalab.path import Path
from orcalab.actor import BaseActor, GroupActor, AssetActor
from orcalab.scene_edit_bus import (
    SceneEditNotificationBus,
    SceneEditNotification,
    SceneEditRequestBus,
)
from orcalab.scene_edit_types import AddActorRequest
from orcalab.state_sync_bus import (
    ManipulatorType,
    CameraMovementType,
    StateSyncNotificationBus,
)
from orcalab.ui.camera.camera_brief import CameraBrief
from orcalab.ui.camera.camera_bus import CameraNotificationBus
from orcalab.protos.edit_service_wrapper import CameraDataPNGResult, EditServiceWrapper

logger = logging.getLogger(__name__)


def _sync_tree_display_names(nodes: list) -> None:
    """递归同步关节叶节点的 display_name 与 Name 属性值。"""
    for node in nodes:
        _sync_tree_display_names(node.children)
        # 关节叶节点：name 不以 "e:" 开头
        if not node.name.startswith("e:"):
            for prop in node.properties:
                if prop.name() == "Name":
                    val = prop.value()
                    if isinstance(val, str) and val:
                        node.display_name = val
                    break


def _sync_joint_display_names(property_groups: list) -> None:
    """对 actor 的所有 property group 同步关节 display_name。"""
    for group in property_groups:
        _sync_tree_display_names(group.tree_data)


def _restore_original_values_recursive(src_nodes: list, dst_nodes: list) -> None:
    for src_node, dst_node in zip(src_nodes, dst_nodes):
        for src_prop, dst_prop in zip(src_node.properties, dst_node.properties):
            dst_prop.set_original_value(src_prop.original_value())
        _restore_original_values_recursive(src_node.children, dst_node.children)


def _apply_original_values_from_template(requests: list, errors: list) -> None:
    """复制 Actor 后，把源 Actor 的 original_value 传播到目标 Actor 的新属性对象，
    确保 is_modified() 正确反映相对于 asset 初始状态的修改（而非复制时已有的值）。
    必须在第二次 _fetch_and_set_properties 之后调用，因为那次调用会替换 property_groups。"""
    for request, error in zip(requests, errors):
        if error:
            continue
        if not isinstance(request.actor, AssetActor):
            continue
        if not isinstance(request.actor_template, AssetActor):
            continue

        src_groups = request.actor_template.property_groups
        dst_groups = request.actor.property_groups

        for src_group, dst_group in zip(src_groups, dst_groups):
            # 普通属性（跳过 TREE 容器属性）
            for src_prop, dst_prop in zip(src_group.properties, dst_group.properties):
                if src_prop.value_type().name == "TREE":
                    continue
                dst_prop.set_original_value(src_prop.original_value())

            # 树形属性（关节等）
            _restore_original_values_recursive(src_group.tree_data, dst_group.tree_data)


class _TrasformChangeList:
    def __init__(self):
        self.actor_paths: List[Path] = []
        self.transforms: List[Transform] = []

    def __repr__(self) -> str:
        return f"_TrasformChangeList({self.actor_paths})"


class RemoteScene(SceneEditNotification):
    def __init__(self, config_service: ConfigService):
        super().__init__()

        self.config_service = config_service

        self.edit_grpc_addr = f"localhost:{self.config_service.edit_port()}"
        self.executable_path = self.config_service.executable()

        self.in_query = False
        self.shutdown = False

        self._grpc_lock = asyncio.Lock()
        self._service = EditServiceWrapper()

    def connect_bus(self):
        SceneEditNotificationBus.connect(self)

    def disconnect_bus(self):
        SceneEditNotificationBus.disconnect(self)

    async def init_grpc(self):
        self._service.init_grpc(self.edit_grpc_addr)

        await self.change_sim_state(False)
        logger.info("已连接到服务器")

        # Start the pending operation loop.
        await self._query_pending_operation_loop()

    async def destroy_grpc(self):
        self.shutdown = True
        count = 3
        while self.in_query and count > 0:
            print("Waiting for pending operation query to finish...")
            await asyncio.sleep(0.1)
            count -= 1

        await self._service.destroy_grpc()

    async def _query_pending_operation_loop(self):
        if self.shutdown:
            return

        self.in_query = True

        operations = await self.query_pending_operation_loop()
        optimized_operations = self._optimize_operation(operations)
        for op in optimized_operations:
            try:
                await self._process_pending_operation(op)
            except Exception as e:
                logger.error(f"Failed to process pending operation '{op}': {e}")
                continue

        self.in_query = False

        await asyncio.sleep(0.01)
        if not self.shutdown:
            asyncio.create_task(self._query_pending_operation_loop())

    async def _process_pending_operation(self, op: str | _TrasformChangeList):
        logger.debug(f"op: {op}")

        if isinstance(op, _TrasformChangeList):
            transforms = await self._service.get_pending_actor_transform_batch(
                op.actor_paths
            )
            # Transform on backend will be updated by SceneEditService.
            await SceneEditRequestBus().set_transform_batch(
                op.actor_paths,
                transforms,
                undo=False,
                source="remote_scene",
            )
            return

        assert isinstance(op, str)

        if op == "start_transform_change":
            await SceneEditRequestBus().start_change_transform_batch([])
            return

        if op == "end_transform_change":
            await SceneEditRequestBus().end_change_transform_batch([])
            return

        prefix = "actor_delete:"
        if op.startswith(prefix):
            actor_path = Path(op[len(prefix) :])
            await SceneEditRequestBus().delete_actor(
                actor_path, undo=True, source="remote_scene"
            )
            return

        if op == "selection_change":
            actor_paths = await self.get_pending_selection_change()

            paths = []
            for p in actor_paths:
                paths.append(Path(p))

            await SceneEditRequestBus().set_selection(paths, source="remote_scene")
            return

        prefix = "active_actor_change:"
        if op.startswith(prefix):
            actor_path_str = op[len(prefix) :]
            actor_path = Path(actor_path_str) if actor_path_str else None
            await SceneEditRequestBus().set_active_actor(
                actor_path, source="remote_scene"
            )
            return
        
        prefix = "selection_and_active_change:"
        if op.startswith(prefix):
            actor_path_str = op[len(prefix) :]
            actor_path = Path(actor_path_str) if actor_path_str else None

            actor_paths = await self.get_pending_selection_change()

            paths = []
            for p in actor_paths:
                paths.append(Path(p))
            
            await SceneEditRequestBus().set_selection_and_active_actor(paths, actor_path, source="remote_scene")
            return

        # TODO: refactor using e-bus
        if op == "add_item":
            [transform, name] = await self.get_pending_add_item()

            actor_name = make_unique_name(name, Path("/"))

            actor = AssetActor(name=actor_name, asset_path=name)
            actor.transform = transform
            await SceneEditRequestBus().add_actor(
                actor, Path("/"), source="remote_scene"
            )
            return

        if op == "cameras_changed":
            cameras = await self.get_cameras()
            viewport_camera_index = await self.get_active_camera()
            bus = CameraNotificationBus()
            bus.on_cameras_changed(cameras, viewport_camera_index)
            return

        if op == "active_camera_changed":
            viewport_camera_index = await self.get_active_camera()
            bus = CameraNotificationBus()
            bus.on_viewport_camera_changed(viewport_camera_index)
            return

        prefix = "manipulator_type:"
        if op.startswith(prefix):
            value = op[len(prefix) :]
            if value == "translation":
                manipulator_type = ManipulatorType.Translate
            elif value == "rotation":
                manipulator_type = ManipulatorType.Rotate
            elif value == "scale":
                manipulator_type = ManipulatorType.Scale
            else:
                print(f"Unknown manipulator type: {value}")
                return

            bus = StateSyncNotificationBus()
            bus.on_manipulator_type_changed(manipulator_type)
            return

        prefix = "camera_movement_type:"
        if op.startswith(prefix):
            value = op[len(prefix) :]
            if value == "camera_translation":
                camera_movement_type = CameraMovementType.CameraTranslate
            elif value == "camera_rotation":
                camera_movement_type = CameraMovementType.CameraRotate
            elif value == "camera_scale":
                camera_movement_type = CameraMovementType.CameraScale
            else:
                camera_movement_type = CameraMovementType.CameraNone

            bus = StateSyncNotificationBus()
            bus.on_camera_movement_type_changed(camera_movement_type)
            return

        prefix = "debug_draw:"
        if op.startswith(prefix):
            value = op[len(prefix) :]
            enabled = value == "true"
            bus = StateSyncNotificationBus()
            bus.on_debug_draw_changed(enabled)
            return

        prefix = "user_control:"
        if op.startswith(prefix):
            value = op[len(prefix) :]
            enabled = value == "true"
            bus = StateSyncNotificationBus()
            bus.on_runtime_grab_changed(enabled)
            return

        print(f"Unknown pending operation: {op}")

    def _is_transform_change(self, op: str) -> bool:
        return op.startswith("transform_change:")

    def _parse_path(self, op: str) -> str:
        prefix = "transform_change:"
        if op.startswith(prefix):
            return op[len(prefix) :]
        return ""

    def _merge_transform_change(
        self, operations: List[str], start: int, end: int
    ) -> _TrasformChangeList:
        if start >= end:
            return _TrasformChangeList()

        path_set = set()
        result = _TrasformChangeList()

        for i in range(start, end):
            op = operations[i]
            if self._is_transform_change(op):
                actor_path = self._parse_path(op)
                if actor_path in path_set:
                    continue

                path_set.add(actor_path)
                result.actor_paths.append(Path(actor_path))

        return result

    def _optimize_operation(
        self, operations: List[str]
    ) -> List[str | _TrasformChangeList]:
        result = []

        size = len(operations)
        i = 0

        while i < size:
            op = operations[i]

            if self._is_transform_change(op):
                # Merge consecutive transform changes for the same actor.
                j = i + 1
                while j < size and self._is_transform_change(operations[j]):
                    j += 1

                merged_ops = self._merge_transform_change(operations, i, j)
                result.append(merged_ops)
                i = j
            else:
                result.append(op)
                i += 1

        return result

    @override
    async def on_actor_renamed(
        self,
        actor_path: Path,
        new_name: str,
        source: str,
    ):
        await self.rename_actor(actor_path, new_name)

    @override
    async def on_actor_visible_changed(
        self, actor_path: Path, paths_to_update: list, visible: bool, source: str = ""
    ):
        await self.actor_visible_change(visible, paths_to_update)

    @override
    async def on_actor_locked_changed(
        self, actor_path: Path, paths_to_update: list, locked: bool, source: str = ""
    ):
        await self.actor_locked_change(locked, paths_to_update)

    @override
    async def on_property_changed(
        self, property_key: ActorPropertyKey, value: Any, source: str
    ):
        await self.set_properties([property_key], [value])
        await self._sync_property_read_only_state(property_key)

    async def _sync_property_read_only_state(self, property_key: ActorPropertyKey):
        local_scene = get_local_scene()
        actor = local_scene.find_actor_by_path(property_key.actor_path)
        if not isinstance(actor, AssetActor):
            return

        property_groups = await self.get_property_groups(property_key.actor_path)

        for new_group in property_groups:
            if new_group.prefix != property_key.group_prefix:
                continue
            old_group = next(
                (g for g in actor.property_groups if g.prefix == new_group.prefix), None
            )
            if old_group is None:
                continue

            # 处理普通属性
            for new_prop in new_group.properties:
                old_prop = next(
                    (p for p in old_group.properties if p.name() == new_prop.name()),
                    None,
                )
                if old_prop is None:
                    continue

                if old_prop.is_read_only() != new_prop.is_read_only():
                    old_prop.set_read_only(new_prop.is_read_only())
                    await SceneEditNotificationBus().on_property_read_only_changed(
                        property_key.actor_path,
                        new_group.prefix,
                        new_prop.name(),
                        new_prop.is_read_only(),
                    )

            # 处理树形属性
            await self._sync_tree_read_only_state(
                property_key.actor_path,
                new_group,
                old_group,
            )

    async def _sync_tree_read_only_state(
        self,
        actor_path: Path,
        new_group: ActorPropertyGroup,
        old_group: ActorPropertyGroup,
    ):
        """同步树形属性的 read_only 状态"""
        from orcalab.actor_property import TreePropertyNode

        def sync_node(new_node: TreePropertyNode, old_node: TreePropertyNode | None):
            if old_node is None:
                return

            for new_prop in new_node.properties:
                old_prop = next(
                    (p for p in old_node.properties if p.name() == new_prop.name()),
                    None,
                )
                if old_prop is None:
                    continue

                if old_prop.is_read_only() != new_prop.is_read_only():
                    old_prop.set_read_only(new_prop.is_read_only())
                    # 构造完整属性名：节点名.属性名
                    full_prop_name = f"{new_node.name}.{new_prop.name()}"
                    asyncio.create_task(
                        SceneEditNotificationBus().on_property_read_only_changed(
                            actor_path,
                            new_group.prefix,
                            full_prop_name,
                            new_prop.is_read_only(),
                        )
                    )

            # 递归处理子节点
            for new_child in new_node.children:
                old_child = next(
                    (c for c in old_node.children if c.name == new_child.name), None
                )
                sync_node(new_child, old_child)

        # 同步树形数据的 read_only 状态（保留原有值，不替换整个 tree_data）
        for new_node in new_group.tree_data:
            old_node = next(
                (n for n in old_group.tree_data if n.name == new_node.name), None
            )
            sync_node(new_node, old_node)

    async def _fetch_actor_proprerties(self, actor: AssetActor, actor_path: Path):
        property_groups = await self.get_property_groups(actor_path)
        actor.property_groups = property_groups

        keys: List[ActorPropertyKey] = []
        props: List[ActorProperty] = []
        collect_properties(keys, props, property_groups, actor_path)

        values = await self.get_properties(keys)
        for prop, value in zip(props, values):
            prop.set_value(value)
            prop.set_original_value(value)

    ############################################################
    #
    #
    # Grpc methods
    #
    #
    ############################################################

    async def aloha(self) -> bool:
        async with self._grpc_lock:
            return await self._service.aloha()

    async def _fetch_and_set_properties(
        self, requests: List[AddActorRequest], errors: List[str]
    ):
        actors: List[AssetActor] = []
        actor_paths: List[Path] = []

        for req, error in zip(requests, errors):
            if error:
                continue

            if not isinstance(req.actor, AssetActor):
                continue

            actors.append(req.actor)
            actor_paths.append(req.parent_path.append(req.actor.name))

        if not actors:
            return

        property_groups_list = await self._service.get_property_groups_batch(
            actor_paths
        )

        keys: List[ActorPropertyKey] = []
        props: List[ActorProperty] = []
        for actor, actor_path, property_groups in zip(
            actors, actor_paths, property_groups_list
        ):
            actor.property_groups = property_groups
            collect_properties(keys, props, property_groups, actor_path)

        values = await self.get_properties(keys)
        for prop, value in zip(props, values):
            prop.set_value(value)
            prop.set_original_value(value)

        # 同步关节叶节点的 display_name 与 Name 属性值，确保 UI 按钮文字正确
        for actor in actors:
            _sync_joint_display_names(actor.property_groups)

    async def _apply_properties_from_template(
        self, requests: List[AddActorRequest], errors: List[str]
    ):
        keys: List[ActorPropertyKey] = []
        props: List[ActorProperty] = []
        values: List[Any] = []

        for request, error in zip(requests, errors):
            if error:
                continue

            if not isinstance(request.actor, AssetActor):
                continue

            if request.actor_template is None:
                continue

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

        await self._service.set_properties(keys, values)
        for key, prop, value in zip(keys, props, values):
            prop.set_value(value)

    async def add_actor_batch(
        self, requests: List[AddActorRequest], stop_on_error: bool
    ) -> Tuple[bool, List[str]]:
        print(f"add_actor_batch: {len(requests)} actors")
        async with self._grpc_lock:
            await self._service.custom_command("pause_render:true")
            success, errors = await self._service.add_actor_batch(
                requests, stop_on_error
            )
            await self._service.custom_command("pause_render:false")

            if not success and stop_on_error:
                raise Exception("Failed to add actors")

            await self._fetch_and_set_properties(requests, errors)
            await self._apply_properties_from_template(requests, errors)

            # 因为Readonly可能更新，所以我们再次全量更新。
            # TODO: 只针对Readonly属性进行更新，避免不必要的性能开销
            await self._fetch_and_set_properties(requests, errors)

            # 第二次 fetch 会替换 property_groups 并将 original_value 设为当前引擎值。
            # 对于复制的 actor，引擎已持有源 actor 的修改值，导致 is_modified() = False。
            # 此处从源 actor 恢复正确的 original_value，使 is_modified() 能准确标记修改。
            _apply_original_values_from_template(requests, errors)

            return success, errors

    async def delete_actor_batch(self, actor_paths: List[Path]) -> None:
        print(f"delete_actor_batch: {len(actor_paths)} actors")
        async with self._grpc_lock:
            await self._service.custom_command("pause_render:true")
            success, errors = await self._service.delete_actor_batch(actor_paths)
            await self._service.custom_command("pause_render:false")

            if not success:
                raise Exception("Failed to delete actors")

    async def query_pending_operation_loop(self) -> List[str]:
        async with self._grpc_lock:
            return await self._service.query_pending_operation_loop()

    async def get_pending_actor_transform(self, path: Path, local: bool) -> Transform:
        return await self._service.get_pending_actor_transform(path, local)

    async def set_actor_transform_batch(
        self, paths: List[Path], transforms: List[Transform]
    ):
        logger.debug(f"Setting transform batch for {len(paths)} actors")
        await self._service.set_actor_transform_batch(paths, transforms)

    async def publish_scene(self):
        logger.debug("Publishing scene...")
        async with self._grpc_lock:
            await self._service.publish_scene()

    async def get_sync_from_mujoco_to_scene(self) -> bool:
        async with self._grpc_lock:
            return await self._service.get_sync_from_mujoco_to_scene()

    async def set_sync_from_mujoco_to_scene(self, value: bool):
        async with self._grpc_lock:
            await self._service.set_sync_from_mujoco_to_scene(value)

    async def clear_scene(self):
        logger.debug("Clearing scene...")
        async with self._grpc_lock:
            await self._service.clear_scene()

    async def get_pending_selection_change(self) -> List[str]:
        async with self._grpc_lock:
            return await self._service.get_pending_selection_change()

    async def get_pending_add_item(self) -> Tuple[Transform, str]:
        async with self._grpc_lock:
            return await self._service.get_pending_add_item()

    async def set_selection(self, actor_paths: List[Path]):
        async with self._grpc_lock:
            await self._service.set_selection(actor_paths)

    async def get_actor_assets(self) -> List[str]:
        async with self._grpc_lock:
            return await self._service.get_actor_assets()

    async def save_state(self):
        print("Saving state...")
        async with self._grpc_lock:
            await self._service.save_state()

    async def restore_state(self):
        print("Restoring state...")
        async with self._grpc_lock:
            await self._service.restore_state()

    async def rename_actor(self, actor_path: Path, new_name: str):
        async with self._grpc_lock:
            await self._service.rename_actor(actor_path, new_name)

    async def move_actor_batch(
        self, actor_paths: List[Path], new_parent_paths: List[Path]
    ):
        async with self._grpc_lock:
            await self._service.move_actor_batch(actor_paths, new_parent_paths)

    async def actor_visible_change(self, visible: bool, paths_to_update: list):
        async with self._grpc_lock:
            await self._service.set_visibility(visible, paths_to_update)

    async def actor_locked_change(self, locked: bool, paths_to_update: list):
        async with self._grpc_lock:
            await self._service.set_lock(locked, paths_to_update)

    async def get_window_id(self):
        async with self._grpc_lock:
            await self._service.get_window_id()

    async def get_generate_pos(self, posX, posY) -> Transform:
        async with self._grpc_lock:
            return await self._service.get_generate_pos(posX, posY)

    async def get_cache_folder(self) -> str:
        async with self._grpc_lock:
            return await self._service.get_cache_folder()

    async def load_package(self, package_path: str) -> None:
        async with self._grpc_lock:
            await self._service.load_package(package_path)

    async def change_sim_state(self, sim_process_running: bool) -> bool:
        async with self._grpc_lock:
            return await self._service.change_sim_state(sim_process_running)

    async def change_manipulator_type(self, manipulator_type: ManipulatorType) -> bool:
        cmd = f"change_manipulator_type:{manipulator_type.name.lower()}"
        async with self._grpc_lock:
            return await self._service.custom_command(cmd)

    async def change_camera_movement_type(
        self, camera_movement_type: CameraMovementType
    ) -> bool:
        cmd = f"change_camera_movement_type:{camera_movement_type.name.lower()}"
        async with self._grpc_lock:
            return await self._service.custom_command(cmd)

    async def get_camera_png(self, camera_name: str, png_path: str, png_name: str):
        async with self._grpc_lock:
            response = await self._service.get_camera_png(
                camera_name, png_path, png_name
            )
            if not response:
                retry = 2
                while retry > 0:
                    response = await self._service.get_camera_png(
                        camera_name, png_path, png_name
                    )
                    if response:
                        break
                    retry -= 1
                    await asyncio.sleep(0.01)

    async def get_camera_data_png(
        self,
        camera_name: str,
        png_path: str,
        index: int,
        output: list[CameraDataPNGResult] = None,
    ) -> CameraDataPNGResult:
        async with self._grpc_lock:
            result = await self._service.get_camera_data_png(
                camera_name, png_path, index
            )
        if output is not None:
            output.append(result)
        return result

    async def get_actor_asset_aabb(self, actor_path: Path, output: List[float]):
        async with self._grpc_lock:
            await self._service.get_actor_asset_aabb(actor_path, output)

    async def queue_mouse_event(self, x: float, y: float, button: int, action: int):
        await self._service.queue_mouse_event(x, y, button, action)

    async def queue_mouse_wheel_event(self, delta: int):
        await self._service.queue_mouse_wheel_event(delta)

    async def queue_key_event(self, key: int, action: int):
        await self._service.queue_key_event(key, action)

    async def get_cameras(self) -> List[CameraBrief]:
        async with self._grpc_lock:
            return await self._service.get_cameras()

    async def get_active_camera(self) -> int:
        async with self._grpc_lock:
            return await self._service.get_active_camera()

    async def set_active_camera(self, camera_index: int) -> None:
        async with self._grpc_lock:
            await self._service.set_active_camera(camera_index)

    async def get_viewport_camera_transform(self) -> Transform:
        async with self._grpc_lock:
            return await self._service.get_viewport_camera_transform()

    async def get_property_groups(self, actor_path: Path) -> List[ActorPropertyGroup]:
        return await self._service.get_property_groups(actor_path)

    async def get_property_groups_batch(
        self, actor_paths: List[Path]
    ) -> List[List[ActorPropertyGroup]]:
        return await self._service.get_property_groups_batch(actor_paths)

    async def get_properties(self, keys: List[ActorPropertyKey]) -> List[Any]:
        return await self._service.get_properties(keys)

    async def set_properties(self, keys: List[ActorPropertyKey], values: List[Any]):
        await self._service.set_properties(keys, values)

    async def set_highlight_entity(self, entity_id: int, highlight: bool):
        async with self._grpc_lock:
            await self._service.set_highlight_joint(entity_id, highlight)

    async def custom_command(self, command: str):
        async with self._grpc_lock:
            return await self._service.custom_command(command)

    async def set_move_rotate_sensitivity(
        self, move_sensitivity: float, rotate_sensitivity: float
    ):
        logger.info(
            f"Setting move rotate sensitivity: {move_sensitivity}, {rotate_sensitivity}"
        )
        async with self._grpc_lock:
            return await self._service.set_move_rotate_sensitivity(
                move_sensitivity, rotate_sensitivity
            )

    async def set_active_actor(self, actor: Path | None):
        async with self._grpc_lock:
            await self._service.custom_command(
                f"set_active_actor:{actor.string() if actor else ''}"
            )
