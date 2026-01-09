import asyncio
from typing import Any, List, Tuple, override

import logging


from orcalab.actor_property import (
    ActorProperty,
    ActorPropertyGroup,
    ActorPropertyKey,
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
        while self.in_query:
            print("Waiting for pending operation query to finish...")
            await asyncio.sleep(0.1)

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
        # print(op)
        sltc = "start_local_transform_change:"
        if op.startswith(sltc):
            actor_path = Path(op[len(sltc) :])
            self._start_transform_change(actor_path, local=True)

        eltc = "end_local_transform_change:"
        if op.startswith(eltc):
            actor_path = Path(op[len(eltc) :])
            await self._end_transform_change(actor_path, local=True)

        swtc = "start_world_transform_change:"
        if op.startswith(swtc):
            actor_path = Path(op[len(swtc) :])
            self._start_transform_change(actor_path, local=False)

        ewtc = "end_world_transform_change:"
        if op.startswith(ewtc):
            actor_path = Path(op[len(ewtc) :])
            await self._end_transform_change(actor_path, local=False)

        local_transform_change = "local_transform_change:"
        if op.startswith(local_transform_change):
            actor_path = Path(op[len(local_transform_change) :])
            await self._fetch_and_set_transform(actor_path, local=True)

        world_transform_change = "world_transform_change:"
        if op.startswith(world_transform_change):
            actor_path = Path(op[len(world_transform_change) :])
            await self._fetch_and_set_transform(actor_path, local=False)

        ad = "actor_delete:"
        if op.startswith(ad):
            actor_path = Path(op[len(ad) :])
            await SceneEditRequestBus().delete_actor(
                actor_path, undo=True, source="remote"
            )

        selection_change = "selection_change"
        if op.startswith(selection_change):
            actor_paths = await self.get_pending_selection_change()

            paths = []
            for p in actor_paths:
                paths.append(Path(p))

            await SceneEditRequestBus().set_selection(paths, source="remote_scene")

        # TODO: refactor using e-bus
        add_item = "add_item"
        if op.startswith(add_item):
            [transform, name] = await self.get_pending_add_item()

            actor_name = make_unique_name(name, Path("/"))

            actor = AssetActor(name=actor_name, asset_path=name)
            actor.transform = transform
            await SceneEditRequestBus().add_actor(
                actor, Path("/"), source="remote_scene"
            )

        if op == "cameras_changed":
            cameras = await self.get_cameras()
            viewport_camera_index = await self.get_active_camera()
            bus = CameraNotificationBus()
            bus.on_cameras_changed(cameras, viewport_camera_index)

        if op == "active_camera_changed":
            viewport_camera_index = await self.get_active_camera()
            bus = CameraNotificationBus()
            bus.on_viewport_camera_changed(viewport_camera_index)

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

    async def _fetch_actor_proprerties(self, actor: AssetActor, actor_path: Path):
        property_groups = await self.get_property_groups(actor_path)
        actor.property_groups = property_groups

        keys: List[ActorPropertyKey] = []
        props: List[ActorProperty] = []
        for group in property_groups:
            for prop in group.properties:
                key = ActorPropertyKey(
                    actor_path,
                    group.prefix,
                    prop.name(),
                    prop.value_type(),
                )
                keys.append(key)
                props.append(prop)

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

    async def save_body_transform(self):
        async with self._grpc_lock:
            await self._service.save_body_transform()

    async def restore_body_transform(self):
        async with self._grpc_lock:
            await self._service.restore_body_transform()

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
