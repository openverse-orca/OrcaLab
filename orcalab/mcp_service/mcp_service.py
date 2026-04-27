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
from orcalab.scene_layout.scene_layout_helper import SceneLayoutHelper

class OrcaLabMCPServer:
    def __init__(self, port):
        self.port = port
        self.config_service = ConfigService()
        self.metadata_service_bus = MetadataServiceRequestBus()
        self.scene_edit_bus = SceneEditRequestBus()
        self.application_bus = ApplicationRequestBus()
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

    @staticmethod
    def _quat_to_euler_list(quat) -> List[float]:
        """四元数 (w,x,y,z) 转欧拉角 [roll, pitch, yaw] 角度制，顺序 xyz。"""
        if hasattr(quat, "tolist"):
            quat = quat.tolist()
        w, x, y, z = float(quat[0]), float(quat[1]), float(quat[2]), float(quat[3])
        r = Rotation.from_quat([x, y, z, w])
        return r.as_euler("xyz", degrees=True).tolist()

    @staticmethod
    def _euler_to_quat_list(euler: List[float]) -> List[float]:
        """欧拉角 [roll, pitch, yaw] 角度制 xyz 顺序 转四元数 (w,x,y,z)。"""
        r = Rotation.from_euler("xyz", euler, degrees=True)
        x, y, z, w = r.as_quat()
        return [float(w), float(x), float(y), float(z)]

    @staticmethod
    def _mcp_layout_dir() -> str:
        return os.path.join(os.path.expanduser("~"), ".orcalab", "mcp_layout")

    @staticmethod
    def _normalize_layout_name(layout_name: str) -> str:
        # 仅允许文件名，避免路径穿越；强制 .json 后缀
        base = os.path.basename((layout_name or "").strip())
        if not base:
            raise ValueError("layout_name 不能为空")
        if not base.lower().endswith(".json"):
            base += ".json"
        return base

    @staticmethod
    def _actor_to_layout_dict(local_scene, actor: AssetActor | GroupActor) -> dict:
        def _to_list(v):
            return v.tolist() if hasattr(v, "tolist") else v

        def _compact_array(arr):
            return "[" + ",".join(str(x) for x in arr) + "]"

        actor_path = local_scene.get_actor_path(actor)
        path_str = actor_path._p if actor_path is not None else "/"
        data = {
            "name": actor.name,
            "path": path_str,
            "transform": {
                "position": _compact_array(_to_list(actor.transform.position)),
                "rotation": _compact_array(_to_list(actor.transform.rotation)),
                "scale": actor.transform.scale,
            },
            "is_visible": actor.is_visible,
            "is_parent_visible": actor.is_parent_visible,
            "is_locked": actor.is_locked,
            "is_parent_locked": actor.is_parent_locked,
        }

        if actor.name == "root":
            data = {"version": "1.0", **data}

        if isinstance(actor, AssetActor):
            data["type"] = "AssetActor"
            data["asset_path"] = getattr(actor, "_asset_path", getattr(actor, "asset_path", ""))
            data["modified_properties"] = SceneLayoutHelper.collect_modified_properties(actor)
        elif isinstance(actor, GroupActor):
            data["type"] = "GroupActor"
            data["children"] = [
                OrcaLabMCPServer._actor_to_layout_dict(local_scene, child) for child in actor.children
            ]

        return data

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

    @staticmethod
    def _find_first_package_match_by_asset_name(
        metadata_rows: list, asset_name: str
    ) -> tuple[dict | None, str | None]:
        needle = asset_name.strip().lower()
        if not needle:
            return None, None
        for item in metadata_rows:
            if not isinstance(item, dict):
                continue
            name_l = (item.get("name") or "").lower()
            path_l = (item.get("assetPath") or "").lower()
            if needle not in name_l and needle not in path_l:
                continue
            pkg_id = item.get("parentPackageId") or item.get("id")
            if pkg_id:
                return item, str(pkg_id)
        return None, None

    async def subscribe_asset_package_by_asset_name(self, asset_name: str) -> str:
        '''
        根据资产名称在元数据中搜索，并订阅第一个匹配项所属的资产包。
        Args:
            asset_name: 资产显示名或路径片段（不区分大小写，匹配 name 或 assetPath 子串）。
        Returns:
            操作结果的 json 字符串，含 success、所选资产包 id、匹配条目及订阅接口返回。
        '''
        try:
            name = asset_name.strip()
            if not name:
                return json.dumps(
                    {"success": False, "message": "asset_name 不能为空"},
                    ensure_ascii=False,
                )

            meta_out: list[str] = []
            await self.http_service_bus.get_all_metadata(meta_out)
            if not meta_out:
                return json.dumps(
                    {
                        "success": False,
                        "message": "无法获取远程元数据（请确认已登录 DataLink 且网络正常）",
                    },
                    ensure_ascii=False,
                )

            metadata_list = json.loads(meta_out[0])
            if not isinstance(metadata_list, list):
                return json.dumps(
                    {"success": False, "message": "元数据格式异常：非列表"},
                    ensure_ascii=False,
                )

            matched, package_id = self._find_first_package_match_by_asset_name(metadata_list, name)
            if not matched or not package_id:
                return json.dumps(
                    {
                        "success": False,
                        "message": f"未找到名称或路径包含「{name}」的资产",
                    },
                    ensure_ascii=False,
                )

            sub_out: list[str] = []
            await self.http_service_bus.post_asset_subscribe(package_id, sub_out)
            if not sub_out:
                return json.dumps(
                    {
                        "success": False,
                        "package_id": package_id,
                        "matched_asset": {
                            "id": matched.get("id"),
                            "name": matched.get("name"),
                            "assetPath": matched.get("assetPath"),
                            "parentPackageId": matched.get("parentPackageId"),
                        },
                        "message": "订阅请求未执行（请确认已登录 DataLink 且在线）",
                    },
                    ensure_ascii=False,
                )
            sub_result = json.loads(sub_out[0])

            merged = {
                "success": bool(sub_result.get("success")),
                "package_id": package_id,
                "matched_asset": {
                    "id": matched.get("id"),
                    "name": matched.get("name"),
                    "assetPath": matched.get("assetPath"),
                    "parentPackageId": matched.get("parentPackageId"),
                },
                "subscribe": sub_result,
            }
            if merged["success"]:
                merged["message"] = f"已请求订阅资产包 {package_id}（匹配资产: {matched.get('name', '')}）"
            else:
                merged["message"] = sub_result.get("body") or sub_result.get("message") or "订阅请求失败"
            return json.dumps(merged, ensure_ascii=False)
        except json.JSONDecodeError as e:
            return json.dumps(
                {"success": False, "message": f"解析元数据或订阅结果失败: {e}"},
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps(
                {"success": False, "message": f"订阅资产包失败: {e}"},
                ensure_ascii=False,
            )

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
                    "transform.rotation": [roll, pitch, yaw],
                    "transform.scale": 缩放因子,
                    "world_transform.position": [x, y, z],
                    "world_transform.rotation": [roll, pitch, yaw],
                    "world_transform.scale": 缩放因子,
                    "type": "Actor类型",
                }
            }
            rotation 均为欧拉角 [roll, pitch, yaw]，单位度，顺序 xyz
        '''
        actors: List[Dict[Path, BaseActor]] = []
        self.scene_edit_bus.get_all_actors(actors)
        if len(actors) > 0 and actors[0] is not None:
            actors: Dict[Path, BaseActor] = actors[0]
            actors_dict = {}
            for path, actor in actors.items():
                ad = actor.to_dict()
                ad["transform.rotation"] = self._quat_to_euler_list(actor.transform.rotation)
                ad["world_transform.rotation"] = self._quat_to_euler_list(actor.world_transform.rotation)
                actors_dict[path.string()] = ad
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
                    "transform.rotation": [roll, pitch, yaw],
                    "transform.scale": 缩放因子,
                    "world_transform.position": [x, y, z],
                    "world_transform.rotation": [roll, pitch, yaw],
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
                actor = actors[Path(actor_path)]
                ad = actor.to_dict()
                ad["transform.rotation"] = self._quat_to_euler_list(actor.transform.rotation)
                ad["world_transform.rotation"] = self._quat_to_euler_list(actor.world_transform.rotation)
                return json.dumps({actor_path: ad}, ensure_ascii=False)
        return json.dumps({}, ensure_ascii=False)

    async def set_actor_transform(self, actor_path: str, position: List[float], rotation: List[float], scale: float) -> str:
        '''
        设置当前场景中Actor的变换信息
        Args:
            actor_path: Actor在场景中的路径
            position: Actor的位置
            rotation: Actor的欧拉角旋转 [roll, pitch, yaw]，单位度，顺序 xyz
            scale: Actor的缩放
        Returns:
            设置Actor的变换的结果的json字符串格式
        '''
        quat = self._euler_to_quat_list(rotation)
        position_array = np.array(position, dtype=np.float64)
        rotation_array = np.array(quat, dtype=np.float64)
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
                    actor = actors[path]
                    ad = actor.to_dict()
                    ad["transform.rotation"] = self._quat_to_euler_list(actor.transform.rotation)
                    ad["world_transform.rotation"] = self._quat_to_euler_list(actor.world_transform.rotation)
                    selection_dict[path.string()] = ad
        return json.dumps(selection_dict, ensure_ascii=False)

    async def start_simulation(self, program_name: str = "external") -> str:
        '''
        运行仿真（默认启动 无仿真程序（手动启动））
        Args:
            program_name: 配置文件里 [[external_programs.programs]] 的 name 字段；默认 external；
                传 external 表示「无仿真程序」
        Returns:
            运行仿真的结果的json字符串格式
        '''
        try:
            await self.simulation_bus.start_simulation(program_name)
            return json.dumps(
                {"success": True, "message": f"成功启动仿真（program_name={program_name}）"},
                ensure_ascii=False,
            )
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
      
    async def get_viewport_camera_info(self, index: int = 0) -> str:
        '''
        获取当前视口相机的信息，包括Transform, RGB图，深度图，法线图，对象语义图
        Args:
            index: 当前获取的视口图片信息索引，与图片命名有关
        Returns:
            当前视口相机的信息的json字符串格式
            {
                "success": True,
                "message": "成功获取当前视口相机的信息",
                "transform": {
                    "position": [x, y, z],
                    "rotation": [roll, pitch, yaw],
                },
                "color_path": "color_path",
                "depth_path": "depth_path",
                "normal_path": "normal_path",
                "object_color_path": "object_color_path",
            }
        '''
        try:
            output = []
            transform : Transform = None
            await self.camera_bus.get_viewport_camera_transform(output)
            if len(output) > 0 and output[0] is not None:
                transform = output[0]
            if transform is not None:
                position = transform.position.tolist()
                rotation = self._quat_to_euler_list(transform.rotation)
                actor, output = [], []
                await self.application_bus.add_item_to_scene_with_transform("AgentCamera", "prefabs/agentcamera", parent_path=Path.root_path(), transform=transform, output=actor)
                if len(actor) > 0 and actor[0] is not None:
                    actor = actor[0]
                
                viewport_image_path = os.path.join(os.path.expanduser("~"), ".orcalab", "viewport_image")
                color_path = os.path.join(viewport_image_path, "color", f"AgentCamera_color_{index}.png")
                depth_path = os.path.join(viewport_image_path, "depth", f"AgentCamera_depth_{index}.npy")
                # normal_path = os.path.join(viewport_image_path, "normal", f"AgentCamera_normal_{index}.png")
                object_color_path = os.path.join(viewport_image_path, "object_color", f"AgentCamera_object_color_{index}.png")
                await self.scene_edit_notification_bus.get_camera_data_png("AgentCamera", viewport_image_path, index, output)
                await asyncio.sleep(0.2)
                await self.scene_edit_bus.delete_actor(actor, undo=True, source="mcp")
                if len(output) > 0 and output[0] is not None:
                    camera_data_png = output[0]
                    color_path = color_path
                    depth_path = depth_path
                    # normal_path = normal_path
                    object_color_path = object_color_path
                return json.dumps({"success": True, 
                                    "message": "成功获取当前视口相机的信息", 
                                    "transform": {
                                        "position": position,
                                        "rotation": rotation,
                                    },
                                    "color_path": color_path,
                                    "depth_path": depth_path,
                                    # "normal_path": normal_path,
                                    "object_color_path": object_color_path,
                                    }, ensure_ascii=False)
            else:
                return json.dumps({"success": False, "message": "获取当前视口相机信息失败"}, ensure_ascii=False)
        except Exception as e:
            print(f"获取当前视口相机信息失败: {e}")
            return json.dumps({"success": False, "message": f"获取当前视口相机信息失败: {e}"}, ensure_ascii=False)
   
    async def get_viewport_png(self, index: int) -> Image:
        '''
        获取相机截图
        Args:
            index: 当前获取的视口图片信息索引，与图片命名有关
        Returns:
            相机截图的Image对象，MCP客户端可直接渲染显示
        '''
        output = []
        transform: Transform = None
        await self.camera_bus.get_viewport_camera_transform(output)
        if len(output) > 0 and output[0] is not None:
            transform = output[0]
        if transform is None:
            raise RuntimeError("获取视口相机变换失败")

        actor = []
        await self.application_bus.add_item_to_scene_with_transform("mujococamera1080", "prefabs/mujococamera1080", parent_path=Path.root_path(), transform=transform, output=actor)
        if len(actor) > 0 and actor[0] is not None:
            actor = actor[0]

        viewport_image_path = os.path.join(os.path.expanduser("~"), ".orcalab")
        color_path = os.path.join(viewport_image_path, f"viewport_color_{index}.png")
        await self.scene_edit_notification_bus.get_camera_png("mujococamera1080", viewport_image_path, f"viewport_color_{index}.png")
        await asyncio.sleep(0.2)
        await self.scene_edit_bus.delete_actor(actor, undo=True, source="mcp")

        return Image(path=color_path)


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


    async def get_view_png_from_transform(
        self,
        position: List[float],
        rotation: List[float],
        scale: float = 1.0,
        index: int = 0,
    ) -> Image:
        '''
        在指定世界位姿临时放置渲染相机，输出一张视角 PNG 后自动删除（不保留场景中的相机 Actor）。
        Args:
            position: 相机位置 [x, y, z]
            rotation: 欧拉角 [roll, pitch, yaw]，单位度，顺序 xyz
            scale: 均匀缩放，默认 1.0
            index: 输出文件名后缀 view_transform_{index}.png，避免并发覆盖
        Returns:
            截图 Image，文件位于 ~/.orcalab/view_transform_{index}.png
        '''
        if len(position) != 3:
            raise ValueError("position 须为长度 3 的列表 [x, y, z]")
        if len(rotation) != 3:
            raise ValueError("rotation 须为长度 3 的列表 [roll, pitch, yaw]（度，xyz 顺序）")

        quat_list = self._euler_to_quat_list([float(x) for x in rotation])
        transform = Transform(
            position=np.array([float(x) for x in position], dtype=np.float64),
            rotation=np.array(quat_list, dtype=np.float64),
            scale=float(scale),
        )
        camera_type = "mujococamera1080"
        prefab_path = "prefabs/mujococamera1080"

        actor_out: List = []
        await self.application_bus.add_item_to_scene_with_transform(
            camera_type,
            prefab_path,
            parent_path=Path.root_path(),
            transform=transform,
            output=actor_out,
        )
        if len(actor_out) == 0 or actor_out[0] is None:
            raise RuntimeError("临时相机创建失败")

        actor = actor_out[0]
        viewport_image_path = os.path.join(os.path.expanduser("~"), ".orcalab")
        os.makedirs(viewport_image_path, exist_ok=True)
        png_name = f"view_transform_{index}.png"
        color_path = os.path.join(viewport_image_path, png_name)
        await self.scene_edit_notification_bus.get_camera_png(
            camera_type, viewport_image_path, png_name
        )
        await asyncio.sleep(0.2)
        await self.scene_edit_bus.delete_actor(actor, undo=True, source="mcp")

        return Image(path=color_path)

    async def get_viewport_transform(self) -> str:
        '''
        获取当前视口相机的变换
        Args:
            无需传递参数
        Returns:
            当前视口相机的变换的json字符串格式
            {
                "success": True,
                "message": "成功获取当前视口相机变换",
                "transform": {
                    "position": [x, y, z],
                    "rotation": [roll, pitch, yaw],
                    "scale": scale,
                }
            }
            rotation 为欧拉角 [roll, pitch, yaw]，单位度
        '''
        try:
            output = []
            await self.camera_bus.get_viewport_camera_transform(output)
            if len(output) > 0 and output[0] is not None:
                transform : Transform = output[0]
                return json.dumps({"success": True, "message": "成功获取当前视口相机变换", "transform": {
                    "position": transform.position.tolist(),
                    "rotation": self._quat_to_euler_list(transform.rotation),
                    "scale": transform.scale,
                }}, ensure_ascii=False)
            else:
                return json.dumps({"success": False, "message": "获取当前视口相机变换失败"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "message": f"获取当前视口相机变换失败: {e}"}, ensure_ascii=False)
    # async def get_camera_png(self) -> Image:
    #     '''
    #     获取相机截图
    #     Args:
    #         无需传递参数
    #     Returns:
    #         相机截图
    #     '''
    #    pass


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
            rotation: 旋转 [roll, pitch, yaw] (欧拉角)
            scale: 缩放因子
        Returns:
            批量设置变换的结果的json字符串格式
        '''
        try:
            quat = self._euler_to_quat_list(rotation)
            position_array = np.array(position, dtype=np.float64)
            rotation_array = np.array(quat, dtype=np.float64)
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

    # ==================== 布局类 API ====================
    def save_layout(self, layout_path: str) -> str:
        '''
        保存布局
        Args:
            layout_path: 布局名或布局文件路径（可不带 .json）。
                - 仅名称时，保存到 ~/.orcalab/mcp_layout/
                - 传路径时，保存到指定目录
        Returns:
            保存布局的结果的json字符串格式
        '''
        try:
            raw = (layout_path or "").strip()
            if not raw:
                return json.dumps({"success": False, "message": "layout_path 不能为空"}, ensure_ascii=False)

            is_path = (
                (os.sep in raw)
                or (os.altsep is not None and os.altsep in raw)
                or raw.startswith("~")
                or os.path.isabs(raw)
            )

            if is_path:
                target = os.path.abspath(os.path.expanduser(raw))
                file_name = self._normalize_layout_name(os.path.basename(target))
                save_dir = os.path.dirname(target) or self._mcp_layout_dir()
            else:
                file_name = self._normalize_layout_name(raw)
                save_dir = self._mcp_layout_dir()

            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, file_name)

            local_scene_out = []
            self.application_bus.get_local_scene(local_scene_out)
            if not local_scene_out or local_scene_out[0] is None:
                return json.dumps({"success": False, "message": "获取本地场景失败"}, ensure_ascii=False)

            local_scene = local_scene_out[0]
            root = local_scene.root_actor
            scene_layout_dict = self._actor_to_layout_dict(local_scene, root)
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(scene_layout_dict, f, ensure_ascii=False, indent=4)

            return json.dumps(
                {
                    "success": True,
                    "message": f"布局已保存: {save_path}",
                    "layout_path": save_path,
                },
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps({"success": False, "message": f"保存布局失败: {e}"}, ensure_ascii=False)

    async def load_layout(self, layout_path: str) -> str:
        '''
        加载布局
        Args:
            layout_path: 布局文件路径（支持绝对路径、相对路径、~）
        Returns:
            加载布局的结果的json字符串格式
        '''
        try:
            path_raw = (layout_path or "").strip()
            if not path_raw:
                return json.dumps(
                    {"success": False, "message": "layout_path 不能为空"},
                    ensure_ascii=False,
                )
            load_path = os.path.abspath(os.path.expanduser(path_raw))
            if not os.path.exists(load_path):
                return json.dumps(
                    {"success": False, "message": f"布局文件不存在: {load_path}"},
                    ensure_ascii=False,
                )

            local_scene_out = []
            self.application_bus.get_local_scene(local_scene_out)
            if not local_scene_out or local_scene_out[0] is None:
                return json.dumps({"success": False, "message": "获取本地场景失败"}, ensure_ascii=False)

            helper = SceneLayoutHelper(local_scene_out[0])
            ok = await helper.load_scene_layout(None, load_path)
            if not ok:
                return json.dumps(
                    {"success": False, "message": f"加载布局失败: {load_path}"},
                    ensure_ascii=False,
                )

            return json.dumps(
                {
                    "success": True,
                    "message": f"布局已加载: {load_path}",
                    "layout_path": load_path,
                },
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps({"success": False, "message": f"加载布局失败: {e}"}, ensure_ascii=False)

    def add_tools(self):
        # 资产元数据类
        self.mcp.tool(self.get_asset_map)
        self.mcp.tool(self.get_asset_info)
        self.mcp.tool(self.subscribe_asset_package_by_asset_name)

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
        self.mcp.tool(self.get_viewport_camera_info)
        self.mcp.tool(self.get_viewport_png)
        self.mcp.tool(self.get_viewport_transform)
        self.mcp.tool(self.set_viewport_camera)
        self.mcp.tool(self.get_view_png_from_transform)

        # 场景编辑高级
        self.mcp.tool(self.get_actor_asset_aabb)

        # 系统信息类
        self.mcp.tool(self.get_engine_info)

        # 布局类
        self.mcp.tool(self.save_layout)
        self.mcp.tool(self.load_layout)

    async def run(self):
        await self.mcp.run_async(transport="http", port=self.port)

    def stop(self):
        if self._task and not self._task.done():
            self._task.cancel()