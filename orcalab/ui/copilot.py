import asyncio
from typing import List
from copy import deepcopy
import uuid
import numpy as np
from scipy.spatial.transform import Rotation
from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtCore import Qt
from orcalab.actor import BaseActor, AssetActor, GroupActor
from orcalab.path import Path
from orcalab.copilot import CopilotService
from orcalab.math import Transform
import orca_gym.utils.rotations as rotations

class CopilotPanel(QtWidgets.QWidget):
    """Copilot panel for asset search and actor creation"""
    
    add_item_with_transform = QtCore.Signal(str, str, Path, Transform)  # Signal emitted when submit button is clicked, compatible with asset_browser
    request_add_group = QtCore.Signal(object)  # Signal to request creating a group (parent_actor: BaseActor | Path)
    
    def __init__(self, remote_scene=None, main_window=None):
        super().__init__()
        self.remote_scene = remote_scene
        self.main_window = main_window
        self.copilot_service = CopilotService()
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the UI components"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Input section
        input_layout = QtWidgets.QVBoxLayout()
        
        # Text input for asset generation prompt (multi-line)
        self.input_field = QtWidgets.QTextEdit()
        self.input_field.setPlaceholderText("Enter a description of the asset you want to generate...\nExample: 'a red sports car' or 'a wooden dining table'\nUse Ctrl+Enter to submit")
        self.input_field.setMaximumHeight(80)  # Limit height but allow multiple lines
        self.input_field.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.input_field.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.input_field.setStyleSheet("""
            QTextEdit {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 6px;
                font-size: 12px;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            }
            QTextEdit:focus {
                border-color: #007acc;
            }
        """)
        input_layout.addWidget(self.input_field)
        
        # Button layout
        button_layout = QtWidgets.QHBoxLayout()
        
        # Submit button
        self.submit_button = QtWidgets.QPushButton("Submit")
        self.submit_button.setFixedWidth(80)
        self.submit_button.setStyleSheet("""
            QPushButton {
                background-color: #007acc;
                color: #ffffff;
                border: none;
                border-radius: 3px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
            QPushButton:pressed {
                background-color: #004578;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #999999;
            }
        """)
        button_layout.addWidget(self.submit_button)
        
        button_layout.addStretch()  # Push buttons to the left
        
        input_layout.addLayout(button_layout)
        
        layout.addLayout(input_layout)
        
        # Log output section
        log_label = QtWidgets.QLabel("Execution Log:")
        log_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                margin-bottom: 4px;
            }
        """)
        layout.addWidget(log_label)
        
        # Scrollable text area for logs
        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 6px;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.log_text)
        
        # Connect signals
        self.submit_button.clicked.connect(self._on_submit_clicked)
        # QTextEdit doesn't have returnPressed signal, so we'll handle Enter key manually
        self.input_field.keyPressEvent = self._on_input_key_press
        
    def _on_input_key_press(self, event):
        """Handle key press events in the input field"""
        if event.key() == Qt.Key_Return and event.modifiers() & Qt.ControlModifier:
            # Ctrl+Enter submits the form
            self._on_submit_clicked()
            event.accept()
        else:
            # Let other keys work normally (including Enter for new lines)
            QtWidgets.QTextEdit.keyPressEvent(self.input_field, event)
            
    def _on_submit_clicked(self):
        """Handle submit button click"""
        text = self.input_field.toPlainText().strip()
        if text:
            # Use asyncio to run the async asset search and creation
            asyncio.create_task(self._handle_asset_creation(text))
    
            
    def log_message(self, message: str):
        """Add a message to the log"""
        timestamp = QtCore.QDateTime.currentDateTime().toString("hh:mm:ss")
        formatted_message = f"[{timestamp}] {message}"
        self.log_text.append(formatted_message)
        
        # Auto-scroll to bottom
        cursor = self.log_text.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        self.log_text.setTextCursor(cursor)
        
    def log_error(self, error: str):
        """Add an error message to the log"""
        timestamp = QtCore.QDateTime.currentDateTime().toString("hh:mm:ss")
        formatted_message = f"[{timestamp}] ERROR: {error}"
        self.log_text.append(f'<span style="color: #ff6b6b;">{formatted_message}</span>')
        
        # Auto-scroll to bottom
        cursor = self.log_text.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        self.log_text.setTextCursor(cursor)
        
    def log_success(self, message: str):
        """Add a success message to the log"""
        timestamp = QtCore.QDateTime.currentDateTime().toString("hh:mm:ss")
        formatted_message = f"[{timestamp}] SUCCESS: {message}"
        self.log_text.append(f'<span style="color: #51cf66;">{formatted_message}</span>')
        
        # Auto-scroll to bottom
        cursor = self.log_text.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        self.log_text.setTextCursor(cursor)
        
    def clear_log(self):
        """Clear the log"""
        self.log_text.clear()
        
    def set_submit_enabled(self, enabled: bool):
        """Enable or disable the submit button"""
        self.submit_button.setEnabled(enabled)
        
    def clear_input(self):
        """Clear the input field"""
        self.input_field.clear()
        
    def set_remote_scene(self, remote_scene):
        """Set the remote scene instance for asset operations"""
        self.remote_scene = remote_scene
    
    def set_main_window(self, main_window):
        """Set the main window instance for asset operations"""
        self.main_window = main_window
    
    def set_server_config(self, server_url: str, timeout: int = 180):
        """
        Configure the server settings for the copilot service.
        
        Args:
            server_url: The URL of the server to send requests to
            timeout: Request timeout in seconds
        """
        self.copilot_service.set_server_url(server_url)
        self.copilot_service.set_timeout(timeout)
    
    def _display_scene_info(self, scene_data: dict):
        """
        Display detailed scene information in the log output.
        
        Args:
            scene_data: The scene data returned from the server
        """
        try:
            # Display generation info
            if scene_data.get('generation_info'):
                gen_info = scene_data['generation_info']
                self.log_message("🤖 Generation Information:")
                self.log_message(f"  Selected Agent: {gen_info.get('selected_agent', {}).get('agent', 'Unknown')}")
                self.log_message(f"  Reasoning: {gen_info.get('selected_agent', {}).get('reasoning', 'N/A')}")
                self.log_message(f"  Scene Path: {gen_info.get('scene_path', 'N/A')}")
                self.log_message(f"  Message: {gen_info.get('message', 'N/A')}")
            
            # Display scene overview
            self.log_message("📊 Scene Overview:")
            self.log_message(f"  Assets: {scene_data.get('asset_count', 0)}")
            self.log_message(f"  Scene Dimensions: {self._format_dimensions(scene_data.get('scene_dimensions', {}))}")
            self.log_message(f"  Center Point: {self._format_point(scene_data.get('scene_center', []))}")
            
            # Display assets list
            if scene_data.get('assets'):
                self.log_message("🎯 Generated Assets:")
                for i, asset in enumerate(scene_data['assets'][:5]):  # Show first 5 assets
                    self.log_message(f"  {i+1}. {asset.get('name', 'Unknown')}")
                    self.log_message(f"     Position: {self._format_point(asset.get('position', {}))}")
                    self.log_message(f"     Rotation: {self._format_rotation(asset.get('rotation', {}))}")
                    self.log_message(f"     Scale: {self._format_scale(asset.get('scale', {}))}")
                
                if len(scene_data['assets']) > 5:
                    self.log_message(f"  ... and {len(scene_data['assets']) - 5} more assets")
            
        except Exception as e:
            self.log_error(f"Failed to display scene info: {str(e)}")
    
    def _format_dimensions(self, dimensions):
        """Format scene dimensions for display."""
        if not dimensions:
            return "Unknown"
        return f"{dimensions.get('width', 0):.1f} × {dimensions.get('height', 0):.1f} × {dimensions.get('depth', 0):.1f} cm"
    
    def _format_point(self, point):
        """Format a 3D point for display."""
        if isinstance(point, dict):
            return f"({point.get('x', 0):.1f}, {point.get('y', 0):.1f}, {point.get('z', 0):.1f})"
        elif isinstance(point, list) and len(point) >= 3:
            return f"({point[0]:.1f}, {point[1]:.1f}, {point[2]:.1f})"
        return "Unknown"
    
    def _format_rotation(self, rotation):
        """Format rotation for display."""
        if isinstance(rotation, dict):
            return f"({rotation.get('x', 0):.1f}°, {rotation.get('y', 0):.1f}°, {rotation.get('z', 0):.1f}°)"
        return "Unknown"
    
    def _format_scale(self, scale):
        """Format scale for display."""
        if isinstance(scale, dict):
            return f"({scale.get('x', 1):.2f}, {scale.get('y', 1):.2f}, {scale.get('z', 1):.2f})"
        return "Unknown"
    
    def _update_progress_message(self, message: str):
        """
        Update the progress message in the log.
        
        Args:
            message: The progress message to display
        """
        # Remove the last line if it's a progress message (contains dots)
        current_text = self.log_text.toPlainText()
        lines = current_text.split('\n')
        
        # Check if the last line is a progress message (contains dots)
        if lines and ('Generating scene' in lines[-1] and '.' in lines[-1]):
            lines.pop()  # Remove the last progress line
        
        # Add the new progress message
        lines.append(f"[{QtCore.QDateTime.currentDateTime().toString('hh:mm:ss')}] {message}")
        
        # Update the log text
        self.log_text.setPlainText('\n'.join(lines))
        
        # Auto-scroll to bottom
        cursor = self.log_text.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        self.log_text.setTextCursor(cursor)
        
    async def _handle_asset_creation(self, prompt: str):
        """Handle the complete asset creation workflow using server generation"""
        try:
            # Disable submit button during processing
            self.set_submit_enabled(False)
            self.log_message(f"Starting asset generation for prompt: '{prompt}'")
            
            # Step 1: Test server connection
            self.log_message("Step 1: Testing server connection...")
            if not await self.copilot_service.test_connection():
                self.log_error("Failed to connect to server. Please check server configuration.")
                return
            
            self.log_success("Server connection successful!")
            
            # Step 2: Generate asset from prompt
            self.log_message("Step 2: Generating asset from prompt...")
            asset_path, scene_data = await self.copilot_service.generate_asset_from_prompt(
                prompt, 
                progress_callback=self._update_progress_message
            )
            
            if not asset_path:
                self.log_error("Failed to generate asset from prompt")
                return
            
            self.log_success(f"Generated asset: '{asset_path}'")
            
            # Step 2.5: Display detailed asset information
            self._display_scene_info(scene_data)
            
            # Step 3: Create a unified group for the entire scene
            self.log_message("Step 3: Creating unified group for the scene...")
            import secrets
            group_suffix = secrets.token_hex(4)  # Generate 8 hex characters (4 bytes)
            group_name = f"CopilotScene_{group_suffix}"
            group_path = await self.create_group_for_scene(group_name)
            
            # Step 4: Add all scene assets to the group
            self.log_message("Step 4: Adding scene assets to the group...")
            assets = self.copilot_service.get_scene_assets_for_orcalab(scene_data)
            
            scene_center = scene_data.get('scene_center', [])
            center_point = {
                'x': scene_center[0],
                'y': scene_center[1],
                'z': scene_center[2]
            }
            
            await self.add_assets_to_group(assets, group_path, center_point)
            self.log_success(f"All {len(assets)} scene assets added successfully!")
            
            # Step 5: Add walls to the same group
            self.log_message("Step 5: Adding walls to the group...")
            walls = self.copilot_service.create_walls_for_orcalab(scene_data)
            
            if walls:
                await self.add_assets_to_group(walls, group_path, center_point)
                self.log_success(f"All {len(walls)} walls added successfully!")
            else:
                self.log_message("No walls added (no bounding box info available)")
            
            # Step 6: Add corner lights to the same group
            self.log_message("Step 6: Adding corner lights to the group...")
            lights = self.copilot_service.create_corner_lights_for_orcalab(scene_data, light_height=300.0)
            
            if lights:
                await self.add_assets_to_group(lights, group_path, center_point)
                self.log_success(f"All {len(lights)} corner lights added successfully!")
            else:
                self.log_message("No corner lights added (no bounding box info available)")
            
            # Summary
            total_assets = len(assets) + len(walls) + len(lights) if walls and lights else len(assets) + len(walls) if walls else len(assets) + len(lights) if lights else len(assets)
            self.log_success(f"Scene group '{group_name}' created with {total_assets} total assets ({len(assets)} scene assets + {len(walls) if walls else 0} walls + {len(lights) if lights else 0} lights)")
            
            # Clear input field
            self.clear_input()
            self.log_success("Asset generation and scene display completed successfully!")
            
        except Exception as e:
            self.log_error(f"Failed to generate asset: {str(e)}")
            import traceback
            self.log_error(f"Error details: {traceback.format_exc()}")
        finally:
            # Re-enable submit button
            self.set_submit_enabled(True)
    
    
    async def create_group_for_scene(self, group_name: str) -> Path:
        """
        Create a group for the scene and return its path.
        
        Args:
            group_name: Name of the group to create
            
        Returns:
            Path: Path to the created group
        """
        self.log_message(f"Creating group '{group_name}'...")
        
        # Emit signal to request group creation (pass root path as parent)
        root_path = Path.root_path()
        group_path = root_path / group_name
        self.request_add_group.emit(group_path)
        
        # Wait a bit for the group to be created
        await asyncio.sleep(0.1)
        
        self.log_success(f"Group '{group_name}' created successfully!")
        return group_path
    
    async def add_assets_to_group(self, assets_data, group_path, center_point):
        """
        Add assets to an existing group.
        
        Args:
            assets_data: List of asset dictionaries containing asset_path, name, position, rotation, scale
            group_path: Path to the group to add assets to
            center_point: Center point for coordinate conversion
        """
        if not assets_data:
            return
            
        self.log_message(f"Adding {len(assets_data)} assets to group...")
        
        for i, asset_data in enumerate(assets_data):
            self.log_message(f"  Adding asset {i+1}/{len(assets_data)}: {asset_data['name']}")

            transform = self._create_transform_from_server_data(asset_data, center_point)
            self.add_item_with_transform.emit(asset_data['name'], asset_data['asset_path'], group_path, transform)

            # Wait a bit for the asset to be created
            await asyncio.sleep(0.05)
        
        self.log_success(f"All {len(assets_data)} assets added to group!")

    async def create_actor_on_scene(self, assets_data, center_point):
        """
        Create assets using three-step process through signals.
        
        Args:
            assets_data: List of asset dictionaries containing asset_path, name, position, rotation, scale
        """
        if not assets_data:
            return
            
        # Step 1: Create a group to contain all assets using signal
        group_uuid = str(uuid.uuid4())
        group_uuid = group_uuid.replace('-', '_')
        group_name = f"CopilotGroup_{group_uuid}"
        self.log_message(f"Step 1: Creating group '{group_name}'...")
        
        # Emit signal to request group creation (pass root path as parent)
        root_path = Path.root_path()
        group_path = root_path / group_name
        self.request_add_group.emit(group_path)
        
        # Wait a bit for the group to be created (in a real implementation, you might want a callback)
        await asyncio.sleep(0.1)
        
        self.log_success(f"Group '{group_name}' created successfully!")
        
        # Step 2: Add all assets to the group using existing add_item signal
        self.log_message(f"Step 2: Adding {len(assets_data)} assets to group...")
        for i, asset_data in enumerate(assets_data):
            self.log_message(f"  Adding asset {i+1}/{len(assets_data)}: {asset_data['name']}")

            transform = self._create_transform_from_server_data(asset_data, center_point)
            self.add_item_with_transform.emit(asset_data['name'], asset_data['asset_path'], group_path, transform)

            # Wait a bit for the asset to be created
            await asyncio.sleep(0.05)
        
        self.log_success(f"All {len(assets_data)} assets added to group!")  
    
        print(f"Created copilot group '{group_name}' with {len(assets_data)} assets")
        print("Note: All transforms converted from USD to OrcaLab coordinate system")

    def _create_transform_from_server_data(self, asset_data, center_point):
        """
        Create a Transform object from server asset data.
        Server provides world coordinates in centimeters and rotation in degrees.
        We need to convert from USD coordinate system to OrcaLab coordinate system.
        
        USD coordinate system: Right-handed, Y-up, -Z-forward, X-right
        OrcaLab coordinate system: Right-handed, Z-up, X-forward, Y-left
        
        Args:
            asset_data: Dictionary containing position, rotation, scale data
                       - position: in centimeters (USD coordinate system)
                       - rotation: in degrees (Euler angles, USD coordinate system)
                       - scale: unitless scaling factors
            
        Returns:
            Transform object with the asset's transform data in OrcaLab coordinate system
        """
        # Extract position data (convert from centimeters to meters)
        position_offset = np.array([
            center_point.get('x', 0.0) / 100.0,
            -center_point.get('z', 0.0) / 100.0,
            0.0,
        ])

        position_data = asset_data.get('position', {})
        if isinstance(position_data, dict):
            # Convert from centimeters to meters first
            position_usd = {
                'x': position_data.get('x', 0.0) / 100.0,  # cm to m
                'y': position_data.get('y', 0.0) / 100.0,  # cm to m
                'z': position_data.get('z', 0.0) / 100.0   # cm to m
            }
        else:
            position_usd = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        
        # Convert USD coordinates to OrcaLab coordinates
        # USD (X, Y, Z) -> OrcaLab (X, -Z, Y)
        position_orcalab = np.array([
            position_usd['x'],      # X stays the same
            -position_usd['z'],     # USD -Z becomes OrcaLab Y
            position_usd['y'] - 0.005       # USD Y becomes OrcaLab Z ，有一些资产带有底板，下移5mm避免 Z-Fighting
        ], dtype=np.float64)
        position_orcalab = position_orcalab - position_offset
        
        # Debug output for coordinate conversion
        if asset_data.get('name') and 'debug' in asset_data.get('name', '').lower():
            print(f"  Coordinate conversion for {asset_data['name']}:")
            print(f"    USD position (m): {position_usd}")
            print(f"    OrcaLab position (m): {position_orcalab}")
        
        # Extract rotation data (Euler angles in degrees)
        rotation_data = asset_data.get('rotation', {})
        if isinstance(rotation_data, dict):
            rotation_usd = {
                'x': rotation_data.get('x', 0.0),  # degrees
                'y': rotation_data.get('y', 0.0),  # degrees
                'z': rotation_data.get('z', 0.0)   # degrees
            }
        else:
            rotation_usd = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        
        # Convert USD rotation to OrcaLab rotation
        # This accounts for the coordinate system change
        rotation_orcalab = {
            'x': rotation_usd['x'],      # X rotation stays the same
            'y': -rotation_usd['z'],     # USD Z rotation becomes OrcaLab -Y rotation
            'z': rotation_usd['y'] + 180 # USD Y rotation becomes OrcaLab Z rotation + 180
        }
        
        # Convert Euler angles to quaternion
        rotation_euler = np.array([
            np.radians(rotation_orcalab.get('x', 0.0)),
            np.radians(rotation_orcalab.get('y', 0.0)),
            np.radians(rotation_orcalab.get('z', 0.0))
        ])
        rotation_quat = rotations.euler2quat(rotation_euler)
        
        # Extract scale data (unitless scaling factors)
        scale_data = asset_data.get('scale', {})
        if isinstance(scale_data, dict):
            # Use uniform scale (average of x, y, z components)
            scale_x = scale_data.get('x', 1.0)
            scale_y = scale_data.get('y', 1.0)
            scale_z = scale_data.get('z', 1.0)
            scale = (scale_x + scale_y + scale_z) / 3.0
        else:
            scale = 1.0
        
        return Transform(position=position_orcalab, rotation=rotation_quat, scale=scale)

    def _create_transform_from_copilot_data(self, transform_data):
        """
        Create a Transform object from copilot transform data.
        This is the same logic as _create_transform_from_server_data but with a different name for clarity.
        
        Args:
            transform_data: Dictionary containing position, rotation, scale data
            
        Returns:
            Transform object with the transform data in OrcaLab coordinate system
        """
        return self._create_transform_from_server_data(transform_data)
