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

from orcalab.math import Transform
from orcalab.path import Path
from orcalab.actor import GroupActor, AssetActor
from orcalab.actor_property import (
    ActorProperty,
    ActorPropertyGroup,
    ActorPropertyKey,
    ActorPropertyType,
    EntityPropertyGroupEntry,
)
from orcalab.perf_log import perf_timer, perf_log
from orcalab.scene_edit_types import AddActorRequest
from orcalab.ui.camera.camera_brief import CameraBrief

logger = logging.getLogger(__name__)

Success = edit_service_pb2.StatusCode.Success
Error = edit_service_pb2.StatusCode.Error


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
            return False, response.errors
        return True, response.errors

    async def delete_actor_batch(
        self, actor_paths: List[Path]
    ) -> Tuple[bool, List[str]]:
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
            return False, response.errors
        return True, response.errors

    async def query_pending_operation_loop(self) -> List[str]:
        request = edit_service_pb2.GetPendingOperationsRequest()
        response = await self.stub.GetPendingOperations(request)
        self._check_response(response)
        return response.operations

    async def get_pending_actor_transform_batch(
        self, paths: List[Path]
    ) -> List[Transform]:
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
        request = edit_service_pb2.PublishSceneRequest()
        response = await self.stub.PublishScene(request)
        self._check_response(response)

    async def get_sync_from_mujoco_to_scene(self) -> bool:
        request = edit_service_pb2.GetSyncFromMujocoToSceneRequest()
        response = await self.stub.GetSyncFromMujocoToScene(request)
        self._check_response(response)
        return response.value

    async def set_sync_from_mujoco_to_scene(self, value: bool):
        request = edit_service_pb2.SetSyncFromMujocoToSceneRequest(value=value)
        response = await self.stub.SetSyncFromMujocoToScene(request)
        self._check_response(response)

    async def clear_scene(self):
        request = edit_service_pb2.ClearSceneRequest()
        response = await self.stub.ClearScene(request)
        self._check_response(response)

    async def get_pending_add_item(self) -> Tuple[Transform, str]:
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
        request = edit_service_pb2.GetPendingSelectionChangeRequest()
        response = await self.stub.GetPendingSelectionChange(request)
        self._check_response(response)
        return self._from_grpc_selection_data(response.selection)

    async def set_selection(self, selection: BackendSelectionData):
        selection_data = self._to_grpc_selection_data(selection)
        request = edit_service_pb2.SetSelectionRequest(selection=selection_data)
        response = await self.stub.SetSelection(request)
        self._check_response(response)

    async def get_actor_assets(self) -> List[str]:
        request = edit_service_pb2.GetActorAssetsRequest()
        response = await self.stub.GetActorAssets(request)
        self._check_response(response)
        return response.actor_asset_names

    async def save_state(self):
        request = edit_service_pb2.SaveStateRequest()
        response = await self.stub.SaveState(request)
        self._check_response(response)

    async def restore_state(self):
        request = edit_service_pb2.RestoreStateRequest()
        response = await self.stub.RestoreState(request)
        self._check_response(response)

    async def rename_actor(self, actor_path: Path, new_name: str):
        request = edit_service_pb2.RenameActorRequest(
            actor_path=actor_path.string(),
            new_name=new_name,
        )
        response = await self.stub.RenameActor(request)
        self._check_response(response)

    async def move_actor_batch(
        self, actor_paths: List[Path], new_parent_paths: List[Path]
    ):
        actor_paths_str = [p.string() for p in actor_paths]
        new_parent_paths_str = [p.string() for p in new_parent_paths]
        request = edit_service_pb2.MoveActorBatchRequest(
            actor_paths=actor_paths_str,
            new_parent_paths=new_parent_paths_str,
        )

        response = await self.stub.MoveActorBatch(request)
        self._check_response(response)

    async def get_window_id(self):

        request = edit_service_pb2.GetWindowIdRequest()
        response = await self.stub.GetWindowId(request)
        self._check_response(response)
        return response

    async def get_generate_pos(self, posX, posY) -> Transform:
        request = edit_service_pb2.GetGeneratePosRequest(posX=posX, posY=posY)
        response = await self.stub.GetGeneratePos(request)
        self._check_response(response)
        return self._get_transform_from_message(response.transform)

    async def get_cache_folder(self) -> str:
        request = edit_service_pb2.GetCacheFolderRequest()
        response = await self.stub.GetCacheFolder(request)
        self._check_response(response)
        return response.cache_folder

    async def load_package(self, package_path: str) -> None:
        request = edit_service_pb2.LoadPackageRequest(file_path=package_path)
        response = await self.stub.LoadPackage(request)
        self._check_response(response)

    async def change_sim_state(self, sim_process_running: bool):
        request = edit_service_pb2.ChangeSimStateRequest(
            sim_process_running=sim_process_running
        )
        response = await self.stub.ChangeSimState(request)
        self._check_response(response)
        return response

    async def change_manipulator_type(self, manipulator_type: int):
        request = edit_service_pb2.ChangeManipulatorTypeRequest(
            manipulator_type=manipulator_type
        )
        response = await self.stub.ChangeManipulatorType(request)
        self._check_response(response)
        return response

    async def get_camera_png(
        self, camera_name: str, png_path: str, png_name: str
    ) -> bool:
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
        request = edit_service_pb2.GetActiveCameraRequest()
        response = await self.stub.GetActiveCamera(request)

        if response.status_code != Success:
            return -1

        return response.index

    async def set_active_camera(self, camera_index: int) -> None:
        request = edit_service_pb2.SetActiveCameraRequest(index=camera_index)
        response = await self.stub.SetActiveCamera(request)
        self._check_response(response)

    async def get_flycamera_transform(self) -> Transform:
        request = edit_service_pb2.GetFlyCameraTransformRequest()
        response = await self.stub.GetFlyCameraTransform(request)
        self._check_response(response)
        transform = response.flycamera_transform
        return self._get_transform_from_message(transform)

    async def set_flycamera_transform(self, flycamera_transform: Transform) -> None:
        request = edit_service_pb2.SetFlyCameraTransformRequest(
            flycamera_transform=self._create_transform_message(flycamera_transform)
        )
        response = await self.stub.SetFlyCameraTransform(request)
        self._check_response(response)

    async def get_viewport_camera_transform(self) -> Transform:
        request = edit_service_pb2.GetViewportCameraTransformRequest()
        response = await self.stub.GetViewportCameraTransform(request)
        self._check_response(response)
        return self._get_transform_from_message(response.transform)

    def _parse_property_msg(
        self, prop_msg: edit_service_pb2.Property
    ) -> ActorProperty | None:
        """解析属性消息"""
        prop: ActorProperty | None = None
        match prop_msg.type:
            case edit_service_pb2.PropertyType.Unknown:
                return None
            case edit_service_pb2.PropertyType.Bool:
                prop = ActorProperty(
                    name=prop_msg.name,
                    display_name=prop_msg.display_name,
                    type=ActorPropertyType.BOOL,
                    value=False,
                )
            case edit_service_pb2.PropertyType.Int:
                prop = ActorProperty(
                    name=prop_msg.name,
                    display_name=prop_msg.display_name,
                    type=ActorPropertyType.INTEGER,
                    value=0,
                )
            case edit_service_pb2.PropertyType.Float:
                prop = ActorProperty(
                    name=prop_msg.name,
                    display_name=prop_msg.display_name,
                    type=ActorPropertyType.FLOAT,
                    value=0.0,
                )
            case edit_service_pb2.PropertyType.String:
                value = ""
                if prop_msg.editor_hint in ("struct", "container"):
                    value = prop_msg.editor_hint
                prop = ActorProperty(
                    name=prop_msg.name,
                    display_name=prop_msg.display_name,
                    type=ActorPropertyType.STRING,
                    value=value,
                )
            case edit_service_pb2.PropertyType.ENUM:
                prop = ActorProperty(
                    name=prop_msg.name,
                    display_name=prop_msg.display_name,
                    type=ActorPropertyType.ENUM,
                    value="",
                )
            case edit_service_pb2.PropertyType.ASSET:
                prop = ActorProperty(
                    name=prop_msg.name,
                    display_name=prop_msg.display_name,
                    type=ActorPropertyType.ASSET,
                    value="",
                )
        if prop:
            prop.set_read_only(prop_msg.read_only)
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

    def _parse_property_group_msg(
        self, pg_msg: edit_service_pb2.PropertyGroup
    ) -> ActorPropertyGroup:
        name = self._strip_component_suffix(pg_msg.name)
        pg = ActorPropertyGroup(prefix=pg_msg.prefix, name=name, hint=pg_msg.hint)

        if pg_msg.entity_id:
            pg.entity_id = pg_msg.entity_id
        if pg_msg.component_type_id:
            pg.component_type_id = pg_msg.component_type_id

        if pg_msg.display_name:
            pg.display_name = pg_msg.display_name

        for prop_msg in pg_msg.properties:
            prop = self._parse_property_msg(prop_msg)
            if prop:
                pg.properties.append(prop)
                if prop.post_read_fields() and pg_msg.component_type_id:
                    self._register_post_process_rule(prop, pg_msg.component_type_id)

        perf_log(
            f"grpc_wrapper._parse_property_group_msg: name={name}, "
            f"entity_id={pg.entity_id}, prefix={pg_msg.prefix}, "
            f"hint={pg_msg.hint}, props={len(pg.properties)}, "
            f"prop_names=[{', '.join(p.name() for p in pg.properties[:5])}{'...' if len(pg.properties) > 5 else ''}]",
            feature="PROPERTY",
        )

        return pg

    def _create_property_key_message(self, key: ActorPropertyKey):
        key_msg = edit_service_pb2.PropertyKey()
        key_msg.actor_path = key.actor_path.string()
        key_msg.entity_id = key.entity_id
        key_msg.component_type = key.component_type
        key_msg.field_path = key.property_name

        match key.property_type:
            case ActorPropertyType.BOOL:
                key_msg.property_type = edit_service_pb2.PropertyType.Bool
            case ActorPropertyType.INTEGER:
                key_msg.property_type = edit_service_pb2.PropertyType.Int
            case ActorPropertyType.FLOAT:
                key_msg.property_type = edit_service_pb2.PropertyType.Float
            case ActorPropertyType.STRING:
                key_msg.property_type = edit_service_pb2.PropertyType.String
            case ActorPropertyType.ENUM:
                key_msg.property_type = edit_service_pb2.PropertyType.ENUM
            case ActorPropertyType.ASSET:
                key_msg.property_type = edit_service_pb2.PropertyType.ASSET
            case _:
                raise ValueError("Unsupported property type.")

        return key_msg

    def _create_property_value_message(self, key: ActorPropertyKey, value: Any):
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

    def _get_property_value_message_value(self, value_msg) -> Any:
        t = value_msg.WhichOneof("value_oneof")
        match t:
            case "value_bool":
                return value_msg.value_bool
            case "value_int":
                return value_msg.value_int
            case "value_float":
                return value_msg.value_float
            case "value_string":
                return value_msg.value_string
            case "value_asset":
                return value_msg.value_asset
            case _:
                return None

    async def get_properties(self, keys: List[ActorPropertyKey]) -> List[Any]:
        request = edit_service_pb2.GetPropertiesRequest()
        for key in keys:
            key_msg = self._create_property_key_message(key)
            request.keys.items.append(key_msg)

        response = await self.stub.GetProperties(request)
        self._check_response(response)

        values: List[Any] = []
        for value_msg in response.values.items:
            v = self._get_property_value_message_value(value_msg)
            values.append(v)
        return values

    async def set_properties(self, keys: List[ActorPropertyKey], values: List[Any]):
        if len(keys) != len(values):
            raise ValueError("Keys and values must have the same length.")

        request = edit_service_pb2.SetPropertiesRequest()
        for key, value in zip(keys, values):
            key_msg = self._create_property_key_message(key)
            request.keys.items.append(key_msg)
            value_msg = self._create_property_value_message(key, value)
            request.values.items.append(value_msg)

        response = await self.stub.SetProperties(request)
        self._check_response(response)

    async def custom_command(self, command: str):
        request = edit_service_pb2.CustomCommandRequest(command=command)
        response = await self.stub.CustomCommand(request)
        self._check_response(response)

    async def set_visibility(self, visible: bool, actor_paths: List[Path]):
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

        segment = NameWithIndex(name=msg.name, index=position)
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
        with perf_timer(
            "grpc_wrapper.get_entity_hierarchy_batch.total", feature="PARSE"
        ):
            request = edit_service_pb2.GetEntityHierarchyBatchRequest(
                actor_paths=[p.string() for p in actor_paths]
            )
            with perf_timer(
                "grpc_wrapper.get_entity_hierarchy_batch.network", feature="PARSE"
            ):
                response: edit_service_pb2.GetEntityHierarchyBatchResponse = (
                    await self.stub.GetEntityHierarchyBatch(request)
                )
            self._check_response(response)

            with perf_timer(
                "grpc_wrapper.get_entity_hierarchy_batch.parse", feature="PARSE"
            ):
                results: List[EntityInfo | None] = []
                for root_entity, error in zip(response.root_entities, response.errors):
                    if root_entity is not None and len(error) == 0:
                        results.append(
                            self._parse_entity_info(root_entity, None, [], 0)
                        )
                    else:
                        # For now, error is discarded.
                        results.append(None)
                return results

    async def get_entity_property_groups_batch(
        self, actor_path: Path, entity_ids: List[int]
    ) -> List[List[ActorPropertyGroup]]:
        with perf_timer(
            "grpc_wrapper.get_entity_property_groups_batch.total", feature="PARSE"
        ):
            request = edit_service_pb2.GetEntityPropertyGroupsBatchRequest(
                actor_path=actor_path.string(),
                entity_ids=entity_ids,
            )
            with perf_timer(
                "grpc_wrapper.get_entity_property_groups_batch.network", feature="PARSE"
            ):
                response = await self.stub.GetEntityPropertyGroupsBatch(request)
            self._check_response(response)

            with perf_timer(
                "grpc_wrapper.get_entity_property_groups_batch.parse", feature="PARSE"
            ):
                result: List[List[ActorPropertyGroup]] = []
                for pg_list_msg in response.property_group_lists:
                    groups: List[ActorPropertyGroup] = []
                    for pg_msg in pg_list_msg.elements:
                        pg = self._parse_property_group_msg(pg_msg)
                        groups.append(pg)
                    result.append(groups)
            return result

    async def get_assets_by_type_page(
        self, asset_type_uuid: str, page_index: int, page_size: int
    ):
        request = edit_service_pb2.GetAssetsByTypePageRequest(
            asset_type_uuid=asset_type_uuid,
            page_index=page_index,
            page_size=page_size,
        )
        response = await self.stub.GetAssetsByTypePage(request)
        self._check_response(response)
        return response

    async def get_all_entity_property_groups(
        self, actor_path: Path
    ) -> List[EntityPropertyGroupEntry]:
        with perf_timer(
            "grpc_wrapper.get_all_entity_property_groups.total", feature="PARSE"
        ):
            request = edit_service_pb2.GetAllEntityPropertyGroupsRequest(
                actor_path=actor_path.string(),
            )
            with perf_timer(
                "grpc_wrapper.get_all_entity_property_groups.network", feature="PARSE"
            ):
                response = await self.stub.GetAllEntityPropertyGroups(request)
            self._check_response(response)

            perf_log(
                f"grpc_wrapper.get_all_entity_property_groups: parsing {len(response.entries)} entries",
                feature="PARSE",
            )

            with perf_timer(
                "grpc_wrapper.get_all_entity_property_groups.parse", feature="PARSE"
            ):
                entries: List[EntityPropertyGroupEntry] = []
                for entry_msg in response.entries:
                    pg = self._parse_property_group_msg(entry_msg.property_group)
                    entry = EntityPropertyGroupEntry(
                        entity_id=entry_msg.entity_id,
                        entity_path=entry_msg.entity_path,
                        component_type=entry_msg.component_type,
                        component_display_name=entry_msg.component_display_name,
                        property_group=pg,
                    )
                    entries.append(entry)
            return entries
