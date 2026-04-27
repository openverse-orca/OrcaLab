import asyncio
import json
from typing import List, override
import logging
from pathlib import Path as SystemPath
from PySide6 import QtCore, QtWidgets
from PySide6.QtGui import QKeyEvent

from orcalab.local_scene import LocalScene
from orcalab.remote_scene import RemoteScene
from orcalab.report.report import (
    ask_user_consent,
    collect_user_env,
    send_report_directly,
)
from orcalab.scene_edit_service import SceneEditService
from orcalab.scene_layout.scene_layout_helper import SceneLayoutHelper
from orcalab.simulation.simulation_bus import SimulationRequestBus
from orcalab.simulation.simulation_service import SimulationService
from orcalab.ui.camera.camera_bus import (
    CameraNotification,
    CameraRequest,
    CameraNotificationBus,
    CameraRequestBus,
)
from orcalab.ui.icon_util import schedule_windows_taskbar_icon_refresh
from orcalab.ui.viewport import Viewport
from orcalab.config_service import ConfigService
from orcalab.application_bus import ApplicationRequest, ApplicationRequestBus
from orcalab.ui.user_event_bus import UserEventRequest, UserEventRequestBus
from orcalab.report.abnormal_exit_report import take_pending_abnormal_exit_report, send_abnormal_exit_report

logger = logging.getLogger(__name__)


class MainWindowFullScreen(
    QtWidgets.QWidget,
    ApplicationRequest,
    UserEventRequest,
    CameraNotification,
    CameraRequest,
):

    def __init__(self):
        super().__init__()
        self.config_service = ConfigService()

    def connect_buses(self):
        ApplicationRequestBus.connect(self)
        UserEventRequestBus.connect(self)
        CameraNotificationBus.connect(self)
        CameraRequestBus.connect(self)
        logger.debug("connect_buses")

    def disconnect_buses(self):
        UserEventRequestBus.disconnect(self)
        ApplicationRequestBus.disconnect(self)
        CameraNotificationBus.disconnect(self)
        CameraRequestBus.disconnect(self)
        logger.debug("disconnect_buses")

    async def init(self):
        self.local_scene = LocalScene()
        self.remote_scene = RemoteScene(self.config_service)
        self.scene_edit_service = SceneEditService(self.local_scene, self.remote_scene)
        self.simulation_service = SimulationService()

        logger.info("开始初始化 UI…")

        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._viewport_widget = Viewport()
        await asyncio.sleep(0.5)
        layout.addWidget(self._viewport_widget)

        rect = self.screen().availableGeometry()
        self.resize(rect.width(), rect.height())
        self.showMaximized()
        schedule_windows_taskbar_icon_refresh(self)
        await asyncio.sleep(0.5)
        logger.info("UI 初始化完成")

        if await ask_user_consent():
            logger.info("用户允许发送统计数据")
            await send_report_directly()
        else:
            logger.info("用户拒绝发送统计数据")

        # 若上次异常退出，上传上次运行的 log 文件
        if take_pending_abnormal_exit_report():
            try:
                await send_abnormal_exit_report()
            except Exception:
                logger.exception("crash_reports 上传失败")

        logger.info("初始化引擎...")
        self._viewport_widget.init_viewport()
        self._viewport_widget.start_viewport_main_loop()
        await asyncio.sleep(0.5)
        logger.info("引擎初始化完成")

        self.remote_scene.connect_bus()
        self.scene_edit_service.connect_bus()
        self.simulation_service.connect_bus()
        self.connect_buses()

        await self.remote_scene.init_grpc()
        await self.remote_scene.set_sync_from_mujoco_to_scene(False)
        await self.remote_scene.set_selection([])
        await self.remote_scene.clear_scene()

        default_layout_path = self.config_service.default_layout_file()
        if default_layout_path and SystemPath(default_layout_path).exists():
            helper = SceneLayoutHelper(self.local_scene)
            if not await helper.load_scene_layout(self, default_layout_path):
                QtWidgets.QMessageBox.critical(
                    self,
                    "加载默认布局失败",
                    "所选场景的默认布局加载失败。\n",
                    QtWidgets.QMessageBox.StandardButton.Ok,
                )
                QtWidgets.QApplication.quit()
                return

        # Load cameras from remote scene.
        cameras = await self.remote_scene.get_cameras()
        viewport_camera_index = await self.remote_scene.get_active_camera()
        self.on_cameras_changed(cameras, viewport_camera_index)

        await asyncio.sleep(0.5)

        await self.start_sim()

        # 发送匿名统计数据
        await self.send_statistics()

        self.message_bubble("按Esc键退出")

    def stop_viewport_main_loop(self):
        """停止viewport主循环"""
        try:
            if hasattr(self, "_viewport_widget") and self._viewport_widget:
                logger.info("停止 viewport 主循环…")
                self._viewport_widget.stop_viewport_main_loop()
                logger.info("Viewport 主循环已停止")
        except Exception as e:
            logger.exception("停止 viewport 主循环失败: %s", e)

    async def start_sim(self):
        await SimulationRequestBus().start_simulation()

    async def stop_sim(self):
        await SimulationRequestBus().stop_simulation()

    async def cleanup(self):
        self.stop_viewport_main_loop()
        await asyncio.sleep(1)
        await self.stop_sim()
        self.disconnect_buses()
        await asyncio.sleep(1)
        await self.remote_scene.destroy_grpc()

    #
    # ApplicationRequestBus overrides
    #

    @override
    def get_local_scene(self, output: List[LocalScene]):
        output.append(self.local_scene)

    @override
    def get_remote_scene(self, output: List[RemoteScene]):
        output.append(self.remote_scene)

    async def send_statistics(self):
        if not await ask_user_consent():
            return

        data = collect_user_env("backend")
        await self.remote_scene.custom_command(f"user_env_report:{json.dumps(data)}")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == QtCore.Qt.Key.Key_Escape:

            QMessageBox = QtWidgets.QMessageBox

            msg_box = QMessageBox()
            msg_box.setWindowTitle("退出应用")
            msg_box.setText("是否退出 OrcaLab？")

            yes_button = msg_box.addButton("确定", QMessageBox.ButtonRole.YesRole)
            no_button = msg_box.addButton("取消", QMessageBox.ButtonRole.NoRole)
            msg_box.setDefaultButton(no_button)

            msg_box.exec()

            if msg_box.clickedButton() == yes_button:
                asyncio.create_task(self.on_quit())

        return super().keyPressEvent(event)

    async def on_quit(self):
        await self.stop_sim()
        self.close()

    def message_bubble(self, message: str, duration_ms: int = 3000):
        label = QtWidgets.QLabel(message, self)
        label.setStyleSheet(
            """
            background-color: rgba(0, 0, 0, 180);
            color: white;
            padding: 10px;
            """
        )
        label.adjustSize()
        label.move((self.width() - label.width()) // 2, 20)
        label.show()

        QtCore.QTimer.singleShot(duration_ms, label.deleteLater)
