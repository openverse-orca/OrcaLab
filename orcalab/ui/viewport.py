import asyncio
from PySide6 import QtCore, QtWidgets, QtGui
import pathlib

from orcalab.config_service import ConfigService

from orcalab_pyside import Viewport as _Viewport


class Viewport(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._viewport = _Viewport()

        _layout = QtWidgets.QVBoxLayout(self)
        self.setLayout(_layout)

        _layout.addWidget(self._viewport)

    def init_viewport(self):

        self.command_line = [
            "pseudo.exe",
            "--datalink_host=54.223.63.47",
            "--datalink_port=7000",
        ]

        config_service = ConfigService()

        project_path = config_service.orca_project_folder()
        connect_builder_hub = False

        if config_service.is_development():
            project_path = config_service.dev_project_path()
            connect_builder_hub = config_service.connect_builder_hub()

        if not self._validate_project_path(project_path):
            raise RuntimeError(f"Invalid project path: {project_path}")

        self.command_line.append(f"--project-path={project_path}")

        if not self._viewport.init_viewport(self.command_line, connect_builder_hub):
            raise RuntimeError("Failed to initialize viewport")

    def _validate_project_path(self, path: str) -> bool:
        project_dir = pathlib.Path(path)
        if not project_dir.exists() or not project_dir.is_dir():
            return False

        project_json = project_dir / "project.json"
        if not project_json.exists() or not project_json.is_file():
            return False

        return True

    def start_viewport_main_loop(self):
        self._viewport_running = True
        asyncio.create_task(self._viewport_main_loop())

    async def _viewport_main_loop(self):
        self._viewport.main_loop_tick()
        if self._viewport_running:
            asyncio.create_task(self._viewport_main_loop())
