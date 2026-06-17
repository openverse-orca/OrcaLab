import asyncio
from typing import Any, Dict, List, Tuple, override

import logging
import time
from itertools import combinations

from attr import dataclass
import requests

from orcalab.actor_property import (
    ActorEntities,
    ActorPropertyGroup,
    ActorPropertyKey,
    PropertyGetInfo,
    PropertyOverride,
)
from orcalab.actor_util import (
    make_unique_name,
)
from orcalab.camera_data_png_result import CameraDataPNGResult
from orcalab.config_service import ConfigService
from orcalab.entity_info import EntityInfo
from orcalab.entity_path import EntityPath
from orcalab.local_scene import LocalScene
from orcalab.math import Transform
from orcalab.path import Path
from orcalab.actor import BaseActor, GroupActor, AssetActor
from orcalab.scene_edit_bus import (
    SceneEditNotificationBus,
    SceneEditNotification,
    SceneEditRequestBus,
)
from orcalab.scene_edit_types import AddActorRequest
from orcalab.selection_data import BackendSelectionData, SelectionData
from orcalab.state_sync_bus import (
    ManipulatorType,
    CameraMovementType,
    MeasureType,
    PivotPointType,
    StateSyncNotificationBus,
)
from orcalab.ui.camera.camera_brief import CameraBrief
from orcalab.ui.camera.camera_bus import CameraNotificationBus
from orcalab.protos.edit_service_wrapper import EditServiceWrapper

logger = logging.getLogger(__name__)


class _TrasformChangeList:
    def __init__(self):
        self.actor_paths: List[Path] = []
        self.transforms: List[Transform] = []

    def __repr__(self) -> str:
        return f"_TrasformChangeList({self.actor_paths})"


class RemoteScene(SceneEditNotification):
    def __init__(self, config_service: ConfigService, local_scene: LocalScene):
        super().__init__()

        self.config_service = config_service
        self.local_scene = local_scene

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
        _t0 = time.monotonic()
        self._service.init_grpc(self.edit_grpc_addr)
        logger.info("init_grpc channel 创建完成, 耗时: %.2f 秒", time.monotonic() - _t0)

        _t1 = time.monotonic()
        await self.change_sim_state(False)
        logger.info(
            "change_sim_state(False) 完成, 耗时: %.2f 秒", time.monotonic() - _t1
        )
        logger.info("已连接到服务器")

        # Start the pending operation loop.
        _t2 = time.monotonic()
        await self._query_pending_operation_loop()
        logger.info(
            "_query_pending_operation_loop 首次完成, 耗时: %.2f 秒",
            time.monotonic() - _t2,
        )

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
            backend_selection = await self.get_pending_selection_change()
            selection = self._to_selection_data(backend_selection)
            await SceneEditRequestBus().set_selection(selection, source="remote_scene")
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
                manipulator_type = ManipulatorType.ManipulatorNone

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

        prefix = "measure_type:"
        if op.startswith(prefix):
            value = op[len(prefix) :]
            if value == "distance":
                measure_type = MeasureType.Distance
            elif value == "angle":
                measure_type = MeasureType.Angle
            else:
                measure_type = MeasureType.MeasureNone

            bus = StateSyncNotificationBus()
            bus.on_measure_type_changed(measure_type)
            return

        prefix = "pivot_point_type:"
        if op.startswith(prefix):
            value = op[len(prefix) :]
            if value == "individualcenter":
                pivot_point_type = PivotPointType.IndividualCenter
            elif value == "boundingboxcenter":
                pivot_point_type = PivotPointType.BoundingBoxCenter
            elif value == "medianpoint":
                pivot_point_type = PivotPointType.MedianPoint
            elif value == "activeactor":
                pivot_point_type = PivotPointType.ActiveActor
            else:
                pivot_point_type = PivotPointType.Default

            bus = StateSyncNotificationBus()
            bus.on_pivot_point_type_changed(pivot_point_type)
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

        logger.debug(f"Unknown pending operation: {op}")

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
    async def on_actor_visible_changed(
        self, actor_path: Path, paths_to_update: list, visible: bool, source: str = ""
    ):
        await self.actor_visible_change(visible, paths_to_update)

    @override
    async def on_actor_locked_changed(
        self, actor_path: Path, paths_to_update: list, locked: bool, source: str = ""
    ):
        await self.actor_locked_change(locked, paths_to_update)

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

    async def _fetch_entity_heirarchy(self, requests: List[AddActorRequest]):
        asset_actor_paths = []
        for request in requests:
            asset_actor_paths.append(request.parent_path / request.actor.name)

        if not asset_actor_paths:
            return

        infos = await self._service.get_entity_hierarchy_batch(asset_actor_paths)
        for actor_path, info in zip(asset_actor_paths, infos):
            if info is None:
                continue
            self.local_scene.set_entity_root(actor_path, info)

    async def _apply_overrides(self, requests: List[AddActorRequest]):
        keys: List[ActorPropertyKey] = []
        values: List[Any] = []
        for request in requests:
            if not request.property_overrides:
                continue

            actor_path = request.parent_path / request.actor.name
            actor = self.local_scene.find_actor_by_path(actor_path)
            if actor is None:
                logger.error(f"Actor not found for path: {actor_path}")
                continue

            entity_root = actor.entity_root
            for override in request.property_overrides:
                entity_id = entity_root.find_entity_id_by_path(override.entity_path)
                if entity_id == 0:
                    logger.error(
                        f"Entity not found for path: {override.entity_path} in actor: {actor_path}"
                    )
                    continue

                key = ActorPropertyKey(
                    actor_path=actor_path,
                    entity_id=entity_id,
                    entity_path=override.entity_path,
                    component_type_id=override.component_type_id,
                    component_type_index=override.component_type_index,
                    property_name=override.property_name,
                    property_type=override.property_type,
                )

                keys.append(key)
                values.append(override.value)

        await self._service.set_properties(keys, values)

    async def add_actor_batch(
        self, requests: List[AddActorRequest], stop_on_error: bool
    ) -> Tuple[bool, List[str]]:
        logger.debug(f"add_actor_batch: {len(requests)} actors")
        async with self._grpc_lock:
            success, errors = await self._service.add_actor_batch(
                requests, stop_on_error
            )

        if not success and stop_on_error:
            raise Exception("Failed to add actors")

        await self._fetch_entity_heirarchy(requests)
        await self._apply_overrides(requests)

        return success, errors

    async def delete_actor_batch(self, actor_paths: List[Path]) -> None:
        logger.debug(f"delete_actor_batch: {len(actor_paths)} actors")
        async with self._grpc_lock:
            await self._service.custom_command("pause_render:true")
            try:
                success, errors = await self._service.delete_actor_batch(actor_paths)
            finally:
                await self._service.custom_command("pause_render:false")

            if not success:
                raise Exception("Failed to delete actors")

    async def query_pending_operation_loop(self) -> List[str]:
        async with self._grpc_lock:
            return await self._service.query_pending_operation_loop()

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

    async def get_pending_selection_change(self) -> BackendSelectionData:
        async with self._grpc_lock:
            return await self._service.get_pending_selection_change()

    async def get_pending_add_item(self) -> Tuple[Transform, str]:
        async with self._grpc_lock:
            return await self._service.get_pending_add_item()

    async def set_selection(self, selection: SelectionData):
        async with self._grpc_lock:
            backend_selection = self._to_backend_selection_data(selection)
            await self._service.set_selection(backend_selection)

    async def get_actor_assets(self) -> List[str]:
        async with self._grpc_lock:
            return await self._service.get_actor_assets()

    async def get_assets_by_type_page(
        self, asset_type_uuid: str, page_index: int, page_size: int
    ):
        async with self._grpc_lock:
            return await self._service.get_assets_by_type_page(
                asset_type_uuid, page_index, page_size
            )

    async def save_state(self):
        logger.debug("Saving state...")
        async with self._grpc_lock:
            await self._service.save_state()

    async def restore_state(self):
        logger.debug("Restoring state...")
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

    async def change_manipulator_type(self, manipulator_type: ManipulatorType) -> None:
        cmd = f"change_manipulator_type:{manipulator_type.name.lower()}"
        async with self._grpc_lock:
            return await self._service.custom_command(cmd)

    async def change_camera_movement_type(
        self, camera_movement_type: CameraMovementType
    ) -> None:
        cmd = f"change_camera_movement_type:{camera_movement_type.name.lower()}"
        async with self._grpc_lock:
            return await self._service.custom_command(cmd)

    async def change_measure_type(self, measure_type: MeasureType) -> None:
        cmd = f"change_measure_type:{measure_type.name.lower()}"
        async with self._grpc_lock:
            return await self._service.custom_command(cmd)

    async def change_pivot_point_type(self, pivot_point_type: PivotPointType) -> None:
        cmd = f"change_pivot_point_type:{pivot_point_type.name.lower()}"
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
        output: list[CameraDataPNGResult],
    ) -> CameraDataPNGResult:
        async with self._grpc_lock:
            result = await self._service.get_camera_data_png(
                camera_name, png_path, index
            )
        output.append(result)
        return result

    async def get_actor_asset_aabb(self, actor_path: Path, output: List[float]):
        async with self._grpc_lock:
            await self._service.get_actor_asset_aabb(actor_path, output)

    async def find_non_overlapping_position(
        self, actor_path: Path, output: List[float]
    ):
        async with self._grpc_lock:
            await self._service.find_non_overlapping_position(actor_path, output)

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

    async def get_flycamera_transform(self) -> Transform:
        async with self._grpc_lock:
            return await self._service.get_flycamera_transform()

    async def set_flycamera_transform(self, flycamera_transform: Transform) -> None:
        async with self._grpc_lock:
            await self._service.set_flycamera_transform(flycamera_transform)

    async def get_viewport_camera_transform(self) -> Transform:
        async with self._grpc_lock:
            return await self._service.get_viewport_camera_transform()

    def _fill_entity_id(self, keys: List[ActorPropertyKey]) -> List[ActorPropertyKey]:
        new_keys = [key.clone() for key in keys]
        for key in new_keys:
            if key.entity_id != 0:
                continue

            entity_id = self.local_scene.find_entity_id(key.actor_path, key.entity_path)
            if entity_id == 0:
                logger.error(
                    f"Entity not found for path: {key.entity_path} in actor: {key.actor_path}"
                )
                continue
            key.entity_id = entity_id
        return new_keys

    async def get_properties(
        self, keys: List[ActorPropertyKey], refill_entity_id: bool
    ) -> List[PropertyGetInfo]:

        new_keys = self._fill_entity_id(keys)

        return await self._service.get_properties(new_keys)

    async def get_property(
        self, key: ActorPropertyKey, refill_entity_id: bool
    ) -> PropertyGetInfo:
        result = await self.get_properties([key], refill_entity_id)
        assert result and len(result) > 0
        return result[0]

    async def set_properties(
        self,
        keys: List[ActorPropertyKey],
        values: List[Any],
    ):
        new_keys = self._fill_entity_id(keys)
        await self._service.set_properties(new_keys, values)

    async def set_property(
        self,
        key: ActorPropertyKey,
        value: Any,
    ):
        await self.set_properties([key], [value])

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

    def _has_same_type_property_group(self, groups: List[ActorPropertyGroup]) -> bool:
        if len(groups) < 2:
            return False

        # groups size is small.
        for a, b in combinations(groups, 2):
            if a.component_type_id == b.component_type_id:
                return True
        return False

    def _fill_frontend_info(
        self,
        actor_entities: ActorEntities,
        ll: List[List[ActorPropertyGroup]],
    ):
        actor = self.local_scene.find_actor_by_path(actor_entities.actor_path)
        if actor is None:
            logger.error(
                "Actor not found for path: " + actor_entities.actor_path.string()
            )
            return

        for entity_id, property_groups in zip(actor_entities.entity_ids, ll):
            entity_path = actor.entity_root.find_entity_path_by_id(entity_id)
            if entity_path is None:
                logger.error("Entity not found for id: " + str(entity_id))
                continue
            self._fill_frontend_info_1(property_groups, entity_path)

    def _fill_frontend_info_1(
        self, entity_groups: List[ActorPropertyGroup], entity_path: EntityPath
    ):
        if self._has_same_type_property_group(entity_groups):
            # If there are multiple property groups of the same type, we need to fill in the component index.
            type_count = {}
            for group in entity_groups:
                if group.component_type_id not in type_count:
                    type_count[group.component_type_id] = 0
                else:
                    type_count[group.component_type_id] += 1
                group.component_type_index = type_count[group.component_type_id]
                group.entity_path = entity_path
        else:
            for group in entity_groups:
                group.component_type_index = 0
                group.entity_path = entity_path

    async def _get_entity_property_groups_batch(
        self, actor_entities_list: List[ActorEntities]
    ) -> List[List[List[ActorPropertyGroup]]]:
        lll = await self._service.get_entity_property_groups_batch(actor_entities_list)

        for actor_entities, ll in zip(actor_entities_list, lll):
            self._fill_frontend_info(actor_entities, ll)

        return lll

    async def get_entity_property_groups_batch(
        self, actor_entities_list: List[ActorEntities]
    ) -> List[List[List[ActorPropertyGroup]]]:
        async with self._grpc_lock:
            return await self._get_entity_property_groups_batch(actor_entities_list)

    async def get_entity_property_groups(
        self, actor_entities: ActorEntities
    ) -> List[List[ActorPropertyGroup]]:
        async with self._grpc_lock:
            result = await self._get_entity_property_groups_batch([actor_entities])
            if result and len(result) > 0:
                return result[0]
            return []

    async def _get_entity_property_groups_single(
        self, actor_path: Path, entity_id: int
    ) -> List[ActorPropertyGroup]:
        actor_entities = ActorEntities(actor_path, [entity_id])
        result = await self._get_entity_property_groups_batch([actor_entities])
        if result and len(result) > 0 and len(result[0]) > 0:
            return result[0][0]
        return []

    async def _get_actor_property_groups_batch(
        self, actor_paths: List[Path]
    ) -> List[List[ActorPropertyGroup]]:
        ll = await self._service.get_actor_property_groups_batch(actor_paths)

        for actor_path, property_groups in zip(actor_paths, ll):
            actor = self.local_scene.find_actor_by_path(actor_path)
            if actor is None:
                logger.error("Actor not found for path: " + actor_path.string())
                continue

            entity_path = actor.entity_root.root_entity_info.entity_path
            self._fill_frontend_info_1(property_groups, entity_path)

        return ll

    async def get_actor_property_groups_batch(
        self, actor_paths: List[Path]
    ) -> List[List[ActorPropertyGroup]]:
        async with self._grpc_lock:
            return await self._get_actor_property_groups_batch(actor_paths)

    async def get_actor_property_groups(
        self, actor_path: Path
    ) -> List[ActorPropertyGroup]:
        async with self._grpc_lock:
            result = await self._get_actor_property_groups_batch([actor_path])
            if result and len(result) > 0:
                return result[0]
            return []

    def _fill_actor_override_info(
        self, actor_path: Path, overrides: List[PropertyOverride]
    ):
        actor = self.local_scene.find_actor_by_path(actor_path)
        if actor is None:
            logger.error("Actor not found for path: " + actor_path.string())
            overrides.clear()
            return

        for override in overrides:
            if override.entity_id == 0:
                continue
            entity_path = actor.entity_root.find_entity_path_by_id(override.entity_id)
            if entity_path is None:
                logger.error(
                    "Entity not found for id: "
                    + str(override.entity_id)
                    + " in actor: "
                    + actor_path.string()
                )
                continue
            override.entity_path = entity_path

    async def _get_actor_overrides_batch(
        self, actor_paths_list: List[List[Path]]
    ) -> List[List[List[PropertyOverride]]]:
        lll = await self._service.get_actor_overrides_batch(actor_paths_list)
        for actor_paths, ll in zip(actor_paths_list, lll):
            for actor_path, overrides in zip(actor_paths, ll):
                self._fill_actor_override_info(actor_path, overrides)
        return lll

    async def get_actor_overrides_batch_grouped(
        self, actor_paths_list: List[List[Path]]
    ) -> List[List[List[PropertyOverride]]]:
        async with self._grpc_lock:
            return await self._get_actor_overrides_batch(actor_paths_list)

    async def get_actor_overrides_batch(
        self, actor_paths_list: List[Path]
    ) -> List[List[PropertyOverride]]:
        async with self._grpc_lock:
            result = await self._get_actor_overrides_batch([actor_paths_list])
            if result and len(result) > 0:
                return result[0]
            return []

    def _to_backend_selection_data(
        self, selection: SelectionData
    ) -> BackendSelectionData:
        data = BackendSelectionData(
            selection.selected_actors, selection.active_actor_path
        )

        if selection.active_entity_path.empty():
            return data

        if selection.active_actor_path is None:
            logger.error("Active actor is None while active entity is set")
            return data

        actor = self.local_scene.find_actor_by_path(selection.active_actor_path)
        if not isinstance(actor, AssetActor):
            logger.error("Active actor is not an AssetActor while active entity is set")
            return data

        entity_id = actor.entity_root.find_entity_id_by_path(
            selection.active_entity_path
        )
        if entity_id == 0:
            logger.error(
                "Failed to find entity id by path: "
                + selection.active_entity_path.string()
            )
            return data

        data.active_entity = entity_id
        return data

    def _to_selection_data(
        self, backend_selection: BackendSelectionData
    ) -> SelectionData:
        data = SelectionData(
            backend_selection.selected_actors, backend_selection.active_actor
        )

        if backend_selection.active_entity == 0:
            return data

        if backend_selection.active_actor is None:
            logger.error("Active entity is set but active actor is None")
            return data

        actor = self.local_scene.find_actor_by_path(backend_selection.active_actor)
        if not actor:
            logger.error(
                "Active actor not found: " + backend_selection.active_actor.string()
            )
            return data

        if not isinstance(actor, AssetActor):
            logger.error("Active actor is not an AssetActor while active entity is set")
            return data

        entity_path = actor.entity_root.find_entity_path_by_id(
            backend_selection.active_entity
        )
        if entity_path is None:
            logger.error(
                "Failed to find entity path by id: "
                + str(backend_selection.active_entity)
            )
            return data

        data.active_entity_path = entity_path
        return data

    async def set_recursive_display(self, enable: bool):
        await self.custom_command(
            f"set_recursive_display:{'true' if enable else 'false'}"
        )
