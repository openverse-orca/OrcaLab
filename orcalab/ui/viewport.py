import asyncio
import time
from PySide6 import QtCore, QtWidgets, QtGui
import pathlib
import logging

from orcalab.config_service import ConfigService
from orcalab.ui.user_event_bus import UserEventRequestBus
from orcalab.ui.user_event import MouseAction, MouseButton, KeyAction
from orcalab.ui.user_event_util import convert_key_code

logger = logging.getLogger(__name__)


class Viewport(QtWidgets.QWidget):
    assetDropped = QtCore.Signal(str, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setAcceptDrops(True)

        # 帧率控制相关属性
        self.last_frame_time = None
        self.frame_count = 0
        self.target_fps = 60  # 固定目标帧率

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

        if not self._viewport.init_viewport(
            self.command_line,
            connect_builder_hub,
            enable_default_event_filter=True,
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

            # 记录帧时间
            current_time = time.time()
            if self.last_frame_time is not None:
                self.frame_count += 1
                
                # 每120帧进行一次简单的帧率调整
                if self.frame_count % 120 == 0:
                    self._simple_adjust_frame_rate()        
            self.last_frame_time = current_time

            if self._viewport:
                self._viewport.main_loop_tick()

            # 如果还在运行，继续下一帧
            if self._viewport_running:
                # 动态计算睡眠时间以实现目标帧率
                sleep_time = self._calculate_sleep_time()
                await asyncio.sleep(sleep_time)
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

    # 帧率控制相关方法
    def _calculate_sleep_time(self) -> float:
        """计算睡眠时间以实现目标帧率"""
        if self.target_fps <= 0:
            return 0.016  # 默认60 FPS
        
        target_frame_time = 1.0 / self.target_fps
        if self.last_frame_time is None:
            return target_frame_time
        
        current_time = time.time()
        elapsed = current_time - self.last_frame_time
        
        # 如果已经超过目标帧时间，立即返回
        if elapsed >= target_frame_time:
            return 0.0
        
        # 否则计算需要睡眠的时间
        sleep_time = target_frame_time - elapsed
        return max(0.0, sleep_time)
    
    def _simple_adjust_frame_rate(self):
        """简化版动态帧率调整（以60 FPS为基准）"""
        try:
            # 基于帧计数和时间的简单调整
            # 每120帧调整一次，以60 FPS为基准
            if self.frame_count > 0 and self.last_frame_time is not None:
                # 计算实际平均帧率
                total_time = time.time() - self.last_frame_time
                if total_time > 0:
                    actual_fps = self.frame_count / total_time
                    
                    # 如果实际帧率持续高于65 FPS，说明性能充足，可以尝试稍微提高目标帧率
                    if actual_fps > 65 and self.target_fps < 75:
                        self.target_fps = min(self.target_fps + 5, 75)
                        logger.info(f"性能充足，提高目标帧率到: {self.target_fps} FPS")
                    
                    # 如果实际帧率持续低于55 FPS，说明性能不足，降低目标帧率
                    elif actual_fps < 55 and self.target_fps > 45:
                        self.target_fps = max(self.target_fps - 5, 45)
                        logger.info(f"性能不足，降低目标帧率到: {self.target_fps} FPS")
        
        except Exception as e:
            logger.debug(f"简化版动态帧率调整失败: {e}")
    

