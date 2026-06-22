import grpc
import logging
import numpy as np
from typing import Any, List, Tuple

from orcalab.camera_data_png_result import CameraDataPNGResult
from orcalab.entity_path import EntityPath, NameWithIndex
from orcalab.selection_data import BackendSelectionData, SelectionData
from orcalab.property_post_process import (
    PostProcessRegistry,
    PostProcessRule,
    ReadPropertiesAction,
)

logger = logging.getLogger(__name__)

from orcalab.entity_info import EntityInfo

import orcalab.protos.edit_service_pb2_grpc as edit_service_pb2_grpc
import orcalab.protos.edit_service_pb2 as edit_service_pb2

from orcalab.transform import Transform
from orcalab.path import Path
from orcalab.actor import GroupActor, AssetActor
from orcalab.actor_property import (
    ActorEntities,
    ActorProperty,
    ActorPropertyGroup,
    ActorPropertyKey,
    ActorPropertyType,
    PropertyGetInfo,
    PropertyOverride,
)
from orcalab.perf_log import perf_logger, perf_timer, perf_log
from orcalab.scene_edit_types import AddActorRequest
from orcalab.ui.camera.camera_brief import CameraBrief

logger = logging.getLogger(__name__)

Success = edit_service_pb2.StatusCode.Success
Error = edit_service_pb2.StatusCode.Error

LOG_GRPC_TRAFFIC = False


class EditServiceWrapper:
    def __init__(self):
        pass

    def init_grpc(self, addreass: str):
        options = [
            ("grpc.max_receive_message_length", 1024 * 1024 * 1024),
            ("grpc.max_send_message_length", 1024 * 1024 * 1024),
        ]
        self.channel = grpc.aio.insecure_channel(
            addreass,
            options=options,
        )
        self.stub = edit_service_pb2_grpc.GrpcServiceStub(self.channel)

    async def destroy_grpc(self):
        if self.channel:
            await self.channel.close()

    def _create_transform_message(self, transform: Transform):
        msg = edit_service_pb2.Transform(
            pos=transform.position,
            quat=transform.rotation,
            scale=transform.scale,
        )
        return msg

    def _get_transform_from_message(self, msg) -> Transform:
        transform = Transform()
        transform.position = np.array(msg.pos, dtype=np.float64)
        quat = np.array(msg.quat, dtype=np.float64)
        quat = quat / np.linalg.norm(quat)
        transform.rotation = quat
        transform.scale = msg.scale
        return transform

    def _check_response(self, response):
        if response.status_code != Success:
            logger.error(f"[_check_response] gRPC error: {response.error_message}")
            raise Exception(f"Request failed. {response.error_message}")

    def _check_response_no_exception(self, response) -> str:
        if response.status_code != Success:
            logger.error(f"[Error] {response.error_message}")
            return response.error_message
        return ""

    async def aloha(self) -> bool:
        try:
            request = edit_service_pb2.AlohaRequest(value=1)
            response = await self.stub.Aloha(request)
            self._check_response(response)
            if response.value != 2:
                raise Exception("Invalid response value.")
            return True
        except Exception as e:
            return False

    async def add_actor_batch(
        self, in_requests: List[AddActorRequest], stop_on_error
    ) -> Tuple[bool, List[str]]:
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] add_actor_batch() called with {len(in_requests)} requests, stop_on_error={stop_on_error}"
            )

        requests = []
        for in_request in in_requests:
            actor = in_request.actor
            parent_path = in_request.parent_path

            request_union = edit_service_pb2.AddActorRequestUnion()
            if isinstance(actor, GroupActor):
                transform_msg = self._create_transform_message(actor.transform)
                request = edit_service_pb2.AddGroupRequest(
                    actor_name=actor.name,
                    parent_actor_path=parent_path.string(),
                    transform=transform_msg,
                    space=edit_service_pb2.Space.Local,
                )
                request_union.group_actor.CopyFrom(request)
            elif isinstance(actor, AssetActor):
                transform_msg = self._create_transform_message(actor.transform)
                request = edit_service_pb2.AddAssetActorRequest(
                    actor_name=actor.name,
                    spawnable_name=actor.asset_path,
                    parent_actor_path=parent_path.string(),
                    transform=transform_msg,
                    space=edit_service_pb2.Space.Local,
                )
                request_union.asset_actor.CopyFrom(request)
            else:
                raise ValueError("Unsupported actor type.")
            requests.append(request_union)

        batch_request = edit_service_pb2.AddActorBatchRequest(
            requests=requests, stop_on_error=stop_on_error
        )
        response = await self.stub.AddActorBatch(batch_request)
        if response.status_code != Success:
            logger.error(f"Errors occur during add_actor_batch()")
            for req, error in zip(in_requests, response.errors):
                if error:
                    logger.error(
                        f"    Error adding {req.actor.name} under {req.parent_path}: {error}"
                    )
            return False, list(response.errors)
        return True, list(response.errors)

    async def delete_actor_batch(
        self, actor_paths: List[Path]
    ) -> Tuple[bool, List[str]]:
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] delete_actor_batch() called with {len(actor_paths)} actor paths"
            )

        paths = []
        for p in actor_paths:
            if not isinstance(p, Path):
                raise Exception(f"Invalid path: {p}")
            paths.append(p.string())

        batch_request = edit_service_pb2.DeleteActorBatchRequest(actor_paths=paths)
        response = await self.stub.DeleteActorBatch(batch_request)

        if response.status_code != Success:
            logger.error(f"Errors occur during delete_actor_batch()")
            for path, error in zip(actor_paths, response.errors):
                if error:
                    logger.error(f"    Error deleting {path}: {error}")
            return False, list(response.errors)
        return True, list(response.errors)

    async def query_pending_operation_loop(self) -> List[str]:
        request = edit_service_pb2.GetPendingOperationsRequest()
        response = await self.stub.GetPendingOperations(request)
        self._check_response(response)
        return list(response.operations)

    async def get_pending_actor_transform_batch(
        self, paths: List[Path]
    ) -> List[Transform]:
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] get_pending_actor_transform_batch() called with {len(paths)} actor paths"
            )

        request = edit_service_pb2.GetPendingActorTransformBatchRequest(
            actor_paths=[p.string() for p in paths]
        )
        response = await self.stub.GetPendingActorTransformBatch(request)
        self._check_response(response)
        transforms = []
        for transform_msg in response.transforms:
            transform = self._get_transform_from_message(transform_msg)
            transforms.append(transform)
        assert len(transforms) == len(
            paths
        ), "Response transforms length does not match request paths length."
        return transforms

    async def set_actor_transform_batch(
        self, paths: List[Path], transforms: List[Transform]
    ):
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] set_actor_transform_batch() called with {len(paths)} actor paths and {len(transforms)} transforms"
            )

        if len(paths) != len(transforms):
            raise ValueError("Paths and transforms must have the same length.")
        request = edit_service_pb2.SetActorTransformBatchRequest()
        for path, transform in zip(paths, transforms):
            transform_msg = self._create_transform_message(transform)
            request.actor_paths.append(path.string())
            request.transforms.append(transform_msg)

        response = await self.stub.SetActorTransformBatch(request)
        self._check_response(response)

    async def publish_scene(self):
        if LOG_GRPC_TRAFFIC:
            logger.info("[GRPC TRAFFIC] publish_scene() called")
        request = edit_service_pb2.PublishSceneRequest()
        response = await self.stub.PublishScene(request)
        self._check_response(response)

    async def get_sync_from_mujoco_to_scene(self) -> bool:
        if LOG_GRPC_TRAFFIC:
            logger.info("[GRPC TRAFFIC] get_sync_from_mujoco_to_scene() called")
        request = edit_service_pb2.GetSyncFromMujocoToSceneRequest()
        response = await self.stub.GetSyncFromMujocoToScene(request)
        self._check_response(response)
        return response.value

    async def set_sync_from_mujoco_to_scene(self, value: bool):
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] set_sync_from_mujoco_to_scene() called with value={value}"
            )
        request = edit_service_pb2.SetSyncFromMujocoToSceneRequest(value=value)
        response = await self.stub.SetSyncFromMujocoToScene(request)
        self._check_response(response)

    async def clear_scene(self):
        if LOG_GRPC_TRAFFIC:
            logger.info("[GRPC TRAFFIC] clear_scene() called")
        request = edit_service_pb2.ClearSceneRequest()
        response = await self.stub.ClearScene(request)
        self._check_response(response)

    async def get_pending_add_item(self) -> Tuple[Transform, str]:
        if LOG_GRPC_TRAFFIC:
            logger.info("[GRPC TRAFFIC] get_pending_add_item() called")
        request = edit_service_pb2.GetPendingAddItemRequest()
        response = await self.stub.GetPendingAddItem(request)
        self._check_response(response)
        transform = self._get_transform_from_message(response.transform)
        return (transform, response.actor_name)

    def _to_grpc_selection_data(
        self, selection: BackendSelectionData
    ) -> edit_service_pb2.SelectionData:
        paths = []
        for p in selection.selected_actors:
            if not isinstance(p, Path):
                raise Exception(f"Invalid path: {p}")
            paths.append(p.string())

        if selection.active_actor:
            active_actor_path = selection.active_actor.string()
        else:
            active_actor_path = ""

        return edit_service_pb2.SelectionData(
            selected_actor_paths=paths,
            active_actor_path=active_actor_path,
            active_entity_id=selection.active_entity,
        )

    def _from_grpc_selection_data(
        self, selection_data: edit_service_pb2.SelectionData
    ) -> BackendSelectionData:
        paths = [Path(p) for p in selection_data.selected_actor_paths]
        if selection_data.active_actor_path:
            active_actor = Path(selection_data.active_actor_path)
        else:
            active_actor = None
        return BackendSelectionData(
            selected_actors=paths,
            active_actor=active_actor,
            active_entity=selection_data.active_entity_id,
        )

    async def get_pending_selection_change(self) -> BackendSelectionData:
        if LOG_GRPC_TRAFFIC:
            logger.info("[GRPC TRAFFIC] get_pending_selection_change() called")
        request = edit_service_pb2.GetPendingSelectionChangeRequest()
        response = await self.stub.GetPendingSelectionChange(request)
        self._check_response(response)
        return self._from_grpc_selection_data(response.selection)

    async def set_selection(self, selection: BackendSelectionData):
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] set_selection() called with {len(selection.selected_actors)} selected actors and active actor {selection.active_actor}"
            )
        selection_data = self._to_grpc_selection_data(selection)
        request = edit_service_pb2.SetSelectionRequest(selection=selection_data)
        response = await self.stub.SetSelection(request)
        self._check_response(response)

    async def get_actor_assets(self) -> List[str]:
        if LOG_GRPC_TRAFFIC:
            logger.info("[GRPC TRAFFIC] get_actor_assets() called")
        request = edit_service_pb2.GetActorAssetsRequest()
        response = await self.stub.GetActorAssets(request)
        self._check_response(response)
        return list(response.actor_asset_names)

    async def save_state(self):
        if LOG_GRPC_TRAFFIC:
            logger.info("[GRPC TRAFFIC] save_state() called")
        request = edit_service_pb2.SaveStateRequest()
        response = await self.stub.SaveState(request)
        self._check_response(response)

    async def restore_state(self):
        if LOG_GRPC_TRAFFIC:
            logger.info("[GRPC TRAFFIC] restore_state() called")
        request = edit_service_pb2.RestoreStateRequest()
        response = await self.stub.RestoreState(request)
        self._check_response(response)

    async def rename_actor(self, actor_path: Path, new_name: str):
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] rename_actor() called with actor_path={actor_path} and new_name={new_name}"
            )
        request = edit_service_pb2.RenameActorRequest(
            actor_path=actor_path.string(),
            new_name=new_name,
        )
        response = await self.stub.RenameActor(request)
        self._check_response(response)

    async def move_actor_batch(
        self, actor_paths: List[Path], new_parent_paths: List[Path]
    ):
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] move_actor_batch() called with {len(actor_paths)} actor paths and {len(new_parent_paths)} new parent paths"
            )
        actor_paths_str = [p.string() for p in actor_paths]
        new_parent_paths_str = [p.string() for p in new_parent_paths]
        request = edit_service_pb2.MoveActorBatchRequest(
            actor_paths=actor_paths_str,
            new_parent_paths=new_parent_paths_str,
        )

        response = await self.stub.MoveActorBatch(request)
        self._check_response(response)

    async def get_window_id(self):
        if LOG_GRPC_TRAFFIC:
            logger.info("[GRPC TRAFFIC] get_window_id() called")
        request = edit_service_pb2.GetWindowIdRequest()
        response = await self.stub.GetWindowId(request)
        self._check_response(response)
        return response

    async def get_generate_pos(self, posX, posY) -> Transform:
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] get_generate_pos() called with posX={posX} and posY={posY}"
            )
        request = edit_service_pb2.GetGeneratePosRequest(posX=posX, posY=posY)
        response = await self.stub.GetGeneratePos(request)
        self._check_response(response)
        return self._get_transform_from_message(response.transform)

    async def get_cache_folder(self) -> str:
        if LOG_GRPC_TRAFFIC:
            logger.info("[GRPC TRAFFIC] get_cache_folder() called")
        request = edit_service_pb2.GetCacheFolderRequest()
        response = await self.stub.GetCacheFolder(request)
        self._check_response(response)
        return response.cache_folder

    async def load_package(self, package_path: str) -> None:
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] load_package() called with package_path={package_path}"
            )
        request = edit_service_pb2.LoadPackageRequest(file_path=package_path)
        response = await self.stub.LoadPackage(request)
        self._check_response(response)

    async def change_sim_state(self, sim_process_running: bool):
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] change_sim_state() called with sim_process_running={sim_process_running}"
            )
        request = edit_service_pb2.ChangeSimStateRequest(
            sim_process_running=sim_process_running
        )
        response = await self.stub.ChangeSimState(request)
        self._check_response(response)
        return response

    async def get_camera_png(
        self, camera_name: str, png_path: str, png_name: str
    ) -> bool:
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] get_camera_png() called with camera_name={camera_name}, png_path={png_path}, png_name={png_name}"
            )
        request = edit_service_pb2.GetCameraPNGRequest(
            camera_name=camera_name,
            png_path=png_path,
            png_name=png_name,
        )
        response = await self.stub.GetCameraPNG(request)
        if response.status_code != Success:
            return False
        return True

    async def get_camera_data_png(
        self, camera_name: str, png_path: str, index: int
    ) -> CameraDataPNGResult:
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] get_camera_data_png() called with camera_name={camera_name}, png_path={png_path}, index={index}"
            )
        request = edit_service_pb2.GetCameraDataPNGRequest(
            camera_name=camera_name,
            png_path=png_path,
            index=index,
        )
        response = await self.stub.GetCameraDataPNG(request)
        self._check_response(response)
        result = CameraDataPNGResult(
            transform=self._get_transform_from_message(response.transform),
            has_color=response.has_color,
            has_depth=response.has_depth,
            has_normal=response.has_normal,
            has_object_color=response.has_object_color,
        )
        return result

    async def get_actor_asset_aabb(self, actor_path: Path, output: List[float]):
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] get_actor_asset_aabb() called with actor_path={actor_path}"
            )
        request = edit_service_pb2.GetActorAssetAabbRequest(
            actor_path=actor_path.string()
        )
        response = await self.stub.GetActorAssetAabb(request)
        self._check_response(response)
        if output is not None:
            output.extend(response.min)
            output.extend(response.max)
        return response

    async def find_non_overlapping_position(
        self, actor_path: Path, output: List[float]
    ):
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] find_non_overlapping_position() called with actor_path={actor_path}"
            )
        request = edit_service_pb2.FindNonOverlappingPositionRequest(
            actor_path=actor_path.string()
        )
        response = await self.stub.FindNonOverlappingPosition(request)
        self._check_response(response)
        if output is not None:
            output.extend(response.position)
        return response

    async def queue_mouse_event(self, x: float, y: float, button: int, action: int):
        request = edit_service_pb2.QueueMouseEventRequest(
            x=x, y=y, button=button, action=action
        )

        response = await self.stub.QueueMouseEvent(request)
        self._check_response(response)

    async def queue_mouse_wheel_event(self, delta: int):
        request = edit_service_pb2.QueueMouseWheelEventRequest(delta=delta)
        response = await self.stub.QueueMouseWheelEvent(request)
        self._check_response(response)

    async def queue_key_event(self, key: int, action: int):
        request = edit_service_pb2.QueueKeyEventRequest(key=key, action=action)
        response = await self.stub.QueueKeyEvent(request)
        self._check_response(response)

    async def get_cameras(self) -> List[CameraBrief]:
        if LOG_GRPC_TRAFFIC:
            logger.info("[GRPC TRAFFIC] get_cameras() called")
        request = edit_service_pb2.GetCamerasRequest()
        response = await self.stub.GetCameras(request)
        self._check_response(response)

        l = []
        for cam in response.cameras:
            camera_brief = CameraBrief(index=cam.index, name=cam.name)
            camera_brief.source = getattr(cam, "source", "") or ""
            camera_brief.actor_path = getattr(cam, "actor_path", "") or ""
            l.append(camera_brief)
        return l

    async def get_active_camera(self) -> int:
        if LOG_GRPC_TRAFFIC:
            logger.info("[GRPC TRAFFIC] get_active_camera() called")
        request = edit_service_pb2.GetActiveCameraRequest()
        response = await self.stub.GetActiveCamera(request)

        if response.status_code != Success:
            return -1

        return response.index

    async def set_active_camera(self, camera_index: int) -> None:
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] set_active_camera() called with camera_index={camera_index}"
            )
        request = edit_service_pb2.SetActiveCameraRequest(index=camera_index)
        response = await self.stub.SetActiveCamera(request)
        self._check_response(response)

    async def get_flycamera_transform(self) -> Transform:
        if LOG_GRPC_TRAFFIC:
            logger.info("[GRPC TRAFFIC] get_flycamera_transform() called")
        request = edit_service_pb2.GetFlyCameraTransformRequest()
        response = await self.stub.GetFlyCameraTransform(request)
        self._check_response(response)
        transform = response.flycamera_transform
        return self._get_transform_from_message(transform)

    async def set_flycamera_transform(self, flycamera_transform: Transform) -> None:
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] set_flycamera_transform() called with flycamera_transform={flycamera_transform}"
            )
        request = edit_service_pb2.SetFlyCameraTransformRequest(
            flycamera_transform=self._create_transform_message(flycamera_transform)
        )
        response = await self.stub.SetFlyCameraTransform(request)
        self._check_response(response)

    async def get_viewport_camera_transform(self) -> Transform:
        if LOG_GRPC_TRAFFIC:
            logger.info("[GRPC TRAFFIC] get_viewport_camera_transform() called")
        request = edit_service_pb2.GetViewportCameraTransformRequest()
        response = await self.stub.GetViewportCameraTransform(request)
        self._check_response(response)
        return self._get_transform_from_message(response.transform)

    def _read_property_msg(
        self, prop_msg: edit_service_pb2.Property
    ) -> ActorProperty | None:
        property_type = self._read_property_type(prop_msg.type)
        value = self._read_property_value(prop_msg.value, property_type)
        base_value = self._read_property_value(prop_msg.base_value, property_type)
        if value is None or base_value is None:
            return None

        prop = ActorProperty(
            name=prop_msg.name,
            display_name=prop_msg.display_name,
            type=property_type,
            value=value,
            original_value=base_value,
        )

        prop.set_read_only(prop_msg.metadata.read_only)
        prop.set_editor_hint(prop_msg.editor_hint)
        if prop_msg.enum_values:
            prop.set_enum_values(list(prop_msg.enum_values))
        if prop_msg.post_read_fields:
            prop.set_post_read_fields(list(prop_msg.post_read_fields))
            if prop_msg.post_read_delay_ms:
                prop.set_post_read_delay_ms(prop_msg.post_read_delay_ms)
        return prop

    def _register_post_process_rule(self, prop, component_type_id: str):
        registry = PostProcessRegistry.instance()
        registry.register(
            PostProcessRule(
                trigger_property=prop.name(),
                component_type=component_type_id,
                action=ReadPropertiesAction(prop.post_read_fields()),
                delay_ms=prop.post_read_delay_ms() or 100,
            )
        )

    @staticmethod
    def _strip_component_suffix(name: str) -> str:
        suffix = "Component"
        if len(name) > len(suffix) and name.endswith(suffix):
            return name[: -len(suffix)]
        return name

    def _read_property_type(
        self, type_msg: edit_service_pb2.PropertyType
    ) -> ActorPropertyType:
        match type_msg:
            case edit_service_pb2.PropertyType.Bool:
                return ActorPropertyType.BOOL
            case edit_service_pb2.PropertyType.Int:
                return ActorPropertyType.INTEGER
            case edit_service_pb2.PropertyType.Float:
                return ActorPropertyType.FLOAT
            case edit_service_pb2.PropertyType.String:
                return ActorPropertyType.STRING
            case edit_service_pb2.PropertyType.ENUM:
                return ActorPropertyType.ENUM
            case edit_service_pb2.PropertyType.ASSET:
                return ActorPropertyType.ASSET
            case _:
                raise ValueError("Unsupported property type.")

    def _write_property_type(
        self, property_type: ActorPropertyType
    ) -> edit_service_pb2.PropertyType:
        match property_type:
            case ActorPropertyType.BOOL:
                return edit_service_pb2.PropertyType.Bool
            case ActorPropertyType.INTEGER:
                return edit_service_pb2.PropertyType.Int
            case ActorPropertyType.FLOAT:
                return edit_service_pb2.PropertyType.Float
            case ActorPropertyType.STRING:
                return edit_service_pb2.PropertyType.String
            case ActorPropertyType.ENUM:
                return edit_service_pb2.PropertyType.ENUM
            case ActorPropertyType.ASSET:
                return edit_service_pb2.PropertyType.ASSET
            case _:
                raise ValueError("Unsupported property type.")

    def _read_property_group(
        self, pg_msg: edit_service_pb2.PropertyGroup
    ) -> ActorPropertyGroup:
        name = self._strip_component_suffix(pg_msg.name)
        pg = ActorPropertyGroup(
            name=name,
            hint=pg_msg.hint,
            entity_id=pg_msg.entity_id,
            entity_path=EntityPath(),  # provide by frontend
            component_type_id=pg_msg.component_type_id,
            component_type_index=pg_msg.component_type_index,
            properties=[],
        )

        for prop_msg in pg_msg.properties:
            prop = self._read_property_msg(prop_msg)
            if prop:
                pg.properties.append(prop)
                if prop.post_read_fields() and pg_msg.component_type_id:
                    self._register_post_process_rule(prop, pg_msg.component_type_id)

        return pg

    def _create_property_key_message(self, key: ActorPropertyKey):
        key_msg = edit_service_pb2.PropertyKey()
        key_msg.actor_path = key.actor_path.string()
        key_msg.entity_id = key.entity_id
        key_msg.component_type_id = key.component_type_id
        key_msg.component_type_index = key.component_type_index
        key_msg.field_path = key.property_name
        key_msg.property_type = self._write_property_type(key.property_type)
        return key_msg

    def _write_property_value_message(self, key: ActorPropertyKey, value: Any):
        value_msg = edit_service_pb2.PropertyValue()

        match key.property_type:
            case ActorPropertyType.BOOL:
                if not isinstance(value, bool):
                    raise ValueError("Value must be a boolean.")
                value_msg.value_bool = value
            case ActorPropertyType.INTEGER:
                if not isinstance(value, int):
                    raise ValueError("Value must be an integer.")
                value_msg.value_int = value
            case ActorPropertyType.FLOAT:
                if not isinstance(value, float):
                    raise ValueError("Value must be a float.")
                value_msg.value_float = value
            case ActorPropertyType.STRING:
                if not isinstance(value, str):
                    raise ValueError("Value must be a string.")
                value_msg.value_string = value
            case ActorPropertyType.ENUM:
                if not isinstance(value, str):
                    raise ValueError("Value must be a string for enum.")
                value_msg.value_string = value
            case ActorPropertyType.ASSET:
                if not isinstance(value, str):
                    raise ValueError("Value must be a string for asset.")
                value_msg.value_asset = value
            case _:
                raise ValueError("Unsupported property type.")

        return value_msg

    def _read_property_value(
        self,
        value_msg: edit_service_pb2.PropertyValue,
        property_type: ActorPropertyType,
    ) -> Any:
        t = value_msg.WhichOneof("value_oneof")

        match property_type:
            case ActorPropertyType.BOOL:
                if t == "value_bool":
                    return value_msg.value_bool
            case ActorPropertyType.INTEGER:
                if t == "value_int":
                    return value_msg.value_int
            case ActorPropertyType.FLOAT:
                if t == "value_float":
                    return value_msg.value_float
            case ActorPropertyType.STRING:
                if t == "value_string":
                    return value_msg.value_string
            case ActorPropertyType.ENUM:
                if t == "value_string":
                    return value_msg.value_string
            case ActorPropertyType.ASSET:
                if t == "value_asset":
                    return value_msg.value_asset

        logger.error(
            "[Coding Error] Property value does not match the expected property type."
        )
        return None

    def _read_property_get_info_message(
        self,
        info_msg: edit_service_pb2.PropertyGetInfo,
        property_type: ActorPropertyType,
    ) -> PropertyGetInfo:
        value = self._read_property_value(info_msg.value, property_type)
        base_value = self._read_property_value(info_msg.base_value, property_type)
        return PropertyGetInfo(
            read_only=info_msg.metadata.read_only,
            value=value,
            base_value=base_value,
        )

    async def get_properties(
        self, keys: List[ActorPropertyKey]
    ) -> List[PropertyGetInfo]:
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] get_properties() called with {len(keys)} property keys"
            )
        request = edit_service_pb2.GetPropertiesRequest()
        for key in keys:
            key_msg = self._create_property_key_message(key)
            request.keys.append(key_msg)

        response = await self.stub.GetProperties(request)
        self._check_response(response)

        infos: List[PropertyGetInfo] = []
        for key, info_msg in zip(keys, response.infos):
            info = self._read_property_get_info_message(info_msg, key.property_type)
            infos.append(info)
        return infos

    async def set_properties(self, keys: List[ActorPropertyKey], values: List[Any]):
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] set_properties() called with {len(keys)} property keys and {len(values)} values"
            )

        if len(keys) != len(values):
            raise ValueError("Keys and values must have the same length.")

        request = edit_service_pb2.SetPropertiesRequest()
        for key, value in zip(keys, values):
            key_msg = self._create_property_key_message(key)
            request.keys.append(key_msg)
            value_msg = self._write_property_value_message(key, value)
            request.infos.append(edit_service_pb2.PropertySetInfo(value=value_msg))

        response = await self.stub.SetProperties(request)
        self._check_response(response)

    async def custom_command(self, command: str):
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] custom_command() called with command={command}"
            )
        request = edit_service_pb2.CustomCommandRequest(command=command)
        response = await self.stub.CustomCommand(request)
        self._check_response(response)

    async def set_visibility(self, visible: bool, actor_paths: List[Path]):
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] set_visibility() called with visible={visible} and {len(actor_paths)} actor paths"
            )
        paths = []
        for p in actor_paths:
            if not isinstance(p, Path):
                raise Exception(f"Invalid path: {p}")
            paths.append(p.string())

        request = edit_service_pb2.SetVisibilityRequest(
            visible=visible, actor_paths=paths
        )
        response = await self.stub.SetVisibility(request)
        self._check_response(response)

    async def set_lock(self, locked: bool, actor_paths: List[Path]):
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] set_lock() called with locked={locked} and {len(actor_paths)} actor paths"
            )
        paths = []
        for p in actor_paths:
            if not isinstance(p, Path):
                raise Exception(f"Invalid path: {p}")
            paths.append(p.string())

        request = edit_service_pb2.SetLockRequest(locked=locked, actor_paths=paths)
        response = await self.stub.SetLock(request)
        self._check_response(response)

    async def set_move_rotate_sensitivity(
        self, move_sensitivity: float, rotate_sensitivity: float
    ):
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] set_move_rotate_sensitivity() called with move_sensitivity={move_sensitivity} and rotate_sensitivity={rotate_sensitivity}"
            )
        request = edit_service_pb2.SetMoveRotateSensitivityRequest(
            move_sensitivity=move_sensitivity, rotate_sensitivity=rotate_sensitivity
        )
        response = await self.stub.SetMoveRotateSensitivity(request)
        self._check_response(response)

    def _parse_entity_info(
        self,
        msg: edit_service_pb2.EntityInfoMessage,
        parent: EntityInfo | None,
        segments: List[NameWithIndex],
        position: int,
    ) -> EntityInfo:

        entity_info = EntityInfo(entity_id=msg.entity_id, name=msg.name, parent=parent)

        name = msg.name
        if parent is None:
            # 根节点，使用特殊名称，消除Actor名称的影响。
            name = "<root>"

        segment = NameWithIndex(name=name, index=position)
        segments.append(segment)

        children = []
        for i, child in enumerate(msg.children):
            result = self._parse_entity_info(child, entity_info, segments, i)
            children.append(result)

        entity_info.children = children
        entity_info.entity_path = EntityPath(segments.copy())

        segments.pop()

        return entity_info

    async def get_entity_hierarchy_batch(
        self, actor_paths: List[Path]
    ) -> List[EntityInfo | None]:
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] get_entity_hierarchy_batch() called with {len(actor_paths)} actor paths"
            )
        request = edit_service_pb2.GetEntityHierarchyBatchRequest(
            actor_paths=[p.string() for p in actor_paths]
        )
        response: edit_service_pb2.GetEntityHierarchyBatchResponse = (
            await self.stub.GetEntityHierarchyBatch(request)
        )
        self._check_response(response)

        results: List[EntityInfo | None] = []
        for root_entity, error in zip(response.root_entities, response.errors):
            if root_entity is not None and len(error) == 0:
                results.append(self._parse_entity_info(root_entity, None, [], 0))
            else:
                # For now, error is discarded.
                results.append(None)
        return results

    def _write_actor_entities_list_message(
        self, actor_entities_list: List[ActorEntities]
    ) -> List[edit_service_pb2.ActorEntities]:

        messages = []
        for actor_entities in actor_entities_list:
            msg = edit_service_pb2.ActorEntities()
            msg.actor_path = actor_entities.actor_path.string()
            msg.entity_ids.extend(actor_entities.entity_ids)
            messages.append(msg)

        return messages

    async def get_entity_property_groups_batch(
        self, actor_entities_list: List[ActorEntities]
    ) -> List[List[List[ActorPropertyGroup]]]:
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] get_entity_property_groups_batch() called with {len(actor_entities_list)} actor entities"
            )

        if not actor_entities_list:
            return []

        request = edit_service_pb2.GetEntityPropertyGroupsBatchRequest(
            actor_entities_list=self._write_actor_entities_list_message(
                actor_entities_list
            )
        )

        response = await self.stub.GetEntityPropertyGroupsBatch(request)
        self._check_response(response)

        result: List[List[List[ActorPropertyGroup]]] = []
        for property_groups_list_msg in response.property_groups_list_array.elements:
            property_groups_list: List[List[ActorPropertyGroup]] = []
            for property_groups_msg in property_groups_list_msg.elements:
                property_groups: List[ActorPropertyGroup] = []
                for pg_msg in property_groups_msg.elements:
                    pg = self._read_property_group(pg_msg)
                    property_groups.append(pg)
                property_groups_list.append(property_groups)
            result.append(property_groups_list)
        return result

    async def get_actor_property_groups_batch(
        self, actor_paths: List[Path]
    ) -> List[List[ActorPropertyGroup]]:
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] get_actor_property_groups_batch() called with {len(actor_paths)} actor paths"
            )

        if not actor_paths:
            return []

        actor_paths_str = [p.string() for p in actor_paths]
        request = edit_service_pb2.GetActorPropertyGroupsBatchRequest(
            actor_paths=actor_paths_str
        )
        response = await self.stub.GetActorPropertyGroupsBatch(request)
        self._check_response(response)

        result: List[List[ActorPropertyGroup]] = []
        for property_groups_msg in response.property_groups_list.elements:
            property_groups: List[ActorPropertyGroup] = []
            for pg_msg in property_groups_msg.elements:
                pg = self._read_property_group(pg_msg)
                property_groups.append(pg)
            result.append(property_groups)

        return result

    def _read_property_message(
        self, prop_msg: edit_service_pb2.PropertyOverride
    ) -> PropertyOverride:
        property_type = self._read_property_type(prop_msg.property_type)
        value = self._read_property_value(prop_msg.value, property_type)
        return PropertyOverride(
            entity_id=prop_msg.entity_id,
            entity_path=EntityPath(),  # provide by frontend
            component_type_id=prop_msg.component_type_id,
            component_type_index=prop_msg.component_type_index,
            property_name=prop_msg.field_path,
            property_type=property_type,
            value=value,
        )

    def _write_actors_list_message(
        self, actor_paths_list: List[List[Path]]
    ) -> edit_service_pb2.ActorPathsList:
        msg = edit_service_pb2.ActorPathsList()
        for actor_paths in actor_paths_list:
            actor_paths_msg = msg.elements.add()
            actor_paths_msg.elements.extend([p.string() for p in actor_paths])
        return msg

    async def get_actor_overrides_batch(
        self, actor_paths_list: List[List[Path]]
    ) -> List[List[List[PropertyOverride]]]:
        count = 0
        for actor_paths in actor_paths_list:
            count += len(actor_paths)

        if LOG_GRPC_TRAFFIC:

            logger.info(
                f"[GRPC TRAFFIC] get_actor_overrides_batch() called with {count} actor paths"
            )

        if count == 0:
            if not actor_paths_list:
                return []
            return [[] for _ in actor_paths_list]

        request = edit_service_pb2.GetActorOverridesBatchRequest(
            actor_paths_list=self._write_actors_list_message(actor_paths_list)
        )
        response = await self.stub.GetActorOverridesBatch(request)
        self._check_response(response)

        lll: List[List[List[PropertyOverride]]] = []
        for overrides_list_msg in response.overrides_list_array.elements:
            ll: List[List[PropertyOverride]] = []
            for overrides_msg in overrides_list_msg.elements:
                l: List[PropertyOverride] = []
                for override_msg in overrides_msg.elements:
                    override = self._read_property_message(override_msg)
                    l.append(override)
                ll.append(l)
            lll.append(ll)

        return lll

    async def get_assets_by_type_page(
        self, asset_type_uuid: str, page_index: int, page_size: int
    ):
        if LOG_GRPC_TRAFFIC:
            logger.info(
                f"[GRPC TRAFFIC] get_assets_by_type_page() called with asset_type_uuid={asset_type_uuid}, page_index={page_index}, page_size={page_size}"
            )
        request = edit_service_pb2.GetAssetsByTypePageRequest(
            asset_type_uuid=asset_type_uuid,
            page_index=page_index,
            page_size=page_size,
        )
        response = await self.stub.GetAssetsByTypePage(request)
        self._check_response(response)
        return response
