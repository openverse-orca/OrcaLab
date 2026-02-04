import asyncio
import json
from fastmcp import FastMCP
from orcalab.metadata_service_bus import MetadataServiceRequestBus

class OrcaLabMCPServer:
    def __init__(self, port):
        self.port = port
        self.metadata_service_bus = MetadataServiceRequestBus()
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
        self.metadata_service_bus.get_asset_info(output)
        asset_map = output[0]
        return json.dumps(asset_map)

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
        return json.dumps(asset_info)

    

    def add_tools(self):
        self.mcp.tool(self.get_asset_map)
        self.mcp.tool(self.get_asset_info)

    async def run(self):
        await self.mcp.run_async(transport="http", port=self.port)

    def stop(self):
        if self._task and not self._task.done():
            self._task.cancel()