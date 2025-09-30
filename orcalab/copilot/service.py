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
        
    async def generate_asset_from_prompt(self, prompt: str, progress_callback=None) -> tuple[Optional[str], Dict[str, Any]]:
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
            
            # Step 2: Parse the generated scene to get asset information
            if progress_callback:
                progress_callback("Parsing generated scene...")
            scene_data = await self._parse_scene()
            
            # Add generation info to scene data
            scene_data['generation_info'] = {
                'selected_agent': generation_data.get('selected_agent'),
                'scene_path': generation_data.get('scene_path'),
                'message': generation_data.get('message')
            }
            
            # Step 3: Extract the first asset's spawnable name
            asset_path = None
            if scene_data.get('assets') and len(scene_data['assets']) > 0:
                first_asset = scene_data['assets'][0]
                asset_path = first_asset.get('name', '')
            
            return asset_path, scene_data
            
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
            
            if not generation_data.get('success', False):
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
            json={"prompt": prompt},
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
    
    def create_corner_lights_for_orcalab(self, scene_data: Dict[str, Any], light_height: float = 300.0) -> List[Dict[str, Any]]:
        """
        Create corner light assets for OrcaLab based on scene bounding box.
        
        Args:
            scene_data: The scene data from the server containing bounding box info
            light_height: Height of lights above the scene in centimeters (USD coordinate system)
            
        Returns:
            List[Dict[str, Any]]: List of light asset information in USD coordinate system
        """
        lights = []
        
        # Get bounding box information
        if not scene_data.get('bounding_box'):
            print("Warning: No bounding box info available, cannot add corner lights")
            return lights
            
        bbox = scene_data['bounding_box']
        min_point = tuple(bbox['min'])
        max_point = tuple(bbox['max'])
        center_point = tuple(bbox['center'])
        
        # Calculate half dimensions in USD coordinate system (centimeters)
        half_width = (max_point[0] - min_point[0]) / 2.0  # Half width in cm
        half_length = (max_point[2] - min_point[2]) / 2.0  # Half length in cm (USD Z-axis)
        
        # Calculate corner positions (3/4 distance from center to corner) in USD coordinates
        # USD coordinate system: Y-up, so we use (X, Y, Z) where Y is height
        corner_positions = [
            # Corner 1: +width, +length (northeast)
            (half_width * 3/4, half_length * 3/4),
            # Corner 2: +width, -length (southeast) 
            (half_width * 3/4, -half_length * 3/4),
            # Corner 3: -width, +length (northwest)
            (-half_width * 3/4, half_length * 3/4),
            # Corner 4: -width, -length (southwest)
            (-half_width * 3/4, -half_length * 3/4)
        ]
        
        corner_names = ["northeast_light", "southeast_light", "northwest_light", "southwest_light"]
        
        for i, (corner_x, corner_z) in enumerate(corner_positions):
            light_name = corner_names[i]
            
            # Create light position in USD coordinate system (centimeters)
            # USD: (X, Y, Z) where Y is up
            light_position = {
                'x': center_point[0] + corner_x,  # X position relative to center
                'y': light_height,                # Y is height in USD coordinate system
                'z': center_point[2] + corner_z   # Z position relative to center
            }
            
            # Light rotation: point downward (180 degrees around X-axis)
            light_rotation = {
                'x': 180.0,  # 180 degrees around X-axis to point downward
                'y': 0.0,
                'z': 0.0
            }
            
            light_info = {
                'asset_path': 'spotlight',
                'name': light_name,
                'position': light_position,
                'rotation': light_rotation,
                'scale': {'x': 1.0, 'y': 1.0, 'z': 1.0},
                'uuid': f'light_{i+1}'  # Simple UUID for lights
            }
            lights.append(light_info)
            
            print(f"Created {light_name} at USD position ({light_position['x']:.1f}, {light_position['y']:.1f}, {light_position['z']:.1f})cm")
        
        print(f"Created {len(lights)} corner lights successfully in USD coordinate system.")
        return lights
    
    def create_walls_for_orcalab(self, scene_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Create wall assets for OrcaLab based on scene bounding box.
        
        Args:
            scene_data: The scene data from the server containing bounding box info
            wall_height: Height of walls in centimeters (USD coordinate system)
            
        Returns:
            List[Dict[str, Any]]: List of wall asset information in USD coordinate system
        """
        walls = []
        
        # Get bounding box information
        if not scene_data.get('bounding_box'):
            print("Warning: No bounding box info available, cannot add walls")
            return walls
            
        bbox = scene_data['bounding_box']
        min_point = tuple(bbox['min'])
        max_point = tuple(bbox['max'])
        center_point = tuple(bbox['center'])
        
        # Calculate half dimensions in USD coordinate system (centimeters)
        half_width = (max_point[0] - min_point[0]) / 2.0  # Half width in cm
        half_length = (max_point[2] - min_point[2]) / 2.0  # Half length in cm (USD Z-axis)
        
        # Wall positions: North, South, East, West
        # Each wall faces toward the center
        # USD coordinate system: Y-up, so we use (X, Y, Z) where Y is height
        wall_positions = [
            # North wall (facing south toward center)
            {
                'x': center_point[0],
                'y': -200,
                'z': center_point[2] + half_length
            },
            # South wall (facing north toward center)  
            {
                'x': center_point[0],
                'y': -200,
                'z': center_point[2] - half_length
            },
            # East wall (facing west toward center)
            {
                'x': center_point[0] + half_width,
                'y': -200,
                'z': center_point[2]
            },
            # West wall (facing east toward center)
            {
                'x': center_point[0] - half_width,
                'y': -200,
                'z': center_point[2]
            }
        ]
        
        # Wall rotations: Each wall needs to face the center
        wall_rotations = [
            # North wall: rotate 180 degrees around Y to face south
            {'x': -90.0, 'y': 0.0, 'z': 0.0},
            # South wall: no rotation needed (already faces north)
            {'x': 90.0, 'y': 0.0, 'z': 0.0},
            # East wall: rotate -90 degrees around Y to face west
            {'x': 0.0, 'y': 0, 'z': 90.0},
            # West wall: rotate 90 degrees around Y to face east
            {'x': 0.0, 'y': 0, 'z': -90.0}
        ]
        
        wall_names = ["north_wall", "south_wall", "east_wall", "west_wall"]
        
        for i, (position, rotation, name) in enumerate(zip(wall_positions, wall_rotations, wall_names)):
            wall_info = {
                'asset_path': 'wall_10x10',
                'name': name,
                'position': position,
                'rotation': rotation,
                'scale': {'x': 1.0, 'y': 1.0, 'z': 1.0},
                'uuid': f'wall_{i+1}'  # Simple UUID for walls
            }
            walls.append(wall_info)
            
            print(f"Created {name} at USD position ({position['x']:.1f}, {position['y']:.1f}, {position['z']:.1f})cm")
        
        print(f"Created {len(walls)} walls successfully in USD coordinate system.")
        return walls
    