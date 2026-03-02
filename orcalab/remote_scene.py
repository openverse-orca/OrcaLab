import asyncio
from typing import Any, List, Tuple, override

import logging


from orcalab.actor_property import (
    ActorProperty,
    ActorPropertyGroup,
    ActorPropertyKey,
    TreePropertyNode,
)
from orcalab.actor_util import make_unique_name
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
from orcalab.state_sync_bus import ManipulatorType, StateSyncNotificationBus
from orcalab.ui.camera.camera_brief import CameraBrief
from orcalab.ui.camera.camera_bus import CameraNotificationBus
from orcalab.protos.edit_service_wrapper import EditServiceWrapper

logger = logging.getLogger(__name__)


class RemoteScene(SceneEditNotification):
    def __init__(self, config_service: ConfigService):
        super().__init__()

        self.config_service = config_service

        self.edit_grpc_addr = f"localhost:{self.config_service.edit_port()}"
        self.executable_path = self.config_service.executable()

        self.in_query = False
        self.shutdown = False

        self.current_transform: Transform | None = None

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

    async def _process_pending_operation(self, op: str):
        print(op)
        prefix = "start_local_transform_change:"
        if op.startswith(prefix):
            actor_path = Path(op[len(prefix) :])
            self._start_transform_change(actor_path, local=True)
            return

        prefix = "end_local_transform_change:"
        if op.startswith(prefix):
            actor_path = Path(op[len(prefix) :])
            await self._end_transform_change(actor_path, local=True)
            return

        prefix = "start_world_transform_change:"
        if op.startswith(prefix):
            actor_path = Path(op[len(prefix) :])
            self._start_transform_change(actor_path, local=False)
            return

        prefix = "end_world_transform_change:"
        if op.startswith(prefix):
            actor_path = Path(op[len(prefix) :])
            await self._end_transform_change(actor_path, local=False)
            return

        prefix = "local_transform_change:"
        if op.startswith(prefix):
            actor_path = Path(op[len(prefix) :])
            await self._fetch_and_set_transform(actor_path, local=True)
            return

        prefix = "world_transform_change:"
        if op.startswith(prefix):
            actor_path = Path(op[len(prefix) :])
            await self._fetch_and_set_transform(actor_path, local=False)
            return

        prefix = "actor_delete:"
        if op.startswith(prefix):
            actor_path = Path(op[len(prefix) :])
            await SceneEditRequestBus().delete_actor(
                actor_path, undo=True, source="remote"
            )
            return

        if op == "selection_change":
            actor_paths = await self.get_pending_selection_change()

            paths = []
            for p in actor_paths:
                paths.append(Path(p))

            await SceneEditRequestBus().set_selection(paths, source="remote_scene")
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

    def _optimize_operation(self, operations: List[str]) -> List[str]:
        result = []

        size = len(operations)

        def _is_transform_change(op: str) -> bool:
            return op.startswith("local_transform_change:") or op.startswith(
                "world_transform_change:"
            )

        for i in range(size):
            op = operations[i]

            if _is_transform_change(op):
                # Skip intermediate transform changes.
                if i + 1 < size:
                    next_op = operations[i + 1]
                    if _is_transform_change(next_op):
                        continue

            result.append(op)

        return result

    def _start_transform_change(self, actor_path: Path, local: bool):
        SceneEditRequestBus().start_change_transform(actor_path)

        local_scene = get_local_scene()
        actor = local_scene.find_actor_by_path(actor_path)
        assert actor is not None

        if local:
            self.current_transform = actor.transform
        else:
            self.current_transform = actor.world_transform

    async def _end_transform_change(self, actor_path: Path, local: bool):
        assert isinstance(self.current_transform, Transform)
        await SceneEditRequestBus().set_transform(
            actor_path,
            self.current_transform,
            local=local,
            undo=True,
            source="remote_scene",
        )

        SceneEditRequestBus().end_change_transform(actor_path)

        self.current_transform = None

    async def _fetch_and_set_transform(self, actor_path: Path, local: bool):
        self.current_transform = await self.get_pending_actor_transform(
            actor_path, local=True
        )

        await SceneEditRequestBus().set_transform(
            actor_path,
            self.current_transform,
            local=True,
            undo=False,
            source="remote_scene",
        )

        # Transform on viewport will be updated by on_transform_changed.

    @override
    async def on_transform_changed(
        self,
        actor_path: Path,
        transform: Transform,
        local: bool,
        source: str,
    ):
        # We still need to set the transform to viewport, even if source is "remote_scene".
        # This is by design.
        await self.set_actor_transform(actor_path, transform, local)

    @override
    async def on_selection_changed(self, old_selection, new_selection, source=""):
        if source == "remote_scene":
            return

        await self.set_selection(new_selection)

    @override
    async def on_actor_added(
        self,
        actor: BaseActor,
        parent_actor_path: Path,
        source: str,
    ):
        await self.add_actor(actor, parent_actor_path)
        actor_path = parent_actor_path.append(actor.name)
        if isinstance(actor, AssetActor):
            await self._fetch_actor_proprerties(actor, actor_path)

    @override
    async def on_actor_deleted(
        self,
        actor_path: Path,
        source: str,
    ):
        await self.delete_actor(actor_path)

    @override
    async def on_actor_renamed(
        self,
        actor_path: Path,
        new_name: str,
        source: str,
    ):
        await self.rename_actor(actor_path, new_name)

    @override
    async def on_actor_reparented(
        self,
        actor_path: Path,
        new_parent_path: Path,
        row: int,
        source: str,
    ):
        await self.reparent_actor(actor_path, new_parent_path)

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

    def _collect_tree_property_keys(
        self,
        actor_path: Path,
        group_prefix: str,
        node: TreePropertyNode,
        keys: List[ActorPropertyKey],
        props: List[ActorProperty],
    ):
        """递归收集树形属性的子属性 key"""
        for prop in node.properties:
            full_name = f"{node.name}.{prop.name()}"
            key = ActorPropertyKey(
                actor_path,
                group_prefix,
                full_name,
                prop.value_type(),
            )
            keys.append(key)
            props.append(prop)

        for child in node.children:
            self._collect_tree_property_keys(
                actor_path, group_prefix, child, keys, props
            )

    async def _fetch_actor_proprerties(self, actor: AssetActor, actor_path: Path):
        from orcalab.actor_property import ActorPropertyType

        property_groups = await self.get_property_groups(actor_path)
        actor.property_groups = property_groups

        keys: List[ActorPropertyKey] = []
        props: List[ActorProperty] = []
        for group in property_groups:
            for prop in group.properties:
                # TREE 类型的属性没有直接值，跳过获取
                if prop.value_type() == ActorPropertyType.TREE:
                    continue
                key = ActorPropertyKey(
                    actor_path,
                    group.prefix,
                    prop.name(),
                    prop.value_type(),
                )
                keys.append(key)
                props.append(prop)

            # 收集树形属性的子属性
            for tree_node in group.tree_data:
                self._collect_tree_property_keys(
                    actor_path, group.prefix, tree_node, keys, props
                )

        values = await self.get_properties(keys)
        for prop, value in zip(props, values):
            prop.set_value(value)

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

    async def query_pending_operation_loop(self) -> List[str]:
        async with self._grpc_lock:
            return await self._service.query_pending_operation_loop()

    async def get_pending_actor_transform(self, path: Path, local: bool) -> Transform:
        return await self._service.get_pending_actor_transform(path, local)

    async def add_actor(self, actor: BaseActor, parent_path: Path):
        async with self._grpc_lock:
            if isinstance(actor, GroupActor):
                await self._service.add_group_actor(actor, parent_path)
            elif isinstance(actor, AssetActor):
                await self._service.add_asset_actor(actor, parent_path)
            else:
                raise Exception(f"Unsupported actor type: {type(actor)}")

    async def set_actor_transform(self, path: Path, transform: Transform, local: bool):
        await self._service.set_actor_transform(path, transform, local)

    async def publish_scene(self):
        async with self._grpc_lock:
            await self._service.publish_scene()

    async def get_sync_from_mujoco_to_scene(self) -> bool:
        async with self._grpc_lock:
            return await self._service.get_sync_from_mujoco_to_scene()

    async def set_sync_from_mujoco_to_scene(self, value: bool):
        async with self._grpc_lock:
            await self._service.set_sync_from_mujoco_to_scene(value)

    async def clear_scene(self):
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
        async with self._grpc_lock:
            await self._service.save_state()

    async def restore_state(self):
        async with self._grpc_lock:
            await self._service.restore_state()

    async def delete_actor(self, actor_path: Path):
        async with self._grpc_lock:
            await self._service.delete_actor(actor_path)

    async def rename_actor(self, actor_path: Path, new_name: str):
        await self._service.rename_actor(actor_path, new_name)

    async def reparent_actor(self, actor_path: Path, new_parent_path: Path):
        await self._service.reparent_actor(actor_path, new_parent_path)

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

    async def change_manipulator_type(self, manipulator_type: int) -> bool:
        async with self._grpc_lock:
            return await self._service.change_manipulator_type(manipulator_type)

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

    async def get_property_groups(self, actor_path: Path) -> List[ActorPropertyGroup]:
        return await self._service.get_property_groups(actor_path)

    async def get_properties(self, keys: List[ActorPropertyKey]) -> List[Any]:
        return await self._service.get_properties(keys)

    async def set_properties(self, keys: List[ActorPropertyKey], values: List[Any]):
        await self._service.set_properties(keys, values)

    async def custom_command(self, command: str):
        async with self._grpc_lock:
            return await self._service.custom_command(command)
