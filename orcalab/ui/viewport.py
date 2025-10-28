import asyncio
from PySide6 import QtCore, QtWidgets, QtGui
import pathlib

from orcalab.config_service import ConfigService

from orcalab_pyside import Viewport as _Viewport


class Viewport(QtWidgets.QWidget):
    assetDropped = QtCore.Signal(str, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setAcceptDrops(True)

        self._viewport = _Viewport()

        _layout = QtWidgets.QVBoxLayout(self)
        self.setLayout(_layout)

        _layout.addWidget(self._viewport)

    def init_viewport(self):
        config_service = ConfigService()

        self.command_line = [
            "pseudo.exe",
            "--datalink_host=54.223.63.47",
            "--datalink_port=7000",
            # '--rhi-device-validation="enable"'
            "--LoadLevel",
            config_service.level(),
            config_service.lock_fps(),
        ]

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

    def stop_viewport_main_loop(self):
        """安全停止viewport主循环"""
        self._viewport_running = False

    async def _viewport_main_loop(self):
        try:
            # 检查事件循环是否还在运行
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # 事件循环已停止，退出
                return
            
            # 检查viewport是否还在运行
            if not self._viewport_running:
                return
                
            self._viewport.main_loop_tick()
            
            # 如果还在运行，继续下一帧
            if self._viewport_running:
                # 使用asyncio.sleep而不是立即创建新任务，避免递归过深
                await asyncio.sleep(0.016)  # ~60 FPS
                asyncio.create_task(self._viewport_main_loop())
        except Exception as e:
            print(f"Viewport主循环错误: {e}")
            # 发生错误时停止循环
            self._viewport_running = False

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent):
        if event.mimeData().hasFormat("application/x-orca-asset"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QtGui.QDropEvent):
        mime = event.mimeData()
        if mime.hasFormat("application/x-orca-asset"):
            asset_name = mime.data("application/x-orca-asset").data().decode("utf-8")
            local_pos = event.pos()  # QPoint
            x, y = local_pos.x(), local_pos.y()
            viewport_width = self.width()
            viewport_height = self.height()
            normX = x / viewport_width
            normY = y / viewport_height

            self.assetDropped.emit(asset_name, normX, normY)
            event.acceptProposedAction()
        else:
            event.ignore()
