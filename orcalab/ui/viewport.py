import asyncio
import logging
import os
import pathlib
from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.config_service import ConfigService
from orcalab.ui.user_event_bus import UserEventRequestBus
from orcalab.ui.user_event import MouseAction, MouseButton, KeyAction
from orcalab.ui.user_event_util import convert_key_code

logger = logging.getLogger(__name__)


def _env_flag(name: str) -> bool:
    value = os.getenv(name)
    if value is None:
        return False
    return value.lower() not in {"0", "false", "off"}


class Viewport(QtWidgets.QWidget):
    assetDropped = QtCore.Signal(str, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setAcceptDrops(True)

        # 延迟导入 orcalab_pyside，直到实际需要时
        try:
            from orcalab_pyside import Viewport as _Viewport

            self._viewport = _Viewport()
        except ImportError:
            logger.warning("orcalab_pyside 包未安装，某些功能可能不可用")
            self._viewport = None

        _layout = QtWidgets.QVBoxLayout(self)
        _layout.setContentsMargins(1, 1, 1, 1)
        _layout.setSpacing(0)
        self.setLayout(_layout)

        if self._viewport:
            _layout.addWidget(self._viewport)

    def init_viewport(self):
        if not self._viewport:
            raise RuntimeError("orcalab_pyside 包未安装，无法初始化视口")

        config_service = ConfigService()

        base_url = config_service.datalink_base_url()
        if base_url.endswith("/api"):
            base_url = base_url[:-4]

        self.command_line = [
            "pseudo.exe",
            "--LoadLevel",
            config_service.level(),
            config_service.lock_fps(),
            "-datalink-scheme-host-port",
            f"{base_url}"
        ]

        if config_service.enable_debug_tool():
            self.command_line.append("--debug-tool")

        project_path = config_service.orca_project_folder()
        connect_builder_hub = False

        if config_service.is_development():
            project_path = config_service.dev_project_path()
            connect_builder_hub = config_service.connect_builder_hub()

        if not self._validate_project_path(project_path):
            raise RuntimeError(f"Invalid project path: {project_path}")

        self.command_line.append(f"--project-path={project_path}")

        enable_default_event_filter = not _env_flag("ORCA_4050_DISABLE_DEFAULT_EVENT_FILTER")
        if any(
            _env_flag(flag)
            for flag in (
                "ORCA_4050_DEBUG",
                "ORCA_4050_DISABLE_DEFAULT_EVENT_FILTER",
                "ORCA_4050_DISABLE_RUNTIME_PICK",
                "ORCA_4050_DISABLE_PICK_READBACK",
                "ORCA_4050_DISABLE_SURFACE_RESIZE_WORKAROUND",
                "ORCA_4050_SINGLE_FRAME_PICK_LOG",
            )
        ):
            logger.info(
                "4050 special build flags: debug=%s default_event_filter=%s disable_runtime_pick=%s disable_pick_readback=%s disable_surface_resize_workaround=%s single_frame_pick_log=%s",
                _env_flag("ORCA_4050_DEBUG"),
                enable_default_event_filter,
                _env_flag("ORCA_4050_DISABLE_RUNTIME_PICK"),
                _env_flag("ORCA_4050_DISABLE_PICK_READBACK"),
                _env_flag("ORCA_4050_DISABLE_SURFACE_RESIZE_WORKAROUND"),
                _env_flag("ORCA_4050_SINGLE_FRAME_PICK_LOG"),
            )

        if not self._viewport.init_viewport(
            self.command_line,
            connect_builder_hub,
            enable_default_event_filter=enable_default_event_filter,
            custom_event_filter=None,
        ):
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

            if self._viewport:
                self._viewport.main_loop_tick()

            # 如果还在运行，继续下一帧
            if self._viewport_running:
                # 使用asyncio.sleep而不是立即创建新任务，避免递归过深
                await asyncio.sleep(0.016)  # ~60 FPS
                asyncio.create_task(self._viewport_main_loop())
        except Exception as e:
            logger.exception("Viewport 主循环错误: %s", e)
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
            local_pos = event.position()  # QPointF
            x, y = local_pos.x(), local_pos.y()
            viewport_width = self.width()
            viewport_height = self.height()
            normX = x / viewport_width
            normY = y / viewport_height

            self.assetDropped.emit(asset_name, normX, normY)
            event.acceptProposedAction()
        else:
            event.ignore()

    # Example to send user events to the viewport by grpc.
    # Off by default.
    def eventFilter(self, watched, event: QtCore.QEvent) -> bool:
        if (
            event.type() == QtCore.QEvent.Type.KeyPress
            or event.type() == QtCore.QEvent.Type.KeyRelease
        ):
            assert isinstance(event, QtGui.QKeyEvent)
            key_event: QtGui.QKeyEvent = event
            key_code = convert_key_code(key_event)

            if event.type() == QtCore.QEvent.Type.KeyPress:
                UserEventRequestBus().queue_key_event(key_code, KeyAction.Down)
            elif event.type() == QtCore.QEvent.Type.KeyRelease:
                UserEventRequestBus().queue_key_event(key_code, KeyAction.Up)

        if event.type() == QtCore.QEvent.Type.Wheel:
            assert isinstance(event, QtGui.QWheelEvent)
            wheel_event: QtGui.QWheelEvent = event
            delta = wheel_event.angleDelta().y()
            UserEventRequestBus().queue_mouse_wheel_event(delta)

        if (
            event.type() == QtCore.QEvent.Type.MouseButtonPress
            or event.type() == QtCore.QEvent.Type.MouseButtonRelease
            or event.type() == QtCore.QEvent.Type.MouseMove
        ):
            assert isinstance(event, QtGui.QMouseEvent)
            mouse_event: QtGui.QMouseEvent = event

            if mouse_event.button() == QtCore.Qt.MouseButton.NoButton:
                button = MouseButton.NoButton
            elif mouse_event.button() == QtCore.Qt.MouseButton.LeftButton:
                button = MouseButton.Left
            elif mouse_event.button() == QtCore.Qt.MouseButton.RightButton:
                button = MouseButton.Right
            elif mouse_event.button() == QtCore.Qt.MouseButton.MiddleButton:
                button = MouseButton.Middle
            else:
                raise RuntimeError("Unsupported mouse button")

            x = mouse_event.position().x() / self.width()
            y = mouse_event.position().y() / self.height()

            if event.type() == QtCore.QEvent.Type.MouseButtonRelease:
                UserEventRequestBus().queue_mouse_event(x, y, button, MouseAction.Up)
            elif event.type() == QtCore.QEvent.Type.MouseButtonPress:
                UserEventRequestBus().queue_mouse_event(x, y, button, MouseAction.Down)
            elif event.type() == QtCore.QEvent.Type.MouseMove:
                UserEventRequestBus().queue_mouse_event(x, y, button, MouseAction.Move)

        return super().eventFilter(watched, event)
