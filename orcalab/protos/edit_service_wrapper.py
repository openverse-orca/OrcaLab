import asyncio
import grpc
import numpy as np
from typing import Any, List, Tuple

import orcalab.protos.edit_service_pb2_grpc as edit_service_pb2_grpc
import orcalab.protos.edit_service_pb2 as edit_service_pb2

from orcalab.math import Transform
from orcalab.path import Path
from orcalab.actor import BaseActor, GroupActor, AssetActor
from orcalab.actor_property import (
    ActorProperty,
    ActorPropertyGroup,
    ActorPropertyKey,
    ActorPropertyType,
)
from orcalab.ui.camera.camera_brief import CameraBrief

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
        self.stub = None
        self.channel = None

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
            print(f"[Error] {response.error_message}")
            raise Exception(f"Request failed. {response.error_message}")

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

    async def query_pending_operation_loop(self) -> List[str]:
        request = edit_service_pb2.GetPendingOperationsRequest()
        response = await self.stub.GetPendingOperations(request)
        self._check_response(response)
        return response.operations

    async def get_pending_actor_transform(self, path: Path, local: bool) -> Transform:
        space = edit_service_pb2.Space.Local if local else edit_service_pb2.Space.World
        request = edit_service_pb2.GetPendingActorTransformRequest(
            actor_path=path.string(),
            space=space,
        )
        response = await self.stub.GetPendingActorTransform(request)
        self._check_response(response)
        return self._get_transform_from_message(response.transform)

    async def add_group_actor(self, actor: GroupActor, parent_path: Path):
        assert isinstance(actor, GroupActor), "actor must be a GroupActor"
        transform_msg = self._create_transform_message(actor.transform)
        request = edit_service_pb2.AddGroupRequest(
            actor_name=actor.name,
            parent_actor_path=parent_path.string(),
            transform=transform_msg,
            space=edit_service_pb2.Space.Local,
        )
        response = await self.stub.AddGroup(request)

        self._check_response(response)

    async def add_asset_actor(self, actor: AssetActor, parent_path: Path):
        assert isinstance(actor, AssetActor), "actor must be an AssetActor"
        transform_msg = self._create_transform_message(actor.transform)

        request = edit_service_pb2.AddActorRequest(
            actor_name=actor.name,
            spawnable_name=actor.asset_path,
            parent_actor_path=parent_path.string(),
            transform=transform_msg,
            space=edit_service_pb2.Space.Local,
        )
        response = await self.stub.AddActor(request)

        self._check_response(response)

    async def set_actor_transform(self, path: Path, transform: Transform, local: bool):
        transform_msg = self._create_transform_message(transform)
        space = edit_service_pb2.Space.Local if local else edit_service_pb2.Space.World
        request = edit_service_pb2.SetActorTransformRequest(
            actor_path=path.string(),
            transform=transform_msg,
            space=space,
        )

        response = await self.stub.SetActorTransform(request)
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

    async def get_pending_selection_change(self) -> List[str]:
        request = edit_service_pb2.GetPendingSelectionChangeRequest()
        response = await self.stub.GetPendingSelectionChange(request)
        self._check_response(response)
        return response.actor_paths

    async def get_pending_add_item(self) -> Tuple[Transform, str]:
        request = edit_service_pb2.GetPendingAddItemRequest()
        response = await self.stub.GetPendingAddItem(request)
        self._check_response(response)
        transform = self._get_transform_from_message(response.transform)
        return (transform, response.actor_name)

    async def set_selection(self, actor_paths: List[Path]):
        paths = []
        for p in actor_paths:
            if not isinstance(p, Path):
                raise Exception(f"Invalid path: {p}")
            paths.append(p.string())

        request = edit_service_pb2.SetSelectionRequest(actor_paths=paths)
        response = await self.stub.SetSelection(request)
        self._check_response(response)

    async def get_actor_assets(self) -> List[str]:
        request = edit_service_pb2.GetActorAssetsRequest()
        response = await self.stub.GetActorAssets(request)
        self._check_response(response)
        return response.actor_asset_names

    async def save_body_transform(self):
        request = edit_service_pb2.SaveBodyTransformRequest()
        response = await self.stub.SaveBodyTransform(request)
        self._check_response(response)

    async def restore_body_transform(self):
        request = edit_service_pb2.RestoreBodyTransformRequest()
        response = await self.stub.RestoreBodyTransform(request)
        self._check_response(response)

    async def delete_actor(self, actor_path: Path):
        request = edit_service_pb2.DeleteActorRequest(actor_path=actor_path.string())
        response = await self.stub.DeleteActor(request)
        self._check_response(response)

    async def rename_actor(self, actor_path: Path, new_name: str):
        request = edit_service_pb2.RenameActorRequest(
            actor_path=actor_path.string(),
            new_name=new_name,
        )
        response = await self.stub.RenameActor(request)
        self._check_response(response)

    async def reparent_actor(self, actor_path: Path, new_parent_path: Path):
        request = edit_service_pb2.ReParentActorRequest(
            actor_path=actor_path.string(),
            new_parent_path=new_parent_path.string(),
        )

        response = await self.stub.ReParentActor(request)
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

    async def change_sim_state(self, sim_process_running: bool) -> bool:
        request = edit_service_pb2.ChangeSimStateRequest(
            sim_process_running=sim_process_running
        )
        response = await self.stub.ChangeSimState(request)
        self._check_response(response)
        return response

    async def change_manipulator_type(self, manipulator_type: int) -> bool:
        request = edit_service_pb2.ChangeManipulatorTypeRequest(
            manipulator_type=manipulator_type
        )
        response = await self.stub.ChangeManipulatorType(request)
        self._check_response(response)
        return response

    async def get_camera_png(self, camera_name: str, png_path: str, png_name: str) -> bool:
        request = edit_service_pb2.GetCameraPNGRequest(
            camera_name=camera_name,
            png_path=png_path,
            png_name=png_name,
        )
        response = await self.stub.GetCameraPNG(request)
        if response.status_code != Success:
            return False
        return True

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
            camera_brief.source = cam.source
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

    async def get_property_groups(self, actor_path: Path) -> List[ActorPropertyGroup]:
        request = edit_service_pb2.GetPropertyGroupsRequest()
        request.actor_path = actor_path.string()
        response = await self.stub.GetPropertyGroups(request)
        self._check_response(response)

        property_groups: List[ActorPropertyGroup] = []

        for pg_msg in response.property_groups:
            pg = ActorPropertyGroup(
                prefix=pg_msg.prefix, name=pg_msg.name, hint=pg_msg.hint
            )

            for prop_msg in pg_msg.properties:
                match prop_msg.type:
                    case edit_service_pb2.PropertyType.Unknown:
                        break
                    case edit_service_pb2.PropertyType.Bool:
                        prop = ActorProperty(
                            name=prop_msg.name,
                            display_name=prop_msg.display_name,
                            type=ActorPropertyType.BOOL,
                            value=False,
                        )
                        pg.properties.append(prop)
                    case edit_service_pb2.PropertyType.Int:
                        prop = ActorProperty(
                            name=prop_msg.name,
                            display_name=prop_msg.display_name,
                            type=ActorPropertyType.INTEGER,
                            value=0,
                        )
                        pg.properties.append(prop)
                    case edit_service_pb2.PropertyType.Float:
                        prop = ActorProperty(
                            name=prop_msg.name,
                            display_name=prop_msg.display_name,
                            type=ActorPropertyType.FLOAT,
                            value=0.0,
                        )
                        pg.properties.append(prop)
                    case edit_service_pb2.PropertyType.String:
                        prop = ActorProperty(
                            name=prop_msg.name,
                            display_name=prop_msg.display_name,
                            type=ActorPropertyType.STRING,
                            value="",
                        )
                        pg.properties.append(prop)

            property_groups.append(pg)

        return property_groups

    def _create_property_key_message(self, key: ActorPropertyKey):
        key_msg = edit_service_pb2.PropertyKey()
        key_msg.actor_path = key.actor_path.string()
        key_msg.group_prefix = key.group_prefix
        key_msg.property_name = key.property_name
        key_msg.property_type = key.property_type.value
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
