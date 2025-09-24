import asyncio
from typing import List
from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtCore import Qt
from orcalab.actor import BaseActor, AssetActor
from orcalab.path import Path


class CopilotPanel(QtWidgets.QWidget):
    """Copilot panel for asset search and actor creation"""
    
    add_item = QtCore.Signal(str, BaseActor)  # Signal emitted when submit button is clicked, compatible with asset_browser
    
    def __init__(self, remote_scene=None):
        super().__init__()
        self.remote_scene = remote_scene
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the UI components"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Input section
        input_layout = QtWidgets.QVBoxLayout()
        
        # Text input for asset spawnable name (multi-line)
        self.input_field = QtWidgets.QTextEdit()
        self.input_field.setPlaceholderText("Enter asset spawnable name...\nSupports multiple lines for longer names\nUse Ctrl+Enter to submit")
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
        
    async def _handle_asset_creation(self, spawnable_name: str):
        """Handle the complete asset creation workflow"""
        try:
            # Disable submit button during processing
            self.set_submit_enabled(False)
            self.log_message(f"Starting actor creation for spawnable name: '{spawnable_name}'")
            
            # Step 1: Get available assets
            self.log_message("Step 1: Retrieving available assets...")
            if not self.remote_scene:
                self.log_error("Remote scene not available")
                return
                
            assets = await self.remote_scene.get_actor_assets()
            self.log_message(f"Found {len(assets)} available assets")
            
            # Step 2: Search for matching asset
            self.log_message(f"Step 2: Searching for asset with spawnable name '{spawnable_name}'...")
            matching_assets = [asset for asset in assets if spawnable_name.lower() in asset.lower()]
            
            if not matching_assets:
                self.log_error(f"No assets found matching '{spawnable_name}'")
                self.log_message("Available assets:")
                for asset in assets[:10]:  # Show first 10 assets
                    self.log_message(f"  - {asset}")
                if len(assets) > 10:
                    self.log_message(f"  ... and {len(assets) - 10} more")
                return
                
            # Use the first matching asset (exact match preferred)
            exact_match = next((asset for asset in assets if asset.lower() == spawnable_name.lower()), None)
            selected_asset = exact_match if exact_match else matching_assets[0]
            
            if exact_match:
                self.log_success(f"Found exact match: '{selected_asset}'")
            else:
                self.log_success(f"Found closest match: '{selected_asset}' (from {len(matching_assets)} matches)")
            
            # Step 3: Emit signal to create actor using existing add_item_to_scene API
            self.log_message("Step 3: Creating actor using existing API...")
            self.add_item.emit(selected_asset, None)  # None means root path
            self.log_success("Actor creation signal sent successfully!")
            
            # Clear input field
            self.clear_input()
            self.log_success("Actor creation completed successfully!")
            
        except Exception as e:
            self.log_error(f"Failed to create actor: {str(e)}")
            import traceback
            self.log_error(f"Error details: {traceback.format_exc()}")
        finally:
            # Re-enable submit button
            self.set_submit_enabled(True)
