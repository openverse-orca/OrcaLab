import asyncio
import base64
import json
import os
import time
import numpy as np
import tempfile
from fastmcp import FastMCP
from fastmcp.utilities.types import Image
from orcalab.config_service import ConfigService
from orcalab.remote_scene import RemoteScene
from scipy.spatial.transform import Rotation
from orcalab.math import Transform
from orcalab.metadata_service_bus import MetadataServiceRequestBus
from orcalab.scene_edit_bus import SceneEditNotificationBus, SceneEditRequestBus
from orcalab.actor import AssetActor, BaseActor, GroupActor
from orcalab.path import Path
from typing import List, Dict

from orcalab.simulation.simulation_bus import SimulationRequestBus, SimulationState
from orcalab.ui.camera.camera_brief import CameraBrief
from orcalab.ui.camera.camera_bus import CameraRequestBus
from orcalab.application_util import get_remote_scene
from orcalab.application_bus import ApplicationRequestBus
from orcalab.scene_edit_bus import SceneEditRequestBus
from orcalab.undo_service.undo_service_bus import UndoRequestBus
from orcalab.actor_property import ActorPropertyKey, ActorPropertyType
from orcalab.asset_service_bus import AssetServiceRequestBus
from orcalab.http_service.http_bus import HttpServiceRequestBus
from orcalab.ui.panel_bus import PanelRequestBus
from orcalab.copilot.service import CopilotService

class OrcaLabMCPServer:
    def __init__(self, port):
        self.port = port
        self.config_service = ConfigService()
        self.metadata_service_bus = MetadataServiceRequestBus()
        self.scene_edit_bus = SceneEditRequestBus()
        self.scene_edit_notification_bus = SceneEditNotificationBus()
        self.simulation_bus = SimulationRequestBus()
        self.undo_bus = UndoRequestBus()
        self.camera_bus = CameraRequestBus()
        self.asset_service_bus = AssetServiceRequestBus()
        self.http_service_bus = HttpServiceRequestBus()
        self.panel_bus = PanelRequestBus()
        self.copilot_service = CopilotService()
        self.mcp = FastMCP("OrcaLab MCP Server")
        self._task = None
        # Register tools immediately after MCP instance creation
        self.add_tools()

    def get_asset_map(self) -> str:
        '''
        获取所有已订阅资产的元数据信息
        Args:
            无需传递参数
        Returns:
            所有已订阅资产的元数据信息的json字符串格式
        '''
        output = []
        self.metadata_service_bus.get_asset_map(output)
        asset_map = output[0]
        # 去除分类为场景的资产信息，每个资产只返回 name / category / description / assetpath
        def _category_str(val):  # category 可能是 str 或 list
            if val is None:
                return ""
            if isinstance(val, list):
                return "/".join(str(x) for x in val) if val else ""
            return str(val)

        result = {}
        for path, info in asset_map.items():
            cat = _category_str(info.get("category"))
            if "scene" in cat.lower():
                continue
            result[path] = {
                "name": info.get("name", ""),
                "category": cat,
                "description": info.get("description", ""),
                "is3dgs": info.get("is3dgs", False),
                "assetpath": path,
            }
        return json.dumps(result, ensure_ascii=False)

    def get_asset_info(self, asset_path: str) -> str:
        '''
        获取指定资产的元数据信息
        Args:
            asset_path: 资产的路径，该参数可以从所有元数据信息中获取。
        Returns:
            指定资产元数据信息
        '''
        output = []
        self.metadata_service_bus.get_asset_info(asset_path, output)
        asset_info = output[0]
        return json.dumps(asset_info, ensure_ascii=False)

    def get_all_actors(self) -> str:
        '''
        获取当前场景中可操作的Actor的信息
        Args:
            无需传递参数
        Returns:
            当前场景中可操作的Actor的信息的json字符串格式, 键是Actor在场景中的路径, 值是Actor的信息
            {
                "path": {
                    "name": "Actor名称",
                    "parent": "父Actor名称",
                    "transform.position": [x, y, z],
                    "transform.rotation": [w, x, y, z],
                    "transform.scale": 缩放因子,
                    "world_transform.position": [x, y, z],
                    "world_transform.rotation": [w, x, y, z],
                    "world_transform.scale": 缩放因子,
                    "type": "Actor类型",
                }
            }
        '''
        actors: List[Dict[Path, BaseActor]] = []
        self.scene_edit_bus.get_all_actors(actors)
        if len(actors) > 0 and actors[0] is not None:
            actors: Dict[Path, BaseActor] = actors[0]
            actors_dict = {}
            for path, actor in actors.items():
                actors_dict[path.string()] = actor.to_dict()
            return json.dumps(actors_dict)
        return json.dumps({})

    def get_actor_transform(self, actor_path: str) -> str:
        '''
        获取当前场景中Actor的变换信息
        Args:
            actor_path: Actor在场景中的路径
        Returns:
            获取Actor的变换的结果的json字符串格式, 键是Actor在场景中的路径, 值是Actor的变换信息
            {
                "path": {
                    "name": "Actor名称",
                    "parent": "父Actor名称",
                    "transform.position": [x, y, z],
                    "transform.rotation": [w, x, y, z],
                    "transform.scale": 缩放因子,
                    "world_transform.position": [x, y, z],
                    "world_transform.rotation": [w, x, y, z],
                    "world_transform.scale": 缩放因子,
                    "type": "Actor类型",
                }
            }
            获取失败则返回空字符串
        '''
        actors: List[Dict[Path, BaseActor]] = []
        self.scene_edit_bus.get_all_actors(actors)
        if len(actors) > 0 and actors[0] is not None:
            actors: Dict[Path, BaseActor] = actors[0]
            if Path(actor_path) in actors:
                return json.dumps({actor_path: actors[Path(actor_path)].to_dict()}, ensure_ascii=False)
        return json.dumps({}, ensure_ascii=False)

    async def set_actor_transform(self, actor_path: str, position: List[float], rotation: List[float], scale: float) -> str:
        '''
        设置当前场景中Actor的变换信息
        Args:
            actor_path: Actor在场景中的路径
            position: Actor的位置
            rotation: Actor的旋转
            scale: Actor的缩放
        Returns:
            设置Actor的变换的结果的json字符串格式
        '''
        # Convert lists to numpy arrays as required by Transform class
        position_array = np.array(position, dtype=np.float64)
        rotation_array = np.array(rotation, dtype=np.float64)
        transform = Transform(position=position_array, rotation=rotation_array, scale=scale)
        await self.scene_edit_bus.set_transform(Path(actor_path), transform, local=True, undo=True, source="mcp")
        return json.dumps({"success": True, "message": "成功设置Actor的变换"}, ensure_ascii=False)

    async def add_actor(self, actor_name: str, actor_path: str = "", parent_path: str = "/", actor_type: str = "asset") -> str:
        '''
        添加Actor
        Args:
            actor_name: Actor的名称（可以自定义，不要使用中文，最好都用小写，符合python变量命名规范）
            actor_path: 当 actor_type 为 asset 时必填，资产库中的路径（通过 get_asset_map/get_asset_info 获取，需去掉 .spawnable 后缀）；为 group 时忽略
            parent_path: Actor的父Actor在场景中的路径，默认为"/"
            actor_type: "asset" 表示资产实例，"group" 表示空组（仅需 actor_name）
        Returns:
            添加Actor的结果的json字符串格式
        '''
        if actor_type == "group":
            actor = GroupActor(name=actor_name)
        else:
            if not (actor_path or "").strip():
                return json.dumps({"success": False, "message": "添加资产类 Actor 时 actor_path 不能为空"}, ensure_ascii=False)
            actor = AssetActor(actor_name, actor_path)

        parent = Path(parent_path) if (parent_path and parent_path.strip()) else Path.root_path()
        try:
            await self.scene_edit_bus.add_actor(actor, parent, undo=True, source="mcp")
        except Exception as e:
            return json.dumps({"success": False, "message": f"添加Actor失败: {e}"}, ensure_ascii=False)
        return json.dumps({"success": True, "message": "成功添加Actor"}, ensure_ascii=False)

    async def delete_actor(self, actor_path: str) -> str:
        '''
        删除Actor
        Args:
            actor_path: Actor在场景中的路径
        Returns:
            删除Actor的结果的json字符串格式
        '''
        try:
            await self.scene_edit_bus.delete_actor(Path(actor_path), undo=True, source="mcp")
        except Exception as e:
            return json.dumps({"success": False, "message": f"删除Actor失败: {e}"}, ensure_ascii=False)
        return json.dumps({"success": True, "message": "成功删除Actor"}, ensure_ascii=False)

    def get_selection(self) -> str:
        '''
        获取当前场景中的选择
        Args:
            无需传递参数
        Returns:
            当前场景中的选择的actor的json字符串格式
        '''
        selection: List[List[Path]] = []
        self.scene_edit_bus.get_selection(selection)
        selection_dict = {}
        if len(selection) > 0 and selection[0] is not None:
            selection: List[Path] = selection[0]
            actors: List[Dict[Path, BaseActor]] = []
            self.scene_edit_bus.get_all_actors(actors)
            if len(actors) > 0 and actors[0] is not None:
                actors: Dict[Path, BaseActor] = actors[0]
            for path in selection:
                if path in actors:
                    selection_dict[path.string()] = actors[path].to_dict()
        return json.dumps(selection_dict, ensure_ascii=False)

    async def start_simulation(self) -> str:
        '''
        运行仿真
        Args:
            无需传递参数
        Returns:
            运行仿真的结果的json字符串格式
        '''
        try:
            await self.simulation_bus.start_simulation()
            return json.dumps({"success": True, "message": "成功启动仿真"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "message": f"启动仿真失败: {e}"}, ensure_ascii=False)

    async def stop_simulation(self) -> str:
        '''
        停止仿真
        Args:
            无需传递参数
        Returns:
            停止仿真的结果的json字符串格式
        '''
        try:
            await self.simulation_bus.stop_simulation()
            return json.dumps({"success": True, "message": "成功停止仿真"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "message": f"停止仿真失败: {e}"}, ensure_ascii=False)

    # async def get_camera_position(self) -> str:
    #     '''
    #     获取相机位置
    #     Args:
    #         无需传递参数
    #     Returns:
    #         相机位置的json字符串格式
    #     '''
    #     pass
      

    # async def get_camera_png(self) -> Image:
    #     '''
    #     获取相机截图
    #     Args:
    #         无需传递参数
    #     Returns:
    #         相机截图
    #     '''
    #    pass

    # async def get_scene_screenshot(self) -> Image:
    #     '''
    #     获取场景截图
    #     Args:
    #         无需传递参数
    #     Returns:
    #         场景截图
    #     '''
    #     pass

    # ==================== 撤销/重做类 API ====================

    async def undo(self) -> str:
        '''
        撤销上一步操作
        Args:
            无需传递参数
        Returns:
            撤销操作的结果的json字符串格式
        '''
        try:
            # 先检查是否可以撤销
            can_undo_result = []
            self.undo_bus.can_undo(can_undo_result)
            if len(can_undo_result) > 0 and not can_undo_result[0]:
                return json.dumps({"success": False, "message": "没有可撤销的操作"}, ensure_ascii=False)

            await self.undo_bus.undo()
            return json.dumps({"success": True, "message": "成功撤销上一步操作"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "message": f"撤销操作失败: {e}"}, ensure_ascii=False)

    async def redo(self) -> str:
        '''
        重做下一步操作
        Args:
            无需传递参数
        Returns:
            重做操作的结果的json字符串格式
        '''
        try:
            # 先检查是否可以重做
            can_redo_result = []
            self.undo_bus.can_redo(can_redo_result)
            if len(can_redo_result) > 0 and not can_redo_result[0]:
                return json.dumps({"success": False, "message": "没有可重做的操作"}, ensure_ascii=False)

            await self.undo_bus.redo()
            return json.dumps({"success": True, "message": "成功重做下一步操作"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "message": f"重做操作失败: {e}"}, ensure_ascii=False)

    def can_undo(self) -> str:
        '''
        检查是否可以撤销
        Args:
            无需传递参数
        Returns:
            是否可以撤销的json字符串格式
        '''
        can_undo_result = []
        self.undo_bus.can_undo(can_undo_result)
        result = can_undo_result[0] if len(can_undo_result) > 0 else False
        return json.dumps({"can_undo": result}, ensure_ascii=False)

    def can_redo(self) -> str:
        '''
        检查是否可以重做
        Args:
            无需传递参数
        Returns:
            是否可以重做的json字符串格式
        '''
        can_redo_result = []
        self.undo_bus.can_redo(can_redo_result)
        result = can_redo_result[0] if len(can_redo_result) > 0 else False
        return json.dumps({"can_redo": result}, ensure_ascii=False)

    # ==================== 选择操作类 API ====================

    async def set_selection(self, actor_paths: List[str]) -> str:
        '''
        设置当前选中的Actor
        Args:
            actor_paths: Actor路径列表，如 ["/Actor1", "/Actor2"]。传入空列表可清空选择。
        Returns:
            设置选择的结果的json字符串格式
        '''
        try:
            paths = [Path(p) for p in actor_paths]
            await self.scene_edit_bus.set_selection(paths, undo=True, source="mcp")
            return json.dumps({"success": True, "message": f"成功设置选择，共选中 {len(paths)} 个Actor"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "message": f"设置选择失败: {e}"}, ensure_ascii=False)

    async def clear_selection(self) -> str:
        '''
        清空当前选择
        Args:
            无需传递参数
        Returns:
            清空选择的结果的json字符串格式
        '''
        try:
            await self.scene_edit_bus.set_selection([], undo=True, source="mcp")
            return json.dumps({"success": True, "message": "成功清空选择"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "message": f"清空选择失败: {e}"}, ensure_ascii=False)

    # ==================== Actor 编辑类 API ====================

    async def rename_actor(self, actor_path: str, new_name: str) -> str:
        '''
        重命名Actor
        Args:
            actor_path: Actor在场景中的路径
            new_name: 新的名称
        Returns:
            重命名操作的结果的json字符串格式
        '''
        try:
            # 获取 Actor 对象
            actors: List[Dict[Path, BaseActor]] = []
            self.scene_edit_bus.get_all_actors(actors)
            if len(actors) == 0 or actors[0] is None:
                return json.dumps({"success": False, "message": "无法获取场景Actor列表"}, ensure_ascii=False)

            actors_dict: Dict[Path, BaseActor] = actors[0]
            path_obj = Path(actor_path)
            if path_obj not in actors_dict:
                return json.dumps({"success": False, "message": f"找不到Actor: {actor_path}"}, ensure_ascii=False)

            actor = actors_dict[path_obj]
            old_name = actor.name
            await self.scene_edit_bus.rename_actor(actor, new_name, undo=True, source="mcp")
            return json.dumps({"success": True, "message": f"成功将Actor从 '{old_name}' 重命名为 '{new_name}'"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "message": f"重命名Actor失败: {e}"}, ensure_ascii=False)

    async def reparent_actor(self, actor_path: str, new_parent_path: str, row: int = -1) -> str:
        '''
        改变Actor的父级（移动Actor到另一个父级下）
        若 new_parent_path 对应的 Group 不存在，会先按路径逐级创建。
        Args:
            actor_path: Actor在场景中的路径
            new_parent_path: 新父级Actor的路径，使用 "/" 表示根节点
            row: 插入位置，-1表示添加到末尾
        Returns:
            改变父级操作的结果的json字符串格式
        '''
        try:
            parent_path = Path((new_parent_path or "").strip() or "/")
            # 若目标父路径不是根且不存在，则按级创建缺失的 Group
            if parent_path != Path.root_path():
                actors_out: List[Dict[Path, BaseActor]] = []
                self.scene_edit_bus.get_all_actors(actors_out)
                actors = actors_out[0] if actors_out and actors_out[0] is not None else {}
                segments = [s for s in parent_path.string().strip("/").split("/") if s]
                current = Path.root_path()
                for seg in segments:
                    current = current.append(seg)
                    if current not in actors:
                        await self.scene_edit_bus.add_actor(
                            GroupActor(seg), current.parent(), undo=True, source="mcp"
                        )
                        actors_out = []
                        self.scene_edit_bus.get_all_actors(actors_out)
                        actors = actors_out[0] if actors_out and actors_out[0] is not None else {}
            await self.scene_edit_bus.reparent_actor(Path(actor_path), Path(new_parent_path), row, undo=True, source="mcp")
            return json.dumps({"success": True, "message": f"成功将Actor移动到 '{new_parent_path}' 下"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "message": f"改变Actor父级失败: {e}"}, ensure_ascii=False)


    # ==================== 仿真状态类 API ====================

    def get_simulation_state(self) -> str:
        '''
        获取当前仿真状态
        Args:
            无需传递参数
        Returns:
            仿真状态的json字符串格式，状态包括：Stopped(停止)、Launching(启动中)、Running(运行中)、Failed(失败)
        '''
        try:
            state_result = []
            self.simulation_bus.get_simulation_state(state_result)
            if len(state_result) > 0 and state_result[0] is not None:
                state: SimulationState = state_result[0]
                state_names = {
                    SimulationState.Stopped: "Stopped",
                    SimulationState.Launching: "Launching",
                    SimulationState.Running: "Running",
                    SimulationState.Failed: "Failed"
                }
                state_name = state_names.get(state, "Unknown")
                return json.dumps({"state": state_name, "running": state == SimulationState.Running}, ensure_ascii=False)
            return json.dumps({"state": "Unknown", "running": False}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "message": f"获取仿真状态失败: {e}"}, ensure_ascii=False)

    # ==================== 场景编辑高级 API ====================

    async def get_actor_asset_aabb(self, actor_path: str) -> str:
        '''
        获取Actor的轴对齐包围盒(AABB)
        Args:
            actor_path: Actor在场景中的路径
        Returns:
            包围盒信息的json字符串格式，包含min、max、center点
        '''
        try:
            output = []
            await self.scene_edit_notification_bus.get_actor_asset_aabb(Path(actor_path), output)
            if len(output) > 0:
                aabb = output
                return json.dumps({
                    "success": True,
                    "actor_path": actor_path,
                    "aabb": aabb,
                    "message": f"成功获取Actor的包围盒"
                }, ensure_ascii=False)
            return json.dumps({"success": False, "message": "无法获取包围盒信息"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "message": f"获取Actor包围盒失败: {e}"}, ensure_ascii=False)

    # ==================== 批量操作类 API ====================

    async def delete_actors(self, actor_paths: List[str]) -> str:
        '''
        批量删除多个Actor
        Args:
            actor_paths: Actor路径列表，如 ["/Actor1", "/Actor2"]
        Returns:
            批量删除操作的结果的json字符串格式
        '''
        try:
            success_count = 0
            failed_paths = []
            for path in actor_paths:
                try:
                    await self.scene_edit_bus.delete_actor(Path(path), undo=True, source="mcp")
                    success_count += 1
                except Exception as e:
                    failed_paths.append({"path": path, "error": str(e)})

            result = {
                "success": success_count > 0,
                "message": f"成功删除 {success_count}/{len(actor_paths)} 个Actor",
                "success_count": success_count,
                "total_count": len(actor_paths),
                "failed": failed_paths
            }
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "message": f"批量删除Actor失败: {e}"}, ensure_ascii=False)

    async def set_actors_transform(self, actor_paths: List[str], position: List[float], rotation: List[float], scale: float) -> str:
        '''
        批量设置多个Actor的变换
        Args:
            actor_paths: Actor路径列表
            position: 位置 [x, y, z]
            rotation: 旋转 [w, x, y, z] (四元数)
            scale: 缩放因子
        Returns:
            批量设置变换的结果的json字符串格式
        '''
        try:
            position_array = np.array(position, dtype=np.float64)
            rotation_array = np.array(rotation, dtype=np.float64)
            transform = Transform(position=position_array, rotation=rotation_array, scale=scale)

            success_count = 0
            failed_paths = []
            for path in actor_paths:
                try:
                    await self.scene_edit_bus.set_transform(Path(path), transform, local=True, undo=True, source="mcp")
                    success_count += 1
                except Exception as e:
                    failed_paths.append({"path": path, "error": str(e)})

            result = {
                "success": success_count > 0,
                "message": f"成功设置 {success_count}/{len(actor_paths)} 个Actor的变换",
                "success_count": success_count,
                "total_count": len(actor_paths),
                "failed": failed_paths
            }
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "message": f"批量设置Actor变换失败: {e}"}, ensure_ascii=False)

    # ==================== 相机控制类 API ====================

    async def set_viewport_camera(self, camera_index: int) -> str:
        '''
        设置视口相机
        Args:
            camera_index: 相机索引
        Returns:
            操作结果的json字符串格式
        '''
        try:
            await self.camera_bus.set_viewport_camera(camera_index)
            return json.dumps({"success": True, "message": f"成功切换到相机 {camera_index}"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "message": f"设置视口相机失败: {e}"}, ensure_ascii=False)

    # ==================== 系统信息类 API ====================

    def get_engine_info(self) -> str:
        '''
        获取引擎基础信息
        Args:
            无需传递参数
        Returns:
            引擎基础信息的json字符串格式，包括：
            - engine_version: 引擎版本号
            - app_version: OrcaLab应用版本号
            - keyboard_shortcuts: 快捷键信息列表
        '''
        def _get_keyboard_shortcuts() -> List[Dict[str, str]]:
            shortcuts = [
                {"action": "新建布局", "shortcut": "Ctrl+N", "scope": "全局"},
                {"action": "打开布局", "shortcut": "Ctrl+O", "scope": "全局"},
                {"action": "保存布局", "shortcut": "Ctrl+S", "scope": "全局"},
                {"action": "另存为", "shortcut": "Ctrl+Shift+S", "scope": "全局"},
                {"action": "撤销", "shortcut": "Ctrl+Z", "scope": "全局"},
                {"action": "重做", "shortcut": "Ctrl+Shift+Z", "scope": "全局"},
                {"action": "平移操纵器", "shortcut": "1", "scope": "全局"},
                {"action": "旋转操纵器", "shortcut": "2", "scope": "全局"},
                {"action": "缩放操纵器", "shortcut": "3", "scope": "全局"},
                {"action": "按住 Shift 可切换为世界坐标", "shortcut": "Shift + 1/2/3", "scope": "全局"},
                {"action": "聚焦到选择物体", "shortcut": "Z", "scope": "全局"},
                {"action": "相机向前移动", "shortcut": "按住鼠标右键 + W", "scope": "视窗"},
                {"action": "相机向后移动", "shortcut": "按住鼠标右键 + S", "scope": "视窗"},
                {"action": "相机向左移动", "shortcut": "按住鼠标右键 + A", "scope": "视窗"},
                {"action": "相机向右移动", "shortcut": "按住鼠标右键 + D", "scope": "视窗"},
                {"action": "相机向上移动", "shortcut": "按住鼠标右键 + E", "scope": "视窗"},
                {"action": "相机向下移动", "shortcut": "按住鼠标右键 + Q", "scope": "视窗"},
                {"action": "转动相机", "shortcut": "按住鼠标右键 + 移动鼠标", "scope": "视窗"},
                {"action": "绕一点转动相机", "shortcut": "Alt + 按住鼠标左键 + 移动鼠标", "scope": "视窗"},
                {"action": "切换选择的物体控制状态（仿真/用户控制）", "shortcut": "F3", "scope": "全局"},
                {"action": "显示/隐藏物理碰撞和 Joint", "shortcut": "F4", "scope": "全局"},
                {"action": "删除选择物体", "shortcut": "Delete", "scope": "全局"},
            ]
            return shortcuts

        try:
            # 安全地获取配置信息
            config = getattr(self.config_service, 'config', {})
            engine_version = config.get("orcalab", {}).get("version", "unknown")
            app_version = self.config_service.app_version()
            
            info = {
                "engine_version": engine_version,
                "app_version": app_version,
                "keyboard_shortcuts": _get_keyboard_shortcuts(),
            }
            return json.dumps(info, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "message": f"获取引擎信息失败: {e}"}, ensure_ascii=False)

    def add_tools(self):
        # 资产元数据类
        self.mcp.tool(self.get_asset_map)
        self.mcp.tool(self.get_asset_info)

        # Actor 查询类
        self.mcp.tool(self.get_all_actors)
        self.mcp.tool(self.get_actor_transform)
        self.mcp.tool(self.get_selection)

        # Actor 编辑类
        self.mcp.tool(self.set_actor_transform)
        self.mcp.tool(self.add_actor)
        self.mcp.tool(self.delete_actor)
        self.mcp.tool(self.rename_actor)
        self.mcp.tool(self.reparent_actor)
        
        # 选择操作类
        self.mcp.tool(self.set_selection)
        self.mcp.tool(self.clear_selection)

        # 撤销/重做类
        self.mcp.tool(self.undo)
        self.mcp.tool(self.redo)
        self.mcp.tool(self.can_undo)
        self.mcp.tool(self.can_redo)

        # 仿真控制类
        self.mcp.tool(self.start_simulation)
        self.mcp.tool(self.stop_simulation)
        self.mcp.tool(self.get_simulation_state)

        # 批量操作类
        self.mcp.tool(self.delete_actors)
        self.mcp.tool(self.set_actors_transform)

        # 视觉类
        # self.mcp.tool(self.get_camera_position)
        # self.mcp.tool(self.get_camera_png)
        # self.mcp.tool(self.get_scene_screenshot)

        # 场景编辑高级
        self.mcp.tool(self.get_actor_asset_aabb)

        # 相机控制
        self.mcp.tool(self.set_viewport_camera)

        # 系统信息类
        self.mcp.tool(self.get_engine_info)
        
    async def run(self):
        await self.mcp.run_async(transport="http", port=self.port)

    def stop(self):
        if self._task and not self._task.done():
            self._task.cancel()