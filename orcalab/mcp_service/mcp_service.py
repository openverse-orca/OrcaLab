import asyncio
import json
import numpy as np
from fastmcp import FastMCP
from orcalab.math import Transform
from orcalab.metadata_service_bus import MetadataServiceRequestBus
from orcalab.scene_edit_bus import SceneEditRequestBus
from orcalab.actor import AssetActor, BaseActor, GroupActor
from orcalab.path import Path
from typing import List, Dict

class OrcaLabMCPServer:
    def __init__(self, port):
        self.port = port
        self.metadata_service_bus = MetadataServiceRequestBus()
        self.scene_edit_bus = SceneEditRequestBus()
        self.mcp = FastMCP("OrcaLab MCP Server")
        self._task = None

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
        return json.dumps(asset_map, ensure_ascii=False)

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
        获取Actor的变换
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
        设置Actor的变换
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

    async def add_actor(self, actor_name:str, actor_path: str, parent_path: str = None) -> str:
        '''
        添加Actor
        Args:
            actor_name: Actor的名称
            actor_path: Actor在资产库中的路径，通过get_asset_map 或者get_asset_info获取
            parent_path: Actor的父Actor在场景中的路径，默认为"/" 
            
        Returns:
            添加Actor的结果的json字符串格式
        '''
        print(f"add_actor: actor_name: {actor_name}, actor_path: {actor_path}, parent_path: {parent_path}")
        actor, parent_actor = AssetActor(actor_name, actor_path), None
        actors: List[Dict[Path, BaseActor]] = []
        self.scene_edit_bus.get_all_actors(actors)
        if len(actors) > 0 and actors[0] is not None:
            actors: Dict[Path, BaseActor] = actors[0]
            if Path(parent_path) in actors:
                parent_actor = actors[Path(parent_path)]   
       
        try:
            if parent_path is not None:
                await self.scene_edit_bus.add_actor(actor, Path(parent_path), undo=True, source="mcp")
            else:
                await self.scene_edit_bus.add_actor(actor, Path.root_path(), undo=True, source="mcp")
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

    def add_tools(self):
        self.mcp.tool(self.get_asset_map)
        self.mcp.tool(self.get_asset_info)
        self.mcp.tool(self.get_all_actors)
        self.mcp.tool(self.get_actor_transform)
        self.mcp.tool(self.set_actor_transform)
        self.mcp.tool(self.add_actor)
        self.mcp.tool(self.delete_actor)
        self.mcp.tool(self.get_selection)
        
    async def run(self):
        await self.mcp.run_async(transport="http", port=self.port)

    def stop(self):
        if self._task and not self._task.done():
            self._task.cancel()