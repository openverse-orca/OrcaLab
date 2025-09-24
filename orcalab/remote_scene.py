from orcalab.config_service import ConfigService
from orcalab.math import Transform
import orcalab.protos.edit_service_pb2_grpc as edit_service_pb2_grpc
import orcalab.protos.edit_service_pb2 as edit_service_pb2
import orca_gym.protos.mjc_message_pb2_grpc as mjc_message_pb2_grpc
import orca_gym.protos.mjc_message_pb2 as mjc_message_pb2

from orcalab.path import Path
from orcalab.actor import BaseActor, GroupActor, AssetActor

import os
import grpc
import numpy as np
from typing import List
import subprocess
import time
import pathlib
import psutil

Success = edit_service_pb2.StatusCode.Success
Error = edit_service_pb2.StatusCode.Error


# 由于Qt是异步的，所以这里只提供异步接口。
class RemoteScene:
    def __init__(self, config_service: ConfigService):
        super().__init__()

        self.config_service = config_service

        self.edit_grpc_addr = f"localhost:{self.config_service.edit_port()}"
        self.server_process = None  # Initialize server_process to None
        self.server_process_pid = None  # Track the actual process PID
        self.executable_path = self.config_service.executable()
        self.sim_grpc_addr = f"localhost:{self.config_service.sim_port()}"
    
    def _find_orca_processes(self):
        """Find all OrcaStudio.GameLauncher processes"""
        processes = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'exe']):
                try:
                    # Check by executable name
                    if proc.info['name'] and 'OrcaStudio.GameLauncher' in proc.info['name']:
                        processes.append(proc)
                    # Check by executable path
                    elif proc.info['exe'] and self.executable_path in proc.info['exe']:
                        processes.append(proc)
                    # Check by command line
                    elif proc.info['cmdline'] and any(self.executable_path in str(cmd) for cmd in proc.info['cmdline']):
                        processes.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
        except Exception as e:
            print(f"Error finding OrcaStudio processes: {e}")
        return processes
    
    def _cleanup_orca_processes(self, timeout=10):
        """Clean up all OrcaStudio.GameLauncher processes using the same executable path"""
        print("Starting OrcaStudio.GameLauncher process cleanup...")
        
        # Find all processes using the same executable path
        processes_to_cleanup = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'exe']):
                try:
                    # Check by executable path
                    if proc.info['exe'] and self.executable_path in proc.info['exe']:
                        processes_to_cleanup.append(proc)
                    # Check by executable name
                    elif proc.info['name'] and 'OrcaStudio.GameLauncher' in proc.info['name']:
                        processes_to_cleanup.append(proc)
                    # Check by command line
                    elif proc.info['cmdline'] and any(self.executable_path in str(cmd) for cmd in proc.info['cmdline']):
                        processes_to_cleanup.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
        except Exception as e:
            print(f"Error finding OrcaStudio processes: {e}")
        
        if not processes_to_cleanup:
            print("No OrcaStudio.GameLauncher processes found to clean up")
            return
        
        print(f"Found {len(processes_to_cleanup)} OrcaStudio.GameLauncher processes to clean up:")
        for proc in processes_to_cleanup:
            print(f"  - PID {proc.pid}: {proc.info['name']}")
        
        # First, try graceful termination for all processes
        print("Sending TERM signals to all processes...")
        for proc in processes_to_cleanup:
            try:
                if proc.is_running():
                    print(f"  Sending TERM to PID {proc.pid}")
                    proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                print(f"  Could not terminate PID {proc.pid}: {e}")
        
        # Wait for graceful termination
        print(f"Waiting {timeout} seconds for graceful termination...")
        time.sleep(timeout)
        
        # Check for remaining processes and force kill if necessary
        remaining_processes = []
        for proc in processes_to_cleanup:
            try:
                if proc.is_running():
                    remaining_processes.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if remaining_processes:
            print(f"Force killing {len(remaining_processes)} remaining processes...")
            for proc in remaining_processes:
                try:
                    print(f"  Force killing PID {proc.pid}")
                    proc.kill()
                    proc.wait(timeout=5)
                    print(f"  Successfully killed PID {proc.pid}")
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired) as e:
                    print(f"  Could not kill PID {proc.pid}: {e}")
        else:
            print("All OrcaStudio.GameLauncher processes terminated gracefully")
        
        # Clear the tracked PID
        self.server_process_pid = None
    
    def __del__(self):
        """Destructor to ensure server process is cleaned up"""
        try:
            print("Cleaning up server process in destructor...")
            # Use the new cleanup mechanism
            self._cleanup_orca_processes(timeout=5)
        except Exception as e:
            print(f"Error in destructor cleaning up server process: {e}")

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

        if not self.config_service.attach():
            await self._launch()
        else:
            await self._attach()

        print("connected to server.")

    async def _launch(self):
        print(f"launching server: {self.edit_grpc_addr}")

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

        print(" ".join(cmds))

        # Viewport 会生成一些文件，所以需要指定工作目录。
        server_process = subprocess.Popen(cmds, cwd=str(executable_folder))
        if server_process is None:
            raise Exception("Failed to launch server process.")

        # Record the process PID for tracking
        self.server_process_pid = server_process.pid
        print(f"Launched OrcaStudio.GameLauncher with PID: {self.server_process_pid}")

        # We can 'block' here.
        max_wait_time = 10
        while True:
            if await self.aloha():
                break
            time.sleep(1)
            print("waiting for server to be ready...")
            if server_process.poll() is not None:
                raise Exception("Server process exited unexpectedly.")
            max_wait_time -= 1
            if max_wait_time <= 0:
                server_process.terminate()
                raise Exception("Timeout waiting for server to be ready.")

        self.server_process = server_process

    async def _attach(self):
        print(f"connecting to existing server: {self.edit_grpc_addr}")
        if not await self.aloha():
            raise Exception("Failed to connect to server.")
        self.server_process = None
        self.server_process_pid = None  # No process to track in attach mode

    async def destroy_grpc(self):
        if self.edit_channel:
            await self.edit_channel.close()
        self.edit_stub = None
        self.edit_channel = None

        if self.sim_channel:
            await self.sim_channel.close()
        self.sim_stub = None
        self.sim_channel = None
        
        # Clean up OrcaStudio.GameLauncher processes using the new mechanism
        self._cleanup_orca_processes(timeout=10)
        
        # Also clean up the subprocess object if it exists
        if hasattr(self, 'server_process') and self.server_process is not None:
            try:
                self.server_process = None
            except Exception as e:
                print(f"Error cleaning up server process object: {e}")

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
                spawnable_name=actor.spawnable_name,
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
        print(f"publish_scene")
        request = mjc_message_pb2.PublishSceneRequest()
        response = await self.sim_stub.PublishScene(request)
        if response.status != mjc_message_pb2.PublishSceneResponse.SUCCESS:
            print("Publish scene failed: ", response.error_message)
            raise Exception("Publish scene failed.")
        print("done")

    async def forward_scene(self):
        print(f"forward_scene")
        request = mjc_message_pb2.MJ_ForwardRequest()
        response = await self.sim_stub.MJ_Forward(request)
        print("done")

    async def get_sync_from_mujoco_to_scene(self) -> bool:
        request = edit_service_pb2.GetSyncFromMujocoToSceneRequest()
        response = await self.edit_stub.GetSyncFromMujocoToScene(request)
        self._check_response(response)
        return response.value

    async def set_sync_from_mujoco_to_scene(self, value: bool):
        print(f"set_sync_from_mujoco_to_scene {value}")
        request = edit_service_pb2.SetSyncFromMujocoToSceneRequest(value=value)
        response = await self.edit_stub.SetSyncFromMujocoToScene(request)
        self._check_response(response)
        print("done")

    async def clear_scene(self):
        request = edit_service_pb2.ClearSceneRequest()
        response = await self.edit_stub.ClearScene(request)
        self._check_response(response)

    async def get_pending_selection_change(self) -> list[str]:
        request = edit_service_pb2.GetPendingSelectionChangeRequest()
        response = await self.edit_stub.GetPendingSelectionChange(request)
        self._check_response(response)
        return response.actor_paths

    async def get_pending_add_item(self) -> Transform:
        request = edit_service_pb2.GetPendingAddItemRequest()
        response = await self.edit_stub.GetPendingAddItem(request)
        self._check_response(response)
        return [response.transform, response.actor_name]

    async def set_selection(self, actor_paths: list[Path]):
        paths = []
        for p in actor_paths:
            if not isinstance(p, Path):
                raise Exception(f"Invalid path: {p}")
            paths.append(p.string())

        request = edit_service_pb2.SetSelectionRequest(actor_paths=paths)
        response = await self.edit_stub.SetSelection(request)
        self._check_response(response)

    async def get_actor_assets(self):
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
        return response

    async def get_cache_folder(self) -> str:
        request = edit_service_pb2.GetCacheFolderRequest()
        response = await self.edit_stub.GetCacheFolder(request)
        self._check_response(response)
        return response.cache_folder

    async def load_package(self, package_path: str) -> bool:
        request = edit_service_pb2.LoadPackageRequest(file_path=package_path)
        response = await self.edit_stub.LoadPackage(request)
        self._check_response(response)
        return response.success
    
    async def change_sim_state(self, sim_process_running: bool) -> bool:
            request = edit_service_pb2.ChangeSimStateRequest(sim_process_running=sim_process_running)
            response = await self.edit_stub.ChangeSimState(request)
            self._check_response(response)
            return response
