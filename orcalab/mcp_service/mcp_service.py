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

from orcalab.selection_data import SelectionData
from orcalab.simulation.simulation_bus import SimulationRequestBus, SimulationState
from orcalab.ui.camera.camera_brief import CameraBrief
from orcalab.ui.camera.camera_bus import CameraRequestBus
from orcalab.application_util import get_remote_scene
from orcalab.application_bus import ApplicationRequestBus
from orcalab.scene_edit_bus import SceneEditRequestBus
from orcalab.undo_service.undo_service_bus import UndoRequestBus
from orcalab.actor_property import ActorEntities, ActorPropertyGroup, ActorPropertyKey, ActorPropertyType
from orcalab.asset_service_bus import AssetServiceRequestBus
from orcalab.http_service.http_bus import HttpServiceRequestBus
from orcalab.project_util import get_cache_folder
from orcalab.ui.panel_bus import PanelRequestBus
from orcalab.copilot.service import CopilotService
from orcalab.scene_layout.scene_layout_helper import SceneLayoutHelper
from orcalab.entity_path import EntityPath, NameWithIndex

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
            data = {"version": "2.0", **data}

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

    def get_asset_map(self, project_name: str=None, category: str=None) -> str:
        '''
        获取所有已订阅资产的元数据信息
        Args:
            可选择传入project_name[资产所在项目名称]和category[资产分类]参数，用于筛选资产。
        Returns:
            筛选后的所有已订阅资产的元数据信息的json字符串格式
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
            
            if project_name is not None:
                asset_path = info.get("assetPath") or ""
                if project_name.lower() not in asset_path.lower():
                    continue

            if category is not None:
                category_path = info.get("categoryPath") or ""
                if category.lower() not in category_path.lower():
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
        if not asset_path or not asset_path.strip():
            return json.dumps({"code": 400, "message": "asset_path 不能为空"}, ensure_ascii=False)
        output = []
        self.metadata_service_bus.get_asset_info(asset_path, output)
        if not output or output[0] is None:
            return json.dumps({"code": 404, "message": f"资产路径不存在: {asset_path}"}, ensure_ascii=False)
        return json.dumps(output[0], ensure_ascii=False)

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

    async def unsubscribe_asset_package_by_asset_name(self, asset_name: str) -> str:
        '''
        根据资产名称在元数据中搜索，并取消订阅第一个匹配项所属的资产包。
        Args:
            asset_name: 资产显示名或路径片段（不区分大小写，匹配 name 或 assetPath 子串）。
        Returns:
            操作结果的 json 字符串，含 success、所选资产包 id、匹配条目及取消订阅接口返回。
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

            unsub_out: list[str] = []
            await self.http_service_bus.post_asset_unsubscribe(package_id, unsub_out)
            if not unsub_out:
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
                        "message": "取消订阅请求未执行（请确认已登录 DataLink 且在线）",
                    },
                    ensure_ascii=False,
                )
            unsub_result = json.loads(unsub_out[0])

            merged = {
                "success": bool(unsub_result.get("success")),
                "package_id": package_id,
                "matched_asset": {
                    "id": matched.get("id"),
                    "name": matched.get("name"),
                    "assetPath": matched.get("assetPath"),
                    "parentPackageId": matched.get("parentPackageId"),
                },
                "unsubscribe": unsub_result,
            }
            if merged["success"]:
                merged["message"] = f"已取消订阅资产包 {package_id}（匹配资产: {matched.get('name', '')}）"
            else:
                merged["message"] = unsub_result.get("body") or unsub_result.get("message") or "取消订阅请求失败"
            return json.dumps(merged, ensure_ascii=False)
        except json.JSONDecodeError as e:
            return json.dumps(
                {"success": False, "message": f"解析元数据或取消订阅结果失败: {e}"},
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps(
                {"success": False, "message": f"取消订阅资产包失败: {e}"},
                ensure_ascii=False,
            )

    async def get_subscription_status_by_asset_name(self, asset_name: str) -> str:
        '''
        根据资产名称在元数据中搜索，并查询第一个匹配项所属资产包的订阅状态。
        Args:
            asset_name: 资产显示名或路径片段（不区分大小写，匹配 name 或 assetPath 子串）。
        Returns:
            操作结果的 json 字符串，含 success、所选资产包 id、匹配条目及订阅状态。
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

            status_out: list[str] = []
            await self.http_service_bus.get_asset_subscription_status(package_id, status_out)
            if not status_out:
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
                        "message": "查询订阅状态请求未执行（请确认已登录 DataLink 且在线）",
                    },
                    ensure_ascii=False,
                )
            status_result = json.loads(status_out[0])

            merged = {
                "success": bool(status_result.get("success")),
                "package_id": package_id,
                "matched_asset": {
                    "id": matched.get("id"),
                    "name": matched.get("name"),
                    "assetPath": matched.get("assetPath"),
                    "parentPackageId": matched.get("parentPackageId"),
                },
                "subscription_status": status_result,
            }
            if merged["success"]:
                merged["message"] = f"成功获取资产包订阅状态（匹配资产: {matched.get('name', '')}）"
            else:
                merged["message"] = status_result.get("body") or status_result.get("message") or "查询订阅状态失败"
            return json.dumps(merged, ensure_ascii=False)
        except json.JSONDecodeError as e:
            return json.dumps(
                {"success": False, "message": f"解析元数据或订阅状态结果失败: {e}"},
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps(
                {"success": False, "message": f"查询资产包订阅状态失败: {e}"},
                ensure_ascii=False,
            )

    async def get_my_metadata(self) -> str:
        '''
        获取我的资产列表（包含自己上传的资产和订阅的资产包）
        对应后端接口 GET /api/mymeta/
        Returns:
            资产列表的 json 字符串格式
            {
                "code": 200,
                "data": [
                    {
                        "id": "4c5e6a29-8b3f-4d72-a0c5-9e1b8d7f2a34",
                        "name": "Gryphon_Beast",
                        "category": "scene",
                        "type": "asset_package",
                        "parentPackageId": null,
                        "description": "",
                        "categoryPath": "/scene",
                        "size": 37082768,
                        "imgUrl": "",
                        "version": "2025.11.01",
                        "status": "draft",
                        "author": "linliwan",
                        "assetPath": null,
                        "projectName": "default_project",
                        "isSubscribed": false,
                        "isMyCreation": true
                    }
                ]
            }
        '''
        try:
            output: list[str] = []
            await self.http_service_bus.get_my_metadata(output)
            if not output:
                return json.dumps(
                    {"code": 500, "message": "无法获取我的资产列表（请确认已登录 DataLink 且网络正常）"},
                    ensure_ascii=False,
                )
            return output[0]
        except Exception as e:
            return json.dumps(
                {"code": 500, "message": f"获取我的资产列表失败: {e}"},
                ensure_ascii=False,
            )

    async def get_asset_detail(self, asset_id: str) -> str:
        '''
        根据资产ID获取单个资产详情（含预览图列表、元数据信息等）
        对应后端接口 GET /api/asset/<id>/
        Args:
            asset_id: 资产的ID
        Returns:
            资产详情的json字符串格式
            {
                "code": 200,
                "data": {
                    "id": "...",
                    "name": "...",
                    "category": "...",
                    "type": "asset",
                    "parentPackageId": "...",
                    "description": "...",
                    "categoryPath": "...",
                    "pictures": [...],
                    "isCanEdit": true,
                    ...
                }
            }
        '''
        try:
            output: list[str] = []
            await self.http_service_bus.get_asset_detail(asset_id, output)
            if not output:
                return json.dumps(
                    {"code": 500, "message": "无法获取资产详情（请确认已登录 DataLink 且网络正常）"},
                    ensure_ascii=False,
                )
            return output[0]
        except Exception as e:
            return json.dumps(
                {"code": 500, "message": f"获取资产详情失败: {e}"},
                ensure_ascii=False,
            )

    async def search_assets(self, search_type: str, query: str = "", image_path: str = "") -> str:
        '''
        资产全文检索（支持文字和图片搜索）
        对应后端接口 POST /api/search/
        Args:
            search_type: 搜索类型，"text" 表示文字搜索，"image" 表示图片搜索
            query: 搜索关键词，如"桌子"（search_type 为 text 时必填）
            image_path: 图片文件路径（search_type 为 image 时必填）
        Returns:
            搜索结果的json字符串格式
            {
                "code": 200,
                "data": {
                    "status": "success",
                    "searchType": "text",
                    "query": "kitchen",
                    "totalResults": 10,
                    "results": [...]
                }
            }
        '''
        try:
            search_data = {
                "search_type": search_type,
            }
            if search_type == "text":
                if not query:
                    return json.dumps(
                        {"code": 400, "message": "文字搜索时需要提供 query"},
                        ensure_ascii=False,
                    )
                search_data["query"] = query
            elif search_type == "image":
                if not image_path:
                    return json.dumps(
                        {"code": 400, "message": "图片搜索时需要提供 image_path"},
                        ensure_ascii=False,
                    )
                search_data["image_path"] = image_path
            else:
                return json.dumps(
                    {"code": 400, "message": f"不支持的搜索类型: {search_type}，仅支持 text 或 image"},
                    ensure_ascii=False,
                )
            output: list[str] = []
            await self.http_service_bus.search_assets(search_data, output)
            if not output:
                return json.dumps(
                    {"code": 500, "message": "搜索失败（请确认已登录 DataLink 且网络正常）"},
                    ensure_ascii=False,
                )
            return output[0]
        except Exception as e:
            return json.dumps(
                {"code": 500, "message": f"搜索失败: {e}"},
                ensure_ascii=False,
            )

    async def get_asset_json_by_name(self, asset_name: str) -> str:
        '''
        通过资产名称匹配获取资产对应的metadata JSON 文件内容
        优先通过当前场景中的 Actor 名称查找资产路径，再获取资产 ID 和 JSON 文件。
        如果场景中未找到，则回退到名称前缀匹配方式。

        Args:
            asset_name: 资产名称，如 "黄色越野车"（场景中 Actor 的名称）
        Returns:
            JSON 文件内容的 json 字符串格式，或错误信息。
        '''
        try:
            name = asset_name.strip()
            if not name:
                return json.dumps(
                    {"success": False, "message": "asset_name 不能为空"},
                    ensure_ascii=False,
                    indent=2,
                )

            # 先获取资产映射（无论哪种方式都需要）
            output = []
            self.metadata_service_bus.get_asset_map(output)
            asset_map = output[0] if output else {}

            if not asset_map:
                return json.dumps(
                    {"success": False, "message": "本地资产映射为空，请先同步资产"},
                    ensure_ascii=False,
                    indent=2,
                )

            asset_id = None
            matched_info = {}

            # === 方式一：通过当前场景中的 Actor 查找 ===
            actors: List[Dict[Path, BaseActor]] = []
            self.scene_edit_bus.get_all_actors(actors)
            if actors and actors[0] is not None:
                scene_actors: Dict[Path, BaseActor] = actors[0]
                for _, actor in scene_actors.items():
                    if isinstance(actor, AssetActor) and actor.name == name:
                        actor_asset_path = (actor.asset_path or "").lower()
                        # 在资产映射中查找匹配的 asset_path
                        for map_key, meta in asset_map.items():
                            map_path = map_key.lower()
                            if map_path == actor_asset_path or map_path == actor_asset_path.removesuffix(".spawnable"):
                                asset_id = meta.get("id", "")
                                matched_info = {
                                    "id": asset_id,
                                    "name": meta.get("name"),
                                    "assetPath": map_key,
                                    "version": meta.get("version"),
                                }
                                break
                        if asset_id:
                            break

            # === 方式二：回退到名称前缀匹配 ===
            if not asset_id:
                import re
                base_name = re.sub(r'_\d+$', '', name, count=1)
                needle = base_name.strip().lower()

                candidates = []
                for _, asset_metadata in asset_map.items():
                    asset_name_val = (asset_metadata.get("name") or "").lower()
                    if asset_name_val.startswith(needle):
                        candidates.append(asset_metadata)

                if not candidates:
                    return json.dumps(
                        {
                            "success": False,
                            "message": f"未找到名称以「{base_name}」开头的资产（共扫描 {len(asset_map)} 条记录）",
                        },
                        ensure_ascii=False,
                        indent=2,
                    )

                def _parse_version(v: str):
                    try:
                        parts = v.split(".")
                        return tuple(int(p) for p in parts)
                    except (ValueError, TypeError):
                        return (0, 0, 0)

                candidates.sort(
                    key=lambda m: _parse_version(m.get("version", "")),
                    reverse=True,
                )
                best = candidates[0]
                asset_id = best.get("id", "")
                if not asset_id:
                    return json.dumps(
                        {
                            "success": False,
                            "message": f"匹配到资产「{best.get('name')}」但缺少 id 字段",
                            "matched_asset": best,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                matched_info = {
                    "id": asset_id,
                    "name": best.get("name"),
                    "assetPath": best.get("assetPath"),
                    "version": best.get("version"),
                }

            # 从缓存目录中查找 JSON 文件
            cache_folder = get_cache_folder()
            json_path = cache_folder / f"{asset_id}.json"
            if not json_path.exists():
                return json.dumps(
                    {
                        "success": False,
                        "message": f"JSON 文件不存在: {json_path}",
                        "matched_asset": matched_info,
                    },
                    ensure_ascii=False,
                    indent=2,
                )

            with open(json_path, "r", encoding="utf-8") as f:
                json_content = json.load(f)

            return json.dumps(
                {
                    "success": True,
                    "matched_asset": matched_info,
                    "json_file": str(json_path),
                    "data": json_content,
                },
                ensure_ascii=False,
                indent=2,
            )
        except Exception as e:
            return json.dumps(
                {"success": False, "message": f"获取资产 JSON 失败: {e}"},
                ensure_ascii=False,
                indent=2,
            )

    async def post_generate_task(self, type: str, text: str = "", time_period: str = "", image_path: str = "") -> str:
        '''
        创建生成资产任务（支持文本和图片）
        对应后端接口 POST /api/generate/
        Args:
            type: 生成类型，"text" 表示文本生成，"image" 表示图片生成
            text: 文本描述，如"键盘"（type 为 text 时必填）
            time_period: 时间周期，如"2026-04-01"
            image_path: 图片文件路径（type 为 image 时必填）
        Returns:
            生成任务的json字符串格式
            {
                "success": true,
                "body": {
                    "status": "queued",
                    "taskId": "...",
                    "queuePosition": 3,
                    "message": "任务已加入队列，当前队列位置：3"
                }
            }
        '''
        try:
            task_data = {
                "type": type,
                "timePeriod": time_period,
            }
            if type == "text":
                task_data["text"] = text
            elif type == "image":
                if not image_path:
                    return json.dumps(
                        {"success": False, "message": "图片生成时需要提供 image_path"},
                        ensure_ascii=False,
                    )
                task_data["image_path"] = image_path
            output: list[str] = []
            await self.http_service_bus.post_generate_task(task_data, output)
            if not output:
                return json.dumps(
                    {"success": False, "message": "无法创建生成任务（请确认已登录 DataLink 且网络正常）"},
                    ensure_ascii=False,
                )
            return output[0]
        except Exception as e:
            return json.dumps(
                {"success": False, "message": f"创建生成任务失败: {e}"},
                ensure_ascii=False,
            )

    async def get_generate_task_status(self, task_id: str) -> str:
        '''
        查询生成任务状态和队列位置
        对应后端接口 GET /api/generate/status/<task_id>/
        Args:
            task_id: 任务ID
        Returns:
            任务状态的json字符串格式
            {
                "success": true,
                "body": {
                    "taskId": "...",
                    "status": "pending",
                    "queuePosition": 2,
                    "result": null,
                    "error": null
                }
            }
        '''
        try:
            output: list[str] = []
            await self.http_service_bus.get_generate_task_status(task_id, output)
            if not output:
                return json.dumps(
                    {"success": False, "message": "无法查询生成任务状态（请确认已登录 DataLink 且网络正常）"},
                    ensure_ascii=False,
                )
            return output[0]
        except Exception as e:
            return json.dumps(
                {"success": False, "message": f"查询生成任务状态失败: {e}"},
                ensure_ascii=False,
            )

    async def get_user_generate_tasks(self) -> str:
        '''
        查询用户最近的生成任务（用于页面刷新后恢复）
        对应后端接口 GET /api/generate/user_tasks/
        Args:
            无需传递参数
        Returns:
            用户最近生成任务的json字符串格式
            {
                "success": true,
                "body": {
                    "tasks": [
                        {
                            "taskId": "...",
                            "status": "pending",
                            "queuePosition": 2
                        }
                    ],
                    "count": 1
                }
            }
        '''
        try:
            output: list[str] = []
            await self.http_service_bus.get_user_generate_tasks(output)
            if not output:
                return json.dumps(
                    {"success": False, "message": "无法查询用户生成任务（请确认已登录 DataLink 且网络正常）"},
                    ensure_ascii=False,
                )
            return output[0]
        except Exception as e:
            return json.dumps(
                {"success": False, "message": f"查询用户生成任务失败: {e}"},
                ensure_ascii=False,
            )

    async def post_upload_generate_usdz(
        self,
        file_url: str,
        preview_url: str = "",
        name: str = "",
        project_name: str = "",
        version: str = "",
        time_period: str = "",
        file_type: str = "generate_usdz",
        upload_type: str = "private",
        roles: str = '["admin"]',
        separate_mesh: str = "false",
        generate_lod: str = "false",
        smooth_mesh: str = "false",
        smooth_ratio: str = "2",
        generate_global_config: str = "false",
        use_hub_cli: str = "true",
        size: str = "1",
        usdz_split_mesh: str = "false",
        merge_threshold: str = "0.01",
        merge_iterations: str = "1",
        max_split_mesh_number: str = "100",
    ) -> str:
        '''
        根据 file_url 上传生成完成的 USDZ 资产，异步转为 AssetZip/PAK
        对应后端接口 POST /api/upload/generate_usdz/
        Args:
            file_url: 生成任务完成后返回的文件URL（必填）
            preview_url: 预览图URL
            name: 资产名称
            project_name: 项目名称
            version: 版本号
            time_period: 时间周期
            file_type: 文件类型，默认 "generate_usdz"
            upload_type: 上传类型，默认 "private"
            roles: 可见角色列表，默认 '["admin"]'
            separate_mesh: 是否分离网格，默认 "false"
            generate_lod: 是否生成LOD，默认 "false"
            smooth_mesh: 是否平滑网格，默认 "false"
            smooth_ratio: 平滑比率，默认 "2"
            generate_global_config: 是否生成全局配置，默认 "false"
            use_hub_cli: 是否使用 hub cli，默认 "true"
            size: 大小，默认 "1"
            usdz_split_mesh: 是否拆分USDZ网格，默认 "false"
            merge_threshold: 合并阈值，默认 "0.01"
            merge_iterations: 合并迭代次数，默认 "1"
            max_split_mesh_number: 最大拆分网格数，默认 "100"
        Returns:
            上传结果的json字符串格式
            {
                "success": true,
                "body": {
                    "status": "success",
                    "message": "USDZ文件上传成功，开始处理流程",
                    "taskChainId": "...",
                    "fileType": "generate_usdz",
                    ...
                }
            }
        '''
        try:
            task_data = {
                "file_url": file_url,
                "file_type": file_type,
                "upload_type": upload_type,
                "roles": roles,
                "project_name": project_name or None,
                "name": name or None,
                "version": version or None,
                "timePeriod": time_period or None,
                "preview_url": preview_url or None,
                "separate_mesh": separate_mesh,
                "generate_lod": generate_lod,
                "smooth_mesh": smooth_mesh,
                "smooth_ratio": smooth_ratio,
                "generate_global_config": generate_global_config,
                "use_hub_cli": use_hub_cli,
                "size": size,
                "usdz_split_mesh": usdz_split_mesh,
                "merge_threshold": merge_threshold,
                "merge_iterations": merge_iterations,
                "max_split_mesh_number": max_split_mesh_number,
            }
            output: list[str] = []
            await self.http_service_bus.post_upload_generate_usdz(task_data, output)
            if not output:
                return json.dumps(
                    {"success": False, "message": "无法上传生成资产（请确认已登录 DataLink 且网络正常）"},
                    ensure_ascii=False,
                )
            return output[0]
        except Exception as e:
            return json.dumps(
                {"success": False, "message": f"上传生成资产失败: {e}"},
                ensure_ascii=False,
            )

    async def post_cancel_asset_zip(self, task_id: str) -> str:
        '''
        取消资产压缩包上传（OSS删除）
        对应后端接口 POST /api/cancel_asset_zip/<task_id>/
        Args:
            task_id: 任务ID
        Returns:
            取消结果的json字符串格式
            {
                "code": 200,
                "data": {
                    "status": "success",
                    "message": "资产上传已取消，相关文件已删除"
                }
            }
        '''
        try:
            output: list[str] = []
            await self.http_service_bus.post_cancel_asset_zip(task_id, output)
            if not output:
                return json.dumps(
                    {"success": False, "message": "无法取消资产上传（请确认已登录 DataLink 且网络正常）"},
                    ensure_ascii=False,
                )
            return output[0]
        except Exception as e:
            return json.dumps(
                {"success": False, "message": f"取消资产上传失败: {e}"},
                ensure_ascii=False,
            )

    async def post_check_asset_version(self, time_period: str, project_name: str, name: str, author: str = "") -> str:
        '''
        检测资产版本并返回下一个版本号
        对应后端接口 POST /api/check-asset-version/
        Args:
            time_period: 时间段开始日期（格式：YYYY-MM-DD）
            project_name: 项目名
            name: 资产名，即 zip 压缩包的名字（如 remy.zip 则 name=remy）
            author: 作者（可选，默认使用当前用户）
        Returns:
            检测结果的json字符串格式
            {
                "isDuplicate": false,
                "version": "2026.01.20",
                "message": "未检测到全量资产包，使用初始版本号（全量发布）",
                "revisionKind": "full",
                "baseVersionId": null
            }
            版本号规则：
            - 如果没有重复：使用时间段对应的初始版本号（如 2025.09.01）
            - 如果检测到重复：自动递增小版本号（如 2025.09.02, 2025.09.03...）
        '''
        try:
            version_data = {
                "timePeriod": time_period,
                "project_name": project_name,
                "name": name,
            }
            if author:
                version_data["author"] = author

            output: list[str] = []
            await self.http_service_bus.post_check_asset_version(version_data, output)
            if not output:
                return json.dumps(
                    {"success": False, "message": "无法检测资产版本（请确认已登录 DataLink 且网络正常）"},
                    ensure_ascii=False,
                )
            return output[0]
        except Exception as e:
            return json.dumps(
                {"success": False, "message": f"检测资产版本失败: {e}"},
                ensure_ascii=False,
            )

    async def post_upload_asset_zip(
        self,
        local_path: str,
        name: str,
        version: str,
        project_name: str,
        time_period: str,
        upload_type: str = "private",
        revision_kind: str = "full",
    ) -> str:
        '''
        上传资产压缩包并转换为PAK文件
        对应后端接口 POST /api/upload/asset_zip/
        Args:
            local_path: 资产压缩包路径（如 smb://192.168.110.53/share/RemyLevel_ysb.zip）
            name: 资产名，即 zip 压缩包的名字（如 RemyLevel_ysb.zip 则 name=RemyLevel_ysb）
            version: 版本号（如 2026.04.01）
            project_name: 项目名
            time_period: 时间段开始日期（格式：YYYY-MM-DD）
            upload_type: 上传类型，默认 "private"
            revision_kind: 发布类型，默认 "full"
        Returns:
            上传结果的json字符串格式
            {
                "code": 200,
                "data": {
                    "status": "success",
                    "taskId": "...",
                    "uniqueId": "...",
                    "message": "任务已提交，Worker正在处理"
                }
            }
        '''
        try:
            upload_data = {
                "local_path": local_path,
                "name": name,
                "version": version,
                "project_name": project_name,
                "upload_type": upload_type,
                "timePeriod": time_period,
                "revision_kind": revision_kind,
            }
            output: list[str] = []
            await self.http_service_bus.post_upload_asset_zip(upload_data, output)
            if not output:
                return json.dumps(
                    {"success": False, "message": "无法上传资产压缩包（请确认已登录 DataLink 且网络正常）"},
                    ensure_ascii=False,
                )
            return output[0]
        except Exception as e:
            return json.dumps(
                {"success": False, "message": f"上传资产压缩包失败: {e}"},
                ensure_ascii=False,
            )

    async def post_upload_usdz(
        self,
        local_path: str,
        name: str,
        version: str,
        project_name: str,
        time_period: str,
        upload_type: str = "private",
        revision_kind: str = "full",
        roles: str = '["admin"]',
        size: str = "1",
        usdz_split_mesh: str = "false",
        merge_threshold: str = "0.01",
        merge_iterations: str = "1",
        max_split_mesh_number: str = "100",
        separate_mesh: str = "false",
        generate_lod: str = "false",
        smooth_mesh: str = "false",
        smooth_ratio: str = "2",
        generate_global_config: str = "false",
        use_hub_cli: str = "true",
    ) -> str:
        '''
        上传 USDZ（仅管理员；公网 usdz_file 或私网 local_path 指向 .zip），异步处理 usdz_to_xml_zip → xml_zip_to_asset_zip → asset_zip_to_pak
        对应后端接口 POST /api/upload/usdz/
        Args:
            local_path: 资产压缩包路径（如 smb://192.168.110.53/share/bar_stool_usdz.zip）
            name: 资产名
            version: 版本号（如 2026.04.01）
            project_name: 项目名
            time_period: 时间段开始日期（格式：YYYY-MM-DD）
            upload_type: 上传类型，默认 "private"
            revision_kind: 发布类型，默认 "full"
            roles: 可见角色列表，默认 '["admin"]'
            size: 大小，默认 "1"
            usdz_split_mesh: 是否拆分USDZ网格，默认 "false"
            merge_threshold: 合并阈值，默认 "0.01"
            merge_iterations: 合并迭代次数，默认 "1"
            max_split_mesh_number: 最大拆分网格数，默认 "100"
            separate_mesh: 是否分离网格，默认 "false"
            generate_lod: 是否生成LOD，默认 "false"
            smooth_mesh: 是否平滑网格，默认 "false"
            smooth_ratio: 平滑比率，默认 "2"
            generate_global_config: 是否生成全局配置，默认 "false"
            use_hub_cli: 是否使用 hub cli，默认 "true"
        Returns:
            上传结果的json字符串格式
            {
                "code": 200,
                "data": {
                    "status": "success",
                    "taskChainId": "...",
                    "fileType": "usdz",
                    ...
                }
            }
        '''
        try:
            upload_data = {
                "local_path": local_path,
                "name": name,
                "version": version,
                "project_name": project_name,
                "upload_type": upload_type,
                "timePeriod": time_period,
                "revision_kind": revision_kind,
                "roles": roles,
                "size": size,
                "usdz_split_mesh": usdz_split_mesh,
                "merge_threshold": merge_threshold,
                "merge_iterations": merge_iterations,
                "max_split_mesh_number": max_split_mesh_number,
                "separate_mesh": separate_mesh,
                "generate_lod": generate_lod,
                "smooth_mesh": smooth_mesh,
                "smooth_ratio": smooth_ratio,
                "generate_global_config": generate_global_config,
                "use_hub_cli": use_hub_cli,
                "file_type": "usdz",
            }
            output: list[str] = []
            await self.http_service_bus.post_upload_usdz(upload_data, output)
            if not output:
                return json.dumps(
                    {"success": False, "message": "无法上传USDZ（请确认已登录 DataLink 且网络正常）"},
                    ensure_ascii=False,
                )
            return output[0]
        except Exception as e:
            return json.dumps(
                {"success": False, "message": f"上传USDZ失败: {e}"},
                ensure_ascii=False,
            )

    async def post_upload_xml(
        self,
        local_path: str,
        name: str,
        version: str,
        project_name: str,
        time_period: str,
        upload_type: str = "private",
        revision_kind: str = "full",
        roles: str = '["admin"]',
        separate_mesh: str = "false",
        generate_lod: str = "false",
        smooth_mesh: str = "false",
        smooth_ratio: str = "2",
        generate_global_config: str = "false",
        use_hub_cli: str = "true",
    ) -> str:
        '''
        上传 XML（仅管理员；公网 xml_file 或私网 local_path 指向 .zip），异步处理 xml_zip_to_asset_zip → asset_zip_to_pak
        对应后端接口 POST /api/upload/xml/
        Args:
            local_path: 资产压缩包路径（如 smb://192.168.110.53/share/realman_xml.zip）
            name: 资产名
            version: 版本号（如 2026.01.20）
            project_name: 项目名
            time_period: 时间段开始日期（格式：YYYY-MM-DD）
            upload_type: 上传类型，默认 "private"
            revision_kind: 发布类型，默认 "full"
            roles: 可见角色列表，默认 '["admin"]'
            separate_mesh: 是否分离网格，默认 "false"
            generate_lod: 是否生成LOD，默认 "false"
            smooth_mesh: 是否平滑网格，默认 "false"
            smooth_ratio: 平滑比率，默认 "2"
            generate_global_config: 是否生成全局配置，默认 "false"
            use_hub_cli: 是否使用 hub cli，默认 "true"
        Returns:
            上传结果的json字符串格式
            {
                "code": 200,
                "data": {
                    "status": "success",
                    "taskChainId": "...",
                    "fileType": "xml",
                    ...
                }
            }
        '''
        try:
            upload_data = {
                "local_path": local_path,
                "name": name,
                "version": version,
                "project_name": project_name,
                "upload_type": upload_type,
                "timePeriod": time_period,
                "revision_kind": revision_kind,
                "roles": roles,
                "separate_mesh": separate_mesh,
                "generate_lod": generate_lod,
                "smooth_mesh": smooth_mesh,
                "smooth_ratio": smooth_ratio,
                "generate_global_config": generate_global_config,
                "use_hub_cli": use_hub_cli,
                "file_type": "xml",
            }
            output: list[str] = []
            await self.http_service_bus.post_upload_xml(upload_data, output)
            if not output:
                return json.dumps(
                    {"success": False, "message": "无法上传XML（请确认已登录 DataLink 且网络正常）"},
                    ensure_ascii=False,
                )
            return output[0]
        except Exception as e:
            return json.dumps(
                {"success": False, "message": f"上传XML失败: {e}"},
                ensure_ascii=False,
            )

    async def get_task_chain_progress(self, task_chain_id: str) -> str:
        '''
        查询任务链整体进度
        对应后端接口 GET /api/task_chain_progress/<task_chain_id>/
        Args:
            task_chain_id: 任务链ID
        Returns:
            任务链进度的json字符串格式
            {
                "success": true,
                "body": {
                    "progress": 50,
                    "message": "...",
                    "steps": [...],
                    "currentStep": "...",
                    ...
                }
            }
        '''
        try:
            output: list[str] = []
            await self.http_service_bus.get_task_chain_progress(task_chain_id, output)
            if not output:
                return json.dumps(
                    {"success": False, "message": "无法查询任务链进度（请确认已登录 DataLink 且网络正常）"},
                    ensure_ascii=False,
                )
            return output[0]
        except Exception as e:
            return json.dumps(
                {"success": False, "message": f"查询任务链进度失败: {e}"},
                ensure_ascii=False,
            )

    async def post_save_asset_draft(self, task_id: str, name: str = "", description: str = "", category_path: str = "") -> str:
        '''
        保存资产草稿，用于后续编辑和发布
        对应后端接口 POST /api/save_asset_draft/<task_id>/
        Args:
            task_id: 任务ID
            name: 资产名称
            description: 资产描述（可选）
            category_path: 分类路径（可选）
        Returns:
            保存结果的json字符串格式
            {
                "success": true,
                "body": {
                    "status": "success",
                    "message": "资产草稿已保存",
                    "assetId": "..."
                }
            }
        '''
        try:
            draft_data = {
                "name": name or None,
                "description": description or None,
                "category_path": category_path or None,
            }
            output: list[str] = []
            await self.http_service_bus.post_save_asset_draft(task_id, draft_data, output)
            if not output:
                return json.dumps(
                    {"success": False, "message": "无法保存资产草稿（请确认已登录 DataLink 且网络正常）"},
                    ensure_ascii=False,
                )
            return output[0]
        except Exception as e:
            return json.dumps(
                {"success": False, "message": f"保存资产草稿失败: {e}"},
                ensure_ascii=False,
            )

    async def delete_asset(self, asset_id: str) -> str:
        '''
        删除指定资产（支持级联删除）
        权限说明：只能删除自己的资产（author 为当前用户）
        对应后端接口 DELETE /api/delete/<id>/
        Args:
            asset_id: 资产ID
        Returns:
            删除结果的json字符串格式
            {
                "success": true,
                "body": {
                    "status": "success",
                    "message": "资产包 xxx（ID：...）及其下 N 个子资产已删除",
                    "assetId": "...",
                    "assetName": "...",
                    "deletedCount": 12,
                    "childAssetsCount": 11
                }
            }
        '''
        try:
            output: list[str] = []
            await self.http_service_bus.delete_asset(asset_id, output)
            if not output:
                return json.dumps(
                    {"success": False, "message": "无法删除资产（请确认已登录 DataLink 且网络正常）"},
                    ensure_ascii=False,
                )
            return output[0]
        except Exception as e:
            return json.dumps(
                {"success": False, "message": f"删除资产失败: {e}"},
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
    async def set_selection_and_active_actor(self, actor_paths: List[str], active_actor: str = "") -> str:
        '''
        设置当前选中的Actor列表以及激活Actor
        Args:
            actor_paths: Actor路径列表，如 ["/Actor1", "/Actor2"]。传入空列表可清空选择。
            active_actor: 激活的Actor路径（在属性面板中显示的Actor），为空时自动取第一个选中Actor
        Returns:
            设置选择与激活Actor的结果的json字符串格式
        '''
        try:
            paths = [Path(p) for p in actor_paths]
            active = Path(active_actor) if active_actor else (paths[0] if paths else None)
            await self.scene_edit_bus.set_selection(SelectionData(paths, active), undo=True, source="mcp")
            return json.dumps({"success": True, "message": f"成功设置选择，共选中 {len(paths)} 个Actor"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "message": f"设置选择与激活Actor失败: {e}"}, ensure_ascii=False)

    async def clear_selection(self) -> str:
        '''
        清空当前选择
        Args:
            无需传递参数
        Returns:
            清空选择的结果的json字符串格式
        '''
        try:
            await self.scene_edit_bus.set_selection(SelectionData(), undo=True, source="mcp")
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

    async def duplicate_actors(self, actor_paths: List[str]) -> str:
        '''
        复制Actor
        Args:
            actor_paths: 要复制的Actor路径列表
        Returns:
            复制操作的结果的json字符串格式
        '''
        try:
            paths = [Path(p) for p in actor_paths]
            await self.scene_edit_bus.duplicate_actors(paths, undo=True, source="mcp")
            return json.dumps({"success": True, "message": f"成功复制 {len(paths)} 个Actor"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "message": f"复制Actor失败: {e}"}, ensure_ascii=False)
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
                {"action": "复制", "shortcut": "Ctrl+D", "scope": "全局"},
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

    @staticmethod
    def _parse_entity_path(entity_path_str: str) -> EntityPath:
        if not entity_path_str or not entity_path_str.strip():
            return EntityPath()
        segments = []
        for seg in entity_path_str.strip("/").split("/"):
            seg = seg.strip()
            if not seg:
                continue
            if ":" in seg:
                name, index_str = seg.rsplit(":", 1)
                try:
                    index = int(index_str)
                except ValueError:
                    index = 0
            else:
                name = seg
                index = 0
            segments.append(NameWithIndex(name, index))
        return EntityPath(segments)

    @staticmethod
    def _entity_info_to_dict(entity_info) -> dict:
        return {
            "entity_id": entity_info.entity_id,
            "name": entity_info.name,
            "entity_path": entity_info.entity_path.string(),
            "children": [
                OrcaLabMCPServer._entity_info_to_dict(child)
                for child in entity_info.children
            ],
        }

    @staticmethod
    def _find_entity_id_in_tree(entity_info, target_entity_path_str: str) -> int:
        if entity_info.entity_path.string() == target_entity_path_str:
            return entity_info.entity_id
        for child in entity_info.children:
            result = OrcaLabMCPServer._find_entity_id_in_tree(child, target_entity_path_str)
            if result != 0:
                return result
        return 0

    @staticmethod
    def _split_combined_path(asset_path: str) -> tuple[Path, str | None]:
        parts = asset_path.strip("/").split("/", 1)
        actor_path = Path(f"/{parts[0]}")
        entity_name = parts[1] if len(parts) > 1 else None
        return actor_path, entity_name

    @staticmethod
    def _find_entity_by_name_in_tree(entity_info, target_name: str) -> tuple[int, str] | None:
        if entity_info.name == target_name:
            return entity_info.entity_id, entity_info.entity_path.string()
        for child in entity_info.children:
            result = OrcaLabMCPServer._find_entity_by_name_in_tree(child, target_name)
            if result is not None:
                return result
        return None

    async def get_actor_properties(self, asset_path: str) -> str:
        '''
        获取Actor或指定Entity的所有属性组及其属性值
        Args:
            asset_path: Actor在场景中的路径，如 "/actor_name"（Actor级）或 "/actor_name/Entity名"（Entity级）
        Returns:
            包含所有属性组和属性的json字符串格式，每个属性包含名称、显示名、类型、值、基础值、只读状态等信息
        '''
        try:
            actor_path, entity_name = self._split_combined_path(asset_path)
            remote_scene = get_remote_scene()

            if entity_name is None:
                # Actor 级别
                groups = await remote_scene.get_actor_property_groups(actor_path)
                result = []
                for group in groups:
                    group_dict = {
                        "name": group.name,
                        "hint": group.hint,
                        "entity_path": group.entity_path.string(),
                        "component_type_id": group.component_type_id,
                        "component_type_index": group.component_type_index,
                        "properties": [
                            {
                                "name": prop.name(),
                                "display_name": prop.display_name(),
                                "type": prop.value_type().name,
                                "value": prop.value(),
                                "base_value": prop.base_value(),
                                "read_only": prop.is_read_only(),
                                "editor_hint": prop.editor_hint(),
                                "enum_values": prop.enum_values(),
                            }
                            for prop in group.properties
                        ]
                    }
                    result.append(group_dict)
                return json.dumps(result, ensure_ascii=False)
            else:
                # Entity 级别 — 按 entity 名在层级树中查找
                infos = await remote_scene._service.get_entity_hierarchy_batch([actor_path])
                if not infos or infos[0] is None:
                    return json.dumps(
                        {"error": f"未找到Actor '{actor_path}' 的Entity层级结构"},
                        ensure_ascii=False,
                    )

                found = self._find_entity_by_name_in_tree(infos[0], entity_name)
                if found is None:
                    return json.dumps(
                        {"error": f"未找到名为 '{entity_name}' 的Entity"},
                        ensure_ascii=False,
                    )

                entity_id, _ = found
                actor_entities = ActorEntities(actor_path, [entity_id])
                groups_list = await remote_scene.get_entity_property_groups(actor_entities)
                if not groups_list or not groups_list[0]:
                    return json.dumps([], ensure_ascii=False)

                groups = groups_list[0]
                result = []
                for group in groups:
                    group_dict = {
                        "name": group.name,
                        "hint": group.hint,
                        "entity_path": group.entity_path.string(),
                        "component_type_id": group.component_type_id,
                        "component_type_index": group.component_type_index,
                        "properties": [
                            {
                                "name": prop.name(),
                                "display_name": prop.display_name(),
                                "type": prop.value_type().name,
                                "value": prop.value(),
                                "base_value": prop.base_value(),
                                "read_only": prop.is_read_only(),
                                "editor_hint": prop.editor_hint(),
                                "enum_values": prop.enum_values(),
                            }
                            for prop in group.properties
                        ]
                    }
                    result.append(group_dict)
                return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    async def set_actor_properties(self, asset_path: str, property_name: str, property_value: object) -> str:
        '''
        设置Actor或指定Entity的属性值
        Args:
            asset_path: Actor在场景中的路径，如 "/actor_name"（Actor级）或 "/actor_name/Entity名"（Entity级）
            property_name: 属性名称
            property_value: 属性值（根据属性类型传入对应类型：bool/整数/浮点数/字符串）
        Returns:
            操作结果的json字符串格式
        '''
        try:
            actor_path, entity_name = self._split_combined_path(asset_path)
            remote_scene = get_remote_scene()
            keys = []
            values = []

            if entity_name is None:
                # Actor 级别
                groups = await remote_scene.get_actor_property_groups(actor_path)
                for group in groups:
                    for prop in group.properties:
                        if prop.name() == property_name:
                            key = ActorPropertyKey(
                                actor_path=actor_path,
                                entity_id=0,
                                entity_path=group.entity_path,
                                component_type_id=group.component_type_id,
                                component_type_index=group.component_type_index,
                                property_name=prop.name(),
                                property_type=prop.value_type(),
                            )
                            keys.append(key)
                            values.append(property_value)
            else:
                # Entity 级别 — 按 entity 名在层级树中查找
                infos = await remote_scene._service.get_entity_hierarchy_batch([actor_path])
                if not infos or infos[0] is None:
                    return json.dumps(
                        {
                            "success": False,
                            "message": f"未找到Actor '{actor_path}' 的Entity层级结构",
                        },
                        ensure_ascii=False,
                    )

                found = self._find_entity_by_name_in_tree(infos[0], entity_name)
                if found is None:
                    return json.dumps(
                        {
                            "success": False,
                            "message": f"未找到名为 '{entity_name}' 的Entity",
                        },
                        ensure_ascii=False,
                    )

                entity_id, _ = found
                actor_entities = ActorEntities(actor_path, [entity_id])
                groups_list = await remote_scene.get_entity_property_groups(actor_entities)
                if not groups_list or not groups_list[0]:
                    return json.dumps(
                        {
                            "success": False,
                            "message": f"未找到Entity '{entity_name}' 的属性组",
                        },
                        ensure_ascii=False,
                    )

                groups = groups_list[0]
                for group in groups:
                    for prop in group.properties:
                        if prop.name() == property_name:
                            key = ActorPropertyKey(
                                actor_path=actor_path,
                                entity_id=0,
                                entity_path=group.entity_path,
                                component_type_id=group.component_type_id,
                                component_type_index=group.component_type_index,
                                property_name=prop.name(),
                                property_type=prop.value_type(),
                            )
                            keys.append(key)
                            values.append(property_value)

            if not keys:
                return json.dumps(
                    {"success": False, "message": f"未找到属性 '{property_name}'"},
                    ensure_ascii=False,
                )
            await remote_scene.set_properties(keys, values)
            return json.dumps(
                {"success": True, "message": f"成功设置属性 '{property_name}'"},
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps(
                {"success": False, "message": f"设置属性失败: {e}"},
                ensure_ascii=False,
            )
        
    async def get_entity_hierarchy(self, asset_path: str) -> str:
        '''
        获取Actor的Entity层级结构树
        Args:
            asset_path: Actor在场景中的路径
        Returns:
            Entity层级结构的json字符串格式，包含entity_id、name、entity_path和children
        '''
        try:
            remote_scene = get_remote_scene()
            # 优先从远程服务获取 Entity 层级结构
            infos = await remote_scene._service.get_entity_hierarchy_batch(
                [Path(asset_path)]
            )
            if infos and infos[0] is not None:
                return json.dumps(self._entity_info_to_dict(infos[0]), ensure_ascii=False)

            # 如果远程获取失败，尝试从本地场景获取
            actors: List[Dict[Path, BaseActor]] = []
            self.scene_edit_bus.get_all_actors(actors)
            if len(actors) > 0 and actors[0] is not None:
                actors_dict: Dict[Path, BaseActor] = actors[0]
                path = Path(asset_path)
                if path in actors_dict:
                    actor = actors_dict[path]
                    if isinstance(actor, AssetActor) and actor.entity_root is not None:
                        print(actor.entity_root.root_entity_info)
                        return json.dumps(
                            # self._entity_info_to_dict(actor.entity_root.root_entity_info),
                            ensure_ascii=False,
                        )

            return json.dumps(
                {"error": f"未找到Actor '{asset_path}' 的Entity层级结构"},
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def add_tools(self):
        # 资产元数据类
        self.mcp.tool(self.get_asset_map)
        self.mcp.tool(self.get_asset_info)
        self.mcp.tool(self.subscribe_asset_package_by_asset_name)
        self.mcp.tool(self.unsubscribe_asset_package_by_asset_name)
        self.mcp.tool(self.get_subscription_status_by_asset_name)
        self.mcp.tool(self.get_my_metadata)
        self.mcp.tool(self.get_asset_detail)
        self.mcp.tool(self.search_assets)
        self.mcp.tool(self.get_asset_json_by_name)
        self.mcp.tool(self.post_generate_task)
        self.mcp.tool(self.get_generate_task_status)
        self.mcp.tool(self.get_user_generate_tasks)
        self.mcp.tool(self.post_upload_generate_usdz)
        self.mcp.tool(self.post_cancel_asset_zip)
        self.mcp.tool(self.post_check_asset_version)
        self.mcp.tool(self.post_upload_asset_zip)
        self.mcp.tool(self.post_upload_usdz)
        self.mcp.tool(self.post_upload_xml)
        self.mcp.tool(self.get_task_chain_progress)
        self.mcp.tool(self.post_save_asset_draft)
        self.mcp.tool(self.delete_asset)

        # Actor 查询类
        self.mcp.tool(self.get_all_actors)
        self.mcp.tool(self.get_actor_transform)
        self.mcp.tool(self.get_selection)
        self.mcp.tool(self.get_actor_properties)
        self.mcp.tool(self.get_entity_hierarchy)

        # Actor 编辑类
        self.mcp.tool(self.set_actor_transform)
        self.mcp.tool(self.add_actor)
        self.mcp.tool(self.delete_actor)
        self.mcp.tool(self.rename_actor)
        self.mcp.tool(self.reparent_actor)
        self.mcp.tool(self.duplicate_actors)
        self.mcp.tool(self.set_actor_properties)

        # 选择操作类
        self.mcp.tool(self.set_selection_and_active_actor)
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
        self.config_service.mark_mcp_ready()
        await self.mcp.run_async(transport="http", port=self.port, show_banner=False)

    def stop(self):
        if self._task and not self._task.done():
            self._task.cancel()