import asyncio
from orcalab.actor_property import (
    ActorProperty,
    ActorPropertyGroup,
    ActorPropertyKey,
    ActorPropertyType,
)
from orcalab.config_service import ConfigService
from orcalab.math import Transform
import orcalab.protos.edit_service_pb2_grpc as edit_service_pb2_grpc
import orcalab.protos.edit_service_pb2 as edit_service_pb2
import orca_gym.protos.mjc_message_pb2_grpc as mjc_message_pb2_grpc
import orca_gym.protos.mjc_message_pb2 as mjc_message_pb2

from orcalab.path import Path
from orcalab.actor import BaseActor, GroupActor, AssetActor

from orcalab.scene_edit_bus import (
    SceneEditNotificationBus,
    SceneEditNotification,
    SceneEditRequestBus,
    make_unique_name,
)

import os
import grpc
import numpy as np
from typing import Any, List, Tuple, override
import subprocess
import time
import pathlib
import psutil
import logging

from orcalab.ui.camera.camera_brief import CameraBrief
from orcalab.ui.camera.camera_bus import CameraNotificationBus

Success = edit_service_pb2.StatusCode.Success
Error = edit_service_pb2.StatusCode.Error

logger = logging.getLogger(__name__)


# 由于Qt是异步的，所以这里只提供异步接口。
class RemoteScene(SceneEditNotification):
    def __init__(self, config_service: ConfigService):
        super().__init__()

        self.config_service = config_service

        self.edit_grpc_addr = f"localhost:{self.config_service.edit_port()}"
        self.server_process = None  # Initialize server_process to None
        self.server_process_pid = None  # Track the actual process PID
        self.executable_path = self.config_service.executable()
        self.sim_grpc_addr = f"localhost:{self.config_service.sim_port()}"

        self.in_query = False
        self.shutdown = False

        self.actor_in_editing: Path | None = None
        self.current_transform: Transform | None = None

    def connect_bus(self):
        SceneEditNotificationBus.connect(self)

    def disconnect_bus(self):
        SceneEditNotificationBus.disconnect(self)

    def _find_orca_processes(self):
        """Find all OrcaStudio.GameLauncher processes"""
        processes = []
        try:
            for proc in psutil.process_iter(["pid", "name", "cmdline", "exe"]):
                try:
                    # Check by executable name
                    if (
                        proc.info["name"]
                        and "OrcaStudio.GameLauncher" in proc.info["name"]
                    ):
                        processes.append(proc)
                    # Check by executable path
                    elif proc.info["exe"] and self.executable_path in proc.info["exe"]:
                        processes.append(proc)
                    # Check by command line
                    elif proc.info["cmdline"] and any(
                        self.executable_path in str(cmd) for cmd in proc.info["cmdline"]
                    ):
                        processes.append(proc)
                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):
                    pass
        except Exception as e:
            logger.exception("查找 OrcaStudio 进程失败: %s", e)
        return processes

    def _cleanup_orca_processes(self, timeout=1):
        """Clean up only the OrcaStudio.GameLauncher process launched by this instance"""
        logger.info("开始清理 OrcaStudio.GameLauncher 进程…")

        # Only clean up the process we launched (if any)
        if self.server_process_pid is None:
            logger.info("没有需要清理的 OrcaStudio.GameLauncher 进程")
            return

        try:
            # Find the specific process by PID
            proc = psutil.Process(self.server_process_pid)
            if not proc.is_running():
                logger.info("进程 PID %s 已不在运行", self.server_process_pid)
                self.server_process_pid = None
                return

            logger.info(
                "找到需要清理的 OrcaStudio.GameLauncher 进程，PID %s",
                self.server_process_pid,
            )

            # Try graceful termination
            logger.info("发送 TERM 信号至 PID %s", self.server_process_pid)
            proc.terminate()

            # Wait for graceful termination
            logger.info("等待 %s 秒以便进程优雅退出…", timeout)
            time.sleep(timeout)

            # Check if process is still running
            if proc.is_running():
                logger.warning(
                    "进程 PID %s 未退出，执行强制结束", self.server_process_pid
                )
                proc.kill()
                proc.wait(timeout=5)
                logger.info("已成功强制结束 PID %s", self.server_process_pid)
            else:
                logger.info("进程 PID %s 已优雅退出", self.server_process_pid)

        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.warning("无法清理进程 PID %s: %s", self.server_process_pid, e)
        except Exception as e:
            logger.exception("清理进程时出错: %s", e)
        finally:
            # Clear the tracked PID
            self.server_process_pid = None

    async def init_grpc(self):
        options = [
            ("grpc.max_receive_message_length", 1024 * 1024 * 1024),
            ("grpc.max_send_message_length", 1024 * 1024 * 1024),
        ]
        self.edit_channel = grpc.aio.insecure_channel(
            self.edit_grpc_addr,
            options=options,
        )
        self.sim_channel = grpc.aio.insecure_channel(
            self.sim_grpc_addr,
            options=options,
        )
        self.edit_stub = edit_service_pb2_grpc.GrpcServiceStub(self.edit_channel)
        self.sim_stub = mjc_message_pb2_grpc.GrpcServiceStub(self.sim_channel)

        self.timeout = 3

        # if not self.config_service.attach():
        #     await self._launch()
        # else:
        #     await self._attach()

        await self._attach()

        await self.change_sim_state(False)
        logger.info("已连接到服务器")

        # Start the pending operation loop.
        await self._query_pending_operation_loop()

    async def _launch(self):
        logger.info("启动服务器: %s", self.edit_grpc_addr)

        executable = pathlib.Path(self.config_service.executable())
        if not executable.exists():
            raise Exception(f"Executable not found: {executable}")

        executable_folder = executable.parent

        cmds = [
            str(executable),
            "--project-path ",
            self.config_service.orca_project_folder(),
            "--datalink_host ",
            "54.223.63.47",
            "--datalink_port",
            "7000",
            "--LoadLevel",
            self.config_service.level(),
            self.config_service.lock_fps(),
        ]

        logger.debug("启动命令: %s", " ".join(cmds))

        # Viewport 会生成一些文件，所以需要指定工作目录。
        server_process = subprocess.Popen(cmds, cwd=str(executable_folder))
        if server_process is None:
            raise Exception("Failed to launch server process.")

        # Record the process PID for tracking
        self.server_process_pid = server_process.pid
        logger.info("已启动 OrcaStudio.GameLauncher，PID=%s", self.server_process_pid)

        # We can 'block' here.
        max_wait_time = 60  # 资产太多的时候，重启电脑加载会比较久
        while True:
            try:
                if await self.aloha():
                    break
            except Exception as e:
                pass
            time.sleep(1)
            logger.debug("等待服务器就绪…")
            if server_process.poll() is not None:
                raise Exception("Server process exited unexpectedly.")
            max_wait_time -= 1
            if max_wait_time <= 0:
                server_process.terminate()
                raise Exception("Timeout waiting for server to be ready.")

        self.server_process = server_process

    async def _attach(self):
        logger.info("连接现有服务器: %s", self.edit_grpc_addr)
        if not await self.aloha():
            raise Exception("Failed to connect to server.")
        self.server_process = None
        self.server_process_pid = None  # No process to track in attach mode

    async def destroy_grpc(self):
        self.shutdown = True
        while self.in_query:
            print("Waiting for pending operation query to finish...")
            await asyncio.sleep(0.1)

        if self.edit_channel:
            await self.edit_channel.close()
        self.edit_stub = None
        self.edit_channel = None

        if self.sim_channel:
            await self.sim_channel.close()
        self.sim_stub = None
        self.sim_channel = None

        # Clean up OrcaStudio.GameLauncher processes using the new mechanism
        self._cleanup_orca_processes(timeout=1)

        # Also clean up the subprocess object if it exists
        if hasattr(self, "server_process") and self.server_process is not None:
            try:
                self.server_process = None
            except Exception as e:
                logger.exception("清理 server_process 对象失败: %s", e)

    async def _query_pending_operation_loop(self):
        if self.shutdown:
            return

        self.in_query = True

        operations = await self.query_pending_operation_loop()
        optimized_operations = self._optimize_operation(operations)
        for op in optimized_operations:
            await self._process_pending_operation(op)

        self.in_query = False

        await asyncio.sleep(0.01)
        if not self.shutdown:
            asyncio.create_task(self._query_pending_operation_loop())

    async def _process_pending_operation(self, op: str):
        # print(op)
        sltc = "start_local_transform_change:"
        if op.startswith(sltc):
            actor_path = Path(op[len(sltc) :])

            if self.actor_in_editing is not None:
                raise Exception(
                    f"Another actor is being edited: {self.actor_in_editing}"
                )
            SceneEditRequestBus().record_old_transform(actor_path)
            self.actor_in_editing = actor_path

        eltc = "end_local_transform_change:"
        if op.startswith(eltc):
            actor_path = Path(op[len(eltc) :])

            if self.actor_in_editing != actor_path:
                raise Exception(
                    f"Actor in editing mismatch: {self.actor_in_editing} vs {actor_path}"
                )

            # Trigger an undoable transform change.
            if isinstance(self.current_transform, Transform):
                await SceneEditRequestBus().set_transform(
                    actor_path,
                    self.current_transform,
                    local=True,
                    undo=True,
                    source="remote_scene",
                )

            # Transform on viewport will be updated by on_transform_changed.

            self.actor_in_editing = None
            self.current_transform = None

        swtc = "start_world_transform_change:"
        if op.startswith(swtc):
            actor_path = Path(op[len(swtc) :])

            if self.actor_in_editing is not None:
                raise Exception(
                    f"Another actor is being edited: {self.actor_in_editing}"
                )
            SceneEditRequestBus().record_old_transform(actor_path)
            self.actor_in_editing = actor_path

        ewtc = "end_world_transform_change:"
        if op.startswith(ewtc):
            actor_path = Path(op[len(ewtc) :])

            if self.actor_in_editing != actor_path:
                raise Exception(
                    f"Actor in editing mismatch: {self.actor_in_editing} vs {actor_path}"
                )

            # Trigger an undoable transform change.
            if isinstance(self.current_transform, Transform):
                await SceneEditRequestBus().set_transform(
                    actor_path,
                    self.current_transform,
                    local=False,
                    undo=True,
                    source="remote_scene",
                )

            self.actor_in_editing = None
            self.current_transform = None

        local_transform_change = "local_transform_change:"
        if op.startswith(local_transform_change):
            actor_path = Path(op[len(local_transform_change) :])

            # Currently only support drag from viewport. So actor_in_editing must be set.
            if self.actor_in_editing is None:
                raise Exception(
                    f"No actor is being edited, but got local transform change for {actor_path}"
                )

            if actor_path != self.actor_in_editing:
                raise Exception(
                    f"Actor in editing mismatch: {self.actor_in_editing} vs {actor_path}"
                )

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

        world_transform_change = "world_transform_change:"
        if op.startswith(world_transform_change):
            actor_path = Path(op[len(world_transform_change) :])

            if self.actor_in_editing is None:
                raise Exception(
                    f"No actor is being edited, but got world transform change for {actor_path}"
                )
            if actor_path != self.actor_in_editing:
                raise Exception(
                    f"Actor in editing mismatch: {self.actor_in_editing} vs {actor_path}"
                )
            self.current_transform = await self.get_pending_actor_transform(
                actor_path, local=False
            )
            await SceneEditRequestBus().set_transform(
                actor_path,
                self.current_transform,
                local=False,
                undo=False,
                source="remote_scene",
            )
            # Transform on viewport will be updated by on_transform_changed.

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

        asyncio.create_task(self.set_selection(new_selection))

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
            raise Exception(f"Request failed. {response.error_message}")

    async def aloha(self) -> bool:
        try:
            request = edit_service_pb2.AlohaRequest(value=1)
            response = await self.edit_stub.Aloha(request)
            self._check_response(response)
            if response.value != 2:
                raise Exception("Invalid response value.")
            return True
        except Exception as e:
            return False

    async def query_pending_operation_loop(self) -> List[str]:
        request = edit_service_pb2.GetPendingOperationsRequest()
        response = await self.edit_stub.GetPendingOperations(request)
        self._check_response(response)
        return response.operations

    async def get_pending_actor_transform(self, path: Path, local: bool) -> Transform:
        space = edit_service_pb2.Space.Local if local else edit_service_pb2.Space.World

        request = edit_service_pb2.GetPendingActorTransformRequest(
            actor_path=path.string(),
            space=space,
        )

        response = await self.edit_stub.GetPendingActorTransform(request)
        self._check_response(response)

        transform = response.transform
        return self._get_transform_from_message(transform)

    async def add_actor(self, actor: BaseActor, parent_path: Path):
        transform_msg = self._create_transform_message(actor.transform)

        if isinstance(actor, GroupActor):
            request = edit_service_pb2.AddGroupRequest(
                actor_name=actor.name,
                parent_actor_path=parent_path.string(),
                transform=transform_msg,
                space=edit_service_pb2.Space.Local,
            )
            response = await self.edit_stub.AddGroup(request)
        elif isinstance(actor, AssetActor):
            request = edit_service_pb2.AddActorRequest(
                actor_name=actor.name,
                spawnable_name=actor.asset_path,
                parent_actor_path=parent_path.string(),
                transform=transform_msg,
                space=edit_service_pb2.Space.Local,
            )
            response = await self.edit_stub.AddActor(request)
        else:
            raise Exception(f"Unsupported actor type: {type(actor)}")

        self._check_response(response)

    async def set_actor_transform(self, path: Path, transform: Transform, local: bool):
        transform_msg = self._create_transform_message(transform)
        space = edit_service_pb2.Space.Local if local else edit_service_pb2.Space.World

        request = edit_service_pb2.SetActorTransformRequest(
            actor_path=path.string(),
            transform=transform_msg,
            space=space,
        )

        response = await self.edit_stub.SetActorTransform(request, timeout=self.timeout)
        self._check_response(response)

    async def publish_scene(self):
        logger.debug("Publish scene")
        request = mjc_message_pb2.PublishSceneRequest()
        response = await self.sim_stub.PublishScene(request)
        if response.status != mjc_message_pb2.PublishSceneResponse.SUCCESS:
            logger.error("Publish scene failed: %s", response.error_message)
            raise Exception("Publish scene failed.")
        logger.debug("Publish scene completed")

    async def forward_scene(self):
        logger.debug("Forward scene")
        request = mjc_message_pb2.MJ_ForwardRequest()
        response = await self.sim_stub.MJ_Forward(request)
        logger.debug("Forward scene completed")

    async def get_sync_from_mujoco_to_scene(self) -> bool:
        request = edit_service_pb2.GetSyncFromMujocoToSceneRequest()
        response = await self.edit_stub.GetSyncFromMujocoToScene(request)
        self._check_response(response)
        return response.value

    async def set_sync_from_mujoco_to_scene(self, value: bool):
        logger.debug("Set sync_from_mujoco_to_scene: %s", value)
        request = edit_service_pb2.SetSyncFromMujocoToSceneRequest(value=value)
        response = await self.edit_stub.SetSyncFromMujocoToScene(request)
        self._check_response(response)
        logger.debug("Set sync_from_mujoco_to_scene completed")

    async def clear_scene(self):
        request = edit_service_pb2.ClearSceneRequest()
        response = await self.edit_stub.ClearScene(request)
        self._check_response(response)

    async def get_pending_selection_change(self) -> list[str]:
        request = edit_service_pb2.GetPendingSelectionChangeRequest()
        response = await self.edit_stub.GetPendingSelectionChange(request)
        self._check_response(response)
        return response.actor_paths

    async def get_pending_add_item(self) -> Tuple[Transform, str]:
        request = edit_service_pb2.GetPendingAddItemRequest()
        response = await self.edit_stub.GetPendingAddItem(request)
        self._check_response(response)

        transform = self._get_transform_from_message(response.transform)
        return (transform, response.actor_name)

    async def set_selection(self, actor_paths: list[Path]):
        paths = []
        for p in actor_paths:
            if not isinstance(p, Path):
                raise Exception(f"Invalid path: {p}")
            paths.append(p.string())

        request = edit_service_pb2.SetSelectionRequest(actor_paths=paths)
        response = await self.edit_stub.SetSelection(request)
        self._check_response(response)

    async def get_actor_assets(self) -> List[str]:
        request = edit_service_pb2.GetActorAssetsRequest()
        response = await self.edit_stub.GetActorAssets(request)
        self._check_response(response)
        return response.actor_asset_names

    async def save_body_transform(self):
        request = edit_service_pb2.SaveBodyTransformRequest()
        response = await self.edit_stub.SaveBodyTransform(request)
        self._check_response(response)

    async def restore_body_transform(self):
        request = edit_service_pb2.RestoreBodyTransformRequest()
        response = await self.edit_stub.RestoreBodyTransform(request)
        self._check_response(response)

    async def delete_actor(self, actor_path: Path):
        request = edit_service_pb2.DeleteActorRequest(actor_path=actor_path.string())
        response = await self.edit_stub.DeleteActor(request)
        self._check_response(response)

    async def rename_actor(self, actor_path: Path, new_name: str):
        request = edit_service_pb2.RenameActorRequest(
            actor_path=actor_path.string(),
            new_name=new_name,
        )
        response = await self.edit_stub.RenameActor(request)
        self._check_response(response)

    async def reparent_actor(self, actor_path: Path, new_parent_path: Path):
        request = edit_service_pb2.ReParentActorRequest(
            actor_path=actor_path.string(),
            new_parent_path=new_parent_path.string(),
        )
        response = await self.edit_stub.ReParentActor(request)
        self._check_response(response)

    async def get_window_id(self):
        request = edit_service_pb2.GetWindowIdRequest()
        response = await self.edit_stub.GetWindowId(request)
        self._check_response(response)
        return response

    async def get_generate_pos(self, posX, posY):
        request = edit_service_pb2.GetGeneratePosRequest(
            posX=posX,
            posY=posY,
        )
        response = await self.edit_stub.GetGeneratePos(request)
        self._check_response(response)
        return self._get_transform_from_message(response.transform)

    async def get_cache_folder(self) -> str:
        request = edit_service_pb2.GetCacheFolderRequest()
        response = await self.edit_stub.GetCacheFolder(request)
        self._check_response(response)
        return response.cache_folder

    async def load_package(self, package_path: str) -> None:
        request = edit_service_pb2.LoadPackageRequest(file_path=package_path)
        response = await self.edit_stub.LoadPackage(request)
        self._check_response(response)

    async def change_sim_state(self, sim_process_running: bool) -> bool:
        logger.debug("Change sim_state -> %s", sim_process_running)
        request = edit_service_pb2.ChangeSimStateRequest(
            sim_process_running=sim_process_running
        )
        response = await self.edit_stub.ChangeSimState(request)
        self._check_response(response)
        return response

    async def get_camera_png(self, camera_name: str, png_path: str, png_name: str):
        request = edit_service_pb2.GetCameraPNGRequest(
            camera_name=camera_name,
            png_path=png_path,
            png_name=png_name,
        )
        response = await self.edit_stub.GetCameraPNG(request)
        if response.status_code != Success:
            retry = 2
            while retry > 0:
                response = await self.edit_stub.GetCameraPNG(request)
                if response.status_code == Success:
                    break
                retry -= 1
                await asyncio.sleep(0.01)
        return response

    async def get_actor_asset_aabb(self, actor_path: Path, output: List[float] = None):
        request = edit_service_pb2.GetActorAssetAabbRequest(
            actor_path=actor_path.string()
        )
        response = await self.edit_stub.GetActorAssetAabb(request)
        self._check_response(response)
        if output is not None:
            output.extend(response.min)
            output.extend(response.max)
        return response

    async def queue_mouse_event(
        self,
        x: float,
        y: float,
        button: int,
        action: int,
    ):
        request = edit_service_pb2.QueueMouseEventRequest(
            x=x,
            y=y,
            button=button,
            action=action,
        )
        response = await self.edit_stub.QueueMouseEvent(request)
        self._check_response(response)

    async def queue_mouse_wheel_event(self, delta: int):
        request = edit_service_pb2.QueueMouseWheelEventRequest(delta=delta)
        response = await self.edit_stub.QueueMouseWheelEvent(request)
        self._check_response(response)

    async def queue_key_event(
        self,
        key: int,
        action: int,
    ):
        request = edit_service_pb2.QueueKeyEventRequest(
            key=key,
            action=action,
        )
        response = await self.edit_stub.QueueKeyEvent(request)
        self._check_response(response)

    async def get_cameras(self) -> List[CameraBrief]:
        request = edit_service_pb2.GetCamerasRequest()
        response = await self.edit_stub.GetCameras(request)
        self._check_response(response)

        l = []
        for cam in response.cameras:
            camera_brief = CameraBrief(
                index=cam.index,
                name=cam.name,
            )
            camera_brief.source = cam.source
            l.append(camera_brief)

        return l

    async def get_active_camera(self) -> int:
        request = edit_service_pb2.GetActiveCameraRequest()
        response = await self.edit_stub.GetActiveCamera(request)
        self._check_response(response)
        return response.index

    async def set_active_camera(self, camera_index: int) -> None:
        request = edit_service_pb2.SetActiveCameraRequest(index=camera_index)
        response = await self.edit_stub.SetActiveCamera(request)
        self._check_response(response)

    async def get_property_groups(self, actor_path: Path) -> List[ActorPropertyGroup]:
        request = edit_service_pb2.GetPropertyGroupsRequest()
        request.actor_path = actor_path.string()
        response = await self.edit_stub.GetPropertyGroups(request)
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

        response = await self.edit_stub.GetProperties(request)
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

        response = await self.edit_stub.SetProperties(request)
        self._check_response(response)
