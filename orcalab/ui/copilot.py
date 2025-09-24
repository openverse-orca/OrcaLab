import asyncio
from typing import List
from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtCore import Qt
from orcalab.actor import BaseActor, AssetActor
from orcalab.path import Path
from orcalab.copilot import CopilotService


class CopilotPanel(QtWidgets.QWidget):
    """Copilot panel for asset search and actor creation"""
    
    add_item = QtCore.Signal(str, BaseActor)  # Signal emitted when submit button is clicked, compatible with asset_browser
    
    def __init__(self, remote_scene=None):
        super().__init__()
        self.remote_scene = remote_scene
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
        button_layout.addStretch()  # Push button to the left
        
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
            spawnable_name, scene_data = await self.copilot_service.generate_asset_from_prompt(
                prompt, 
                progress_callback=self._update_progress_message
            )
            
            if not spawnable_name:
                self.log_error("Failed to generate asset from prompt")
                return
            
            self.log_success(f"Generated asset: '{spawnable_name}'")
            
            # Step 2.5: Display detailed asset information
            self._display_scene_info(scene_data)
            
            # Step 3: Emit signal to create actor using existing add_item_to_scene API
            self.log_message("Step 3: Creating actor using existing API...")
            self.add_item.emit(spawnable_name, None)  # None means root path
            self.log_success("Actor creation signal sent successfully!")
            
            # Clear input field
            self.clear_input()
            self.log_success("Asset generation and actor creation completed successfully!")
            
        except Exception as e:
            self.log_error(f"Failed to generate asset: {str(e)}")
            import traceback
            self.log_error(f"Error details: {traceback.format_exc()}")
        finally:
            # Re-enable submit button
            self.set_submit_enabled(True)
