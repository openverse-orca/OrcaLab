"""
Copilot service for handling asset generation requests.

This module provides the business logic for the copilot functionality,
including network requests to the server and data processing.
"""

import asyncio
import json
import requests
import tempfile
import os
from typing import Optional, Dict, Any, List
from pathlib import Path


class CopilotService:
    """Service class for handling copilot asset generation requests."""
    
    def __init__(self, server_url: str = "http://103.237.28.246:9023", timeout: int = 180):
        """
        Initialize the copilot service.
        
        Args:
            server_url: The URL of the server to send requests to
            timeout: Request timeout in seconds
        """
        self.server_url = server_url.rstrip('/')
        self.timeout = timeout
        
    async def generate_asset_from_prompt(self, prompt: str, progress_callback=None):
        """
        Generate an asset from a text prompt by sending a request to the server.
        
        Args:
            prompt: The text prompt describing the desired asset
            progress_callback: Optional callback function to report progress updates
            
        Returns:
            A tuple containing:
            - The spawnable name of the generated asset, or None if generation failed
            - The complete scene data from the server
            
        Raises:
            Exception: If the request fails or server returns an error
        """
        try:
            # Step 1: Generate scene from prompt
            generation_data = await self._generate_scene(prompt, progress_callback)
            
            
            if generation_data.get('status', 'failed') != 'success':
                raise Exception(f"Scene generation failed: {generation_data.get('message', 'Unknown error')}")
            
            return generation_data
            
        except Exception as e:
            raise Exception(f"Failed to generate asset from prompt: {str(e)}")
    
    async def _generate_scene(self, prompt: str, progress_callback=None) -> Dict[str, Any]:
        """
        Send a request to generate a scene from the given prompt.
        
        Args:
            prompt: The text prompt for scene generation
            progress_callback: Optional callback function to report progress updates
            
        Returns:
            The generation response data
            
        Raises:
            Exception: If the request fails
        """
        try:
            # Start progress indicator
            if progress_callback:
                progress_callback("Generating scene")
                # Start a background task to show progress dots
                progress_task = asyncio.create_task(self._show_progress_dots(progress_callback))
            
            # Run the HTTP request in a thread to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                self._make_generation_request,
                prompt
            )
            
            # Stop progress indicator
            if progress_callback and 'progress_task' in locals():
                progress_task.cancel()
                try:
                    await progress_task
                except asyncio.CancelledError:
                    pass
            
            if response.status_code != 200:
                raise Exception(f"Server error: {response.status_code} - {response.text}")
            
            generation_data = response.json()

            # Debug: print full response for troubleshooting
            print(f"Server response: {generation_data}")

            if generation_data.get('status', 'failed') == 'failed':
                raise Exception(f"Scene generation failed: {generation_data.get('message', 'Unknown error')}")
            
            return generation_data
            
        except requests.exceptions.Timeout:
            if progress_callback and 'progress_task' in locals():
                progress_task.cancel()
            raise Exception(f"Request timeout after {self.timeout} seconds. The server may be processing a complex scene.")
        except requests.exceptions.RequestException as e:
            if progress_callback and 'progress_task' in locals():
                progress_task.cancel()
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            if progress_callback and 'progress_task' in locals():
                progress_task.cancel()
            raise Exception(f"Generation error: {str(e)}")
    
    def _make_generation_request(self, prompt: str) -> requests.Response:
        """
        Make the actual HTTP request for scene generation.
        
        Args:
            prompt: The text prompt for scene generation
            
        Returns:
            The HTTP response
        """
        return requests.post(
            f"{self.server_url}/api/generate",
            json={"query": prompt},
            timeout=self.timeout
        )
    
    async def _parse_scene(self) -> Dict[str, Any]:
        """
        Send a request to parse the generated scene.
        
        Returns:
            The parsed scene data
            
        Raises:
            Exception: If the request fails
        """
        try:
            # Run the HTTP request in a thread to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                self._make_parse_request
            )
            
            if response.status_code != 200:
                raise Exception(f"Parse error: {response.status_code} - {response.text}")
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Parse request error: {str(e)}")
        except Exception as e:
            raise Exception(f"Parse error: {str(e)}")
    
    def _make_parse_request(self) -> requests.Response:
        """
        Make the actual HTTP request for scene parsing.
        
        Returns:
            The HTTP response
        """
        return requests.post(
            f"{self.server_url}/api/parse",
            json={},
            timeout=30
        )
    
    async def test_connection(self) -> bool:
        """
        Test the connection to the server.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                self._make_health_request
            )
            return response.status_code == 200
        except:
            return False
    
    def _make_health_request(self) -> requests.Response:
        """
        Make a health check request to the server.
        
        Returns:
            The HTTP response
        """
        return requests.get(f"{self.server_url}/api/health", timeout=5)
    
    async def _show_progress_dots(self, progress_callback):
        """
        Show progress dots every 2 seconds to indicate the process is still running.
        
        Args:
            progress_callback: The callback function to update progress
        """
        dot_count = 0
        try:
            while True:
                await asyncio.sleep(2)  # Wait 2 seconds
                dot_count += 1
                dots = "." * (dot_count % 4)  # Cycle through 0, 1, 2, 3 dots
                progress_callback(f"Generating scene{dots}")
        except asyncio.CancelledError:
            # Task was cancelled, which is expected when generation completes
            pass
    
    def set_server_url(self, server_url: str):
        """
        Update the server URL.
        
        Args:
            server_url: The new server URL
        """
        self.server_url = server_url.rstrip('/')
    
    def set_timeout(self, timeout: int):
        """
        Update the request timeout.
        
        Args:
            timeout: The new timeout in seconds
        """
        self.timeout = timeout
    
    def get_scene_assets_for_orcalab(self, scene_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract asset information from scene data for OrcaLab add_item API.
        Includes transform data (position, rotation, scale) from server.
        
        Args:
            scene_data: The scene data from the server
            
        Returns:
            List[Dict[str, Any]]: List of asset information for OrcaLab with transform data
        """
        assets = []
        
        # Extract assets from scene data
        if scene_data.get('assets'):
            for asset in scene_data['assets']:
                # Use UUID as spawnable name, but ensure it's properly formatted
                uuid = asset.get('uuid', 'unknown')
                asset_path = uuid if uuid != 'unknown' else asset.get('name', 'asset')

                # 将 uuid 转为 asset_$uuid_usda 这样的格式，且 '-' 替换为 '_'
                asset_path = f"asset_{uuid.replace('-', '_')}_usda"
                
                # Debug output to show what spawnable names are being used
                print(f"Asset: {asset.get('name', 'asset')} -> Spawnable: {asset_path} (UUID: {uuid})")
                print(f"  USD Position (cm): {asset.get('position', {})}")
                print(f"  USD Rotation (degrees): {asset.get('rotation', {})}")
                print(f"  Scale: {asset.get('scale', {})}")
                print(f"  Note: Will be converted from USD to OrcaLab coordinate system")
                
                asset_info = {
                    'asset_path': asset_path,
                    'name': asset.get('name', 'asset'),
                    'position': asset.get('position', {}),
                    'rotation': asset.get('rotation', {}),
                    'scale': asset.get('scale', {}),
                    'uuid': uuid  # Keep UUID for reference
                }
                assets.append(asset_info)
        
        return assets
    
    def create_corner_lights_for_orcalab(self, scene_data: Dict[str, Any], light_height: float = 3.0) -> List[Dict[str, Any]]:
        """
        Create corner light assets for OrcaLab based on scene bounding box.
        
        Args:
            scene_data: The scene data from the server containing bounding box info
            light_height: Height of lights above the scene in meters
            
        Returns:
            List[Dict[str, Any]]: List of light asset information in meters
        """
        lights = []
        
        # 计算包围盒
        bbox = self.calculate_bounding_box(scene_data)
        if not bbox:
            print("Warning: Cannot calculate bounding box, cannot add corner lights")
            return lights
            
        min_point = tuple(bbox['min'])
        max_point = tuple(bbox['max'])
        center_point = tuple(bbox['center'])
        
            
        light_position = [center_point[0], center_point[1], max_point[2]]
        light_rotation = [0, 0, -180]
            
        light_info = {
                'asset_path': 'prefabs/light',
                'name': "light",
                'position': light_position,
                'rotation': light_rotation,
                'scale': 1.0,
            }
        lights.append(light_info)
            
        
        print(f"Created {len(lights)} corner lights successfully.")
        return lights
    
    def calculate_bounding_box(self, scene_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据 rooms 和 walls 数据计算场景包围盒
        
        Args:
            scene_data: 包含 rooms 和 walls 信息的场景数据
            
        Returns:
            包含 min, max, center 的包围盒字典，单位为米
        """
        if not scene_data.get('rooms'):
            return None
            
        rooms = scene_data['rooms']
        walls_data = scene_data.get('walls', [])
        
        # 从所有房间的 vertices 计算 XZ 平面的边界
        all_x = []
        all_z = []
        for room in rooms:
            vertices = room.get('vertices', [])
            for vertex in vertices:
                all_x.append(vertex[0])
                all_z.append(vertex[1])
        
        if not all_x or not all_z:
            return None
        
        # 计算 XZ 平面的边界
        min_x = min(all_x)
        max_x = max(all_x)
        min_z = min(all_z)
        max_z = max(all_z)
        
        # 计算 Y 轴边界（高度）
        min_y = 0.0  # 地面
        if walls_data:
            max_height = max(wall.get('height', 0.0) for wall in walls_data)
            max_y = max_height
        else:
            max_y = 2.5  # 默认高度
        
        # 计算中心点
        center_x = (min_x + max_x) / 2.0
        center_y = (min_y + max_y) / 2.0
        center_z = (min_z + max_z) / 2.0
        
        

        bbox = {
            'min': [min_x, -max_z, min_y],
            'max': [max_x, -min_z, max_y],
            'center': [center_x, -center_z, center_y]
        }
        
        print(f"Calculated bounding box: min={bbox['min']}, max={bbox['max']}, center={bbox['center']}")
        return bbox
    
    def create_walls_for_orcalab(self, scene_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        根据场景包围盒创建墙体资产
        
        Args:
            scene_data: 包含 rooms 和 walls 信息的场景数据
            
        Returns:
            墙体资产列表，单位为米
        """
        walls = []
        
        # 计算包围盒
        bbox = self.calculate_bounding_box(scene_data)
        if not bbox:
            print("Warning: Cannot calculate bounding box, cannot add walls")
            return walls
        
        min_point = tuple(bbox['min'])
        max_point = tuple(bbox['max'])
        center_point = tuple(bbox['center'])
        
        # 计算房间尺寸
        room_width = max_point[0] - min_point[0]    # X方向
        room_length = max_point[2] - min_point[2]   # Z方向
        room_height = max_point[1] - min_point[1]   # Y方向
        
        half_width = room_width / 2.0
        half_length = room_length / 2.0
        wall_y = center_point[1]
        

        
        # Wall positions, rotations, scales
        wall_configs = [
            {
                'position': [min_point[0], center_point[1], center_point[2]],
                'rotation': [0, 90.0, 0.0],
                'scale': 1,
                'name': 'wall_1'
            },
            {
                'position': [center_point[0], min_point[1], center_point[2]],
                'rotation': [-90, 0.0, 0.0],
                'scale': 1,
                'name': 'wall_2'
            },
            {
                'position': [center_point[0], center_point[1], min_point[2] + 0.01],
                'rotation': [0, 0, 0.0],
                'scale': 1,
                'name': 'wall_3'
            },
            {
                'position': [max_point[0], center_point[1], center_point[2]],
                'rotation': [0.0, -90.0, 0.0],
                'scale': 1,
                'name': 'wall_4'
            },
            {
                'position': [center_point[0], max_point[1], center_point[2]],
                'rotation': [90, 0, 0],
                'scale': 1,
                'name': 'wall_5'
            },
            {
                'position': [center_point[0], center_point[1], max_point[2]],
                'rotation': [180, 0, 0],
                'scale': 1,
                'name': 'wall_6'
            },

        ]
        
        for i, config in enumerate(wall_configs):
            wall_info = {
                'asset_path': 'prefabs/wall',
                'name': config['name'],
                'position': config['position'],
                'rotation': config['rotation'],
                'scale': config['scale'],
                'uuid': f'wall_{i+1}'
            }
            walls.append(wall_info)
            
         
        
        print(f"Created {len(walls)} walls successfully.")
        return walls
    