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
            spawnable_name = None
            if scene_data.get('assets') and len(scene_data['assets']) > 0:
                first_asset = scene_data['assets'][0]
                spawnable_name = first_asset.get('name', '')
            
            return spawnable_name, scene_data
            
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
                spawnable_name = uuid if uuid != 'unknown' else asset.get('name', 'asset')

                # 将 uuid 转为 asset_$uuid_usda 这样的格式，且 '-' 替换为 '_'
                spawnable_name = f"asset_{uuid.replace('-', '_')}_usda"
                
                # Debug output to show what spawnable names are being used
                print(f"Asset: {asset.get('name', 'asset')} -> Spawnable: {spawnable_name} (UUID: {uuid})")
                print(f"  USD Position (cm): {asset.get('position', {})}")
                print(f"  USD Rotation (degrees): {asset.get('rotation', {})}")
                print(f"  Scale: {asset.get('scale', {})}")
                print(f"  Note: Will be converted from USD to OrcaLab coordinate system")
                
                asset_info = {
                    'spawnable_name': spawnable_name,
                    'name': asset.get('name', 'asset'),
                    'position': asset.get('position', {}),
                    'rotation': asset.get('rotation', {}),
                    'scale': asset.get('scale', {}),
                    'uuid': uuid  # Keep UUID for reference
                }
                assets.append(asset_info)
        
        return assets
    