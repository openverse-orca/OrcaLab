import asyncio

from typing import Any, Dict, List, Tuple, override
import numpy as np
import logging

import json
import ast
import os
from pathlib import Path as SystemPath
from PySide6 import QtCore, QtWidgets, QtGui
from qasync import asyncWrap

from orcalab.actor import AssetActor, BaseActor, GroupActor
from orcalab.actor_util import make_unique_name
from orcalab.local_scene import LocalScene
from orcalab.path import Path
from orcalab.pyside_util import connect
from orcalab.remote_scene import RemoteScene
from orcalab.scene_layout.scene_layout_helper import SceneLayoutHelper
from orcalab.simulation.simulation_bus import (
    SimulationRequestBus,
    SimulationNotification,
    SimulationNotificationBus,
    SimulationState,
)
from orcalab.simulation.simulation_service import SimulationService
from orcalab.ui.actor_editor import ActorEditor
from orcalab.ui.actor_outline import ActorOutline
from orcalab.ui.actor_outline_model import ActorOutlineModel
from orcalab.ui.asset_browser.asset_browser import AssetBrowser
from orcalab.ui.asset_browser.thumbnail_render_bus import ThumbnailRenderRequestBus
from orcalab.ui.camera.camera_brief import CameraBrief
from orcalab.ui.camera.camera_bus import (
    CameraNotification,
    CameraRequest,
    CameraNotificationBus,
    CameraRequestBus,
)
from orcalab.ui.camera.camera_selector import CameraSelector
from orcalab.ui.copilot import CopilotPanel
from orcalab.ui.icon_util import make_icon
from orcalab.ui.theme_service import ThemeService
from orcalab.ui.tool_bar import ToolBar
from orcalab.ui.manipulator_bar import ManipulatorBar
from orcalab.ui.terminal_widget import TerminalWidget
from orcalab.ui.viewport import Viewport
from orcalab.ui.panel_manager import PanelManager
from orcalab.ui.panel import Panel
from orcalab.math import Transform
from orcalab.config_service import ConfigService
from orcalab.undo_service.undo_service import UndoService
from orcalab.scene_edit_service import SceneEditService
from orcalab.scene_edit_bus import SceneEditRequestBus
from orcalab.undo_service.undo_service_bus import can_redo, can_undo
from orcalab.url_service.url_service import UrlServiceServer
from orcalab.asset_service import AssetService
from orcalab.asset_service_bus import (
    AssetServiceNotification,
    AssetServiceNotificationBus,
)
from orcalab.application_bus import ApplicationRequest, ApplicationRequestBus

from orcalab.ui.user_event_bus import UserEventRequest, UserEventRequestBus


logger = logging.getLogger(__name__)


class MainWindow(
    PanelManager,
    ApplicationRequest,
    AssetServiceNotification,
    UserEventRequest,
    CameraNotification,
    CameraRequest,
    SimulationNotification,
):

    add_item_by_drag = QtCore.Signal(str, Transform)
    load_scene_layout_sig = QtCore.Signal(str)

    def __init__(self):
        super().__init__()
        self.cwd = os.getcwd()
        self.config_service = ConfigService()
        self._base_title = self.config_service._get_package_version()
        self.default_layout_path: str | None = None
        self.current_layout_path: str | None = None
        self._cleanup_in_progress = False
        self._cleanup_completed = False

        # Let empty area can steal focus.
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.ClickFocus)
        self.setWindowTitle(f"{self._base_title}")

    def connect_buses(self):
        super().connect_buses()
        ApplicationRequestBus.connect(self)
        AssetServiceNotificationBus.connect(self)
        UserEventRequestBus.connect(self)
        CameraNotificationBus.connect(self)
        CameraRequestBus.connect(self)
        SimulationNotificationBus.connect(self)
        logger.debug("connect_buses")

    def disconnect_buses(self):
        SimulationNotificationBus.disconnect(self)
        UserEventRequestBus.disconnect(self)
        AssetServiceNotificationBus.disconnect(self)
        ApplicationRequestBus.disconnect(self)
        CameraNotificationBus.disconnect(self)
        CameraRequestBus.disconnect(self)
        super().disconnect_buses()
        logger.debug("disconnect_buses")

    # def start_viewport_main_loop(self):
    #     self._viewport_widget.start_viewport_main_loop()

    async def init(self):
        self.local_scene = LocalScene()
        self.remote_scene = RemoteScene(self.config_service)

        self.asset_service = AssetService()
        self.url_server = UrlServiceServer()
        self.simulation_service = SimulationService()
        self.undo_service = UndoService()

        original_add_command = self.undo_service.add_command

        def add_command_with_dirty(command, _orig=original_add_command):
            _orig(command)
            if not self.undo_service._in_undo_redo:
                self._layout_modified = True
                self._update_title()

        self.undo_service.add_command = add_command_with_dirty

        self.scene_edit_service = SceneEditService(self.local_scene)

        self._viewport_widget = Viewport()

        self._current_scene_name: str | None = None
        self._current_layout_name: str | None = None
        self._layout_modified: bool = False

        logger.info("开始初始化 UI…")
        await self._init_ui()
        logger.info("UI 初始化完成")

        rect = QtCore.QRect(0, 0, 2000, 1200)
        self.resize(rect.width(), rect.height())
        center=self.screen().availableGeometry().center()
        self.move(center-rect.center())
        self.restore_default_layout()
        self.show()

        self._viewport_widget.init_viewport()
        self._viewport_widget.start_viewport_main_loop()
        await asyncio.sleep(0.5)

        connect(self.actor_outline_model.add_item, self.add_item_to_scene)

        connect(self.asset_browser_widget.add_item, self.add_item_to_scene)

        connect(self.copilot_widget.add_item_with_transform, self.add_item_to_scene_with_transform)
        connect(self.copilot_widget.request_add_group, self.on_copilot_add_group)

        connect(self.menu_file.aboutToShow, self.prepare_file_menu)
        connect(self.menu_edit.aboutToShow, self.prepare_edit_menu)
        connect(self.menu_help.aboutToShow, self.prepare_help_menu)

        connect(self.add_item_by_drag, self.add_item_drag)
        connect(self.load_scene_layout_sig, self.load_scene_layout)

        connect(self._viewport_widget.assetDropped, self.get_transform_and_add_item)

        self.actor_outline_widget.connect_bus()
        self.actor_outline_model.connect_bus()
        self.actor_editor_widget.connect_bus()

        self.undo_service.connect_bus()
        self.scene_edit_service.connect_bus()
        self.remote_scene.connect_bus()
        self.simulation_service.connect_bus()

        self.connect_buses()

        await self.remote_scene.init_grpc()
        await self.remote_scene.set_sync_from_mujoco_to_scene(False)
        await self.remote_scene.set_selection([])
        await self.remote_scene.clear_scene()

        self.default_layout_path = self._resolve_path(self.config_service.default_layout_file())
        if self.default_layout_path and SystemPath(self.default_layout_path).exists():
            try:
                await self.load_scene_layout(self.default_layout_path)
            except Exception as exc:  # noqa: BLE001
                logger.exception("加载默认布局失败: %s", exc)
                import traceback

                detail_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                QtWidgets.QMessageBox.critical(
                    self,
                    "加载默认布局失败",
                    "所选场景的默认布局加载失败。\n"
                    "请复制下方错误信息寻求帮助，并重新启动程序选择“空白布局”。\n\n"
                    f"{detail_text}",
                    QtWidgets.QMessageBox.StandardButton.Ok,
                )
                QtWidgets.QApplication.quit()
                return
            else:
                self._mark_layout_clean()

        self.cache_folder = await self.remote_scene.get_cache_folder()
        await self.url_server.start()

        logger.info("启动异步资产加载…")
        asyncio.create_task(self._load_assets_async())

        # Load cameras from remote scene.
        cameras = await self.remote_scene. get_cameras()
        viewport_camera_index = await self.remote_scene.get_active_camera()
        self.on_cameras_changed(cameras, viewport_camera_index)

    def stop_viewport_main_loop(self):
        """停止viewport主循环"""
        try:
            if hasattr(self, '_viewport_widget') and self._viewport_widget:
                logger.info("停止 viewport 主循环…")
                self._viewport_widget.stop_viewport_main_loop()
                logger.info("Viewport 主循环已停止")
        except Exception as e:
            logger.exception("停止 viewport 主循环失败: %s", e)

    async def cleanup_viewport_resources(self):
        """清理viewport相关资源"""
        try:
            logger.info("清理 viewport 资源…")

            # 停止viewport主循环
            self.stop_viewport_main_loop()

            # 等待viewport完全停止
            await asyncio.sleep(1)

            # 清理viewport对象
            if hasattr(self, '_viewport_widget') and self._viewport_widget:
                # 确保主循环已停止
                self._viewport_widget.stop_viewport_main_loop()

                # 等待一下让循环自然结束
                await asyncio.sleep(0.5)

                # 清理viewport对象
                del self._viewport_widget
                self._viewport_widget = None

            logger.info("Viewport 资源清理完成")
        except Exception as e:
            logger.exception("清理 viewport 资源失败: %s", e)

    async def _load_assets_async(self):
        """异步加载资产，不阻塞UI初始化"""
        try:
            logger.info("开始异步加载资产…")
            # 等待一下让服务器完全准备好
            await asyncio.sleep(2)

            # 尝试获取资产，带超时
            assets = await asyncio.wait_for(
                self.remote_scene.get_actor_assets(), 
                timeout=10.0
            )
            await self.asset_browser_widget.set_assets(assets)
            logger.info("资产加载完成，共 %s 个资产", len(assets))
        except asyncio.TimeoutError:
            logger.warning("资产加载超时，使用空列表")
            await self.asset_browser_widget.set_assets([])
        except Exception as e:
            logger.exception("资产加载失败: %s", e)
            await self.asset_browser_widget.set_assets([])

    async def _init_ui(self):
        logger.info("创建工具栏…")
        self.tool_bar = ToolBar()
        layout = QtWidgets.QVBoxLayout(self._tool_bar_area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.tool_bar)

        # 为工具栏添加样式
        self.tool_bar.setStyleSheet("""
            QWidget {
                background-color: #3c3c3c;
                border-bottom: 1px solid #404040;
            }
            QToolButton {
                background-color: #4a4a4a;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 4px;
                margin: 2px;
            }
            QToolButton:hover {
                background-color: #5a5a5a;
                border-color: #666666;
            }
            QToolButton:pressed {
                background-color: #2a2a2a;
            }
        """)
        connect(self.tool_bar.action_start.triggered, self.start_sim)
        connect(self.tool_bar.action_stop.triggered, self.stop_sim)

        self.manipulator_bar = ManipulatorBar()
        layout = QtWidgets.QVBoxLayout(self._manipulator_bar_area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.manipulator_bar)

        # 为工具栏添加样式
        self.manipulator_bar.setStyleSheet("""
            QTreeWidget {
                background-color: #3c3c3c;
                border-bottom: 1px solid #404040;
            }
            QToolButton {
                color: #cccccc;
                background-color: #4a4a4a;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 4px;
                margin: 2px;
            }
            QToolButton:hover {
                background-color: #5a5a5a;
                border-color: #666666;
            }
            QToolButton:pressed {
                background-color: #2a2a2a;
            }
        """)

        connect(self.manipulator_bar.move_button.triggered, self.manipulator_move)
        connect(self.manipulator_bar.rotate_button.triggered, self.manipulator_rotate)
        connect(self.manipulator_bar.scale_button.triggered, self.manipulator_scale)

        logger.info("设置主内容区域…")
        layout = QtWidgets.QVBoxLayout(self._main_content_area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._viewport_widget)

        logger.info("创建场景层次结构…")
        self.actor_outline_model = ActorOutlineModel(self.local_scene)
        self.actor_outline_model.set_root_group(self.local_scene.root_actor)

        self.actor_outline_widget = ActorOutline()
        self.actor_outline_widget.set_actor_model(self.actor_outline_model)

        theme_service = ThemeService()

        panel_icon_color = theme_service.get_color("panel_icon")

        panel = Panel("大纲", self.actor_outline_widget)
        panel.panel_icon = make_icon(":/icons/text_bullet_list_tree", panel_icon_color)
        self.add_panel(panel, "left")

        logger.info("创建属性编辑器…")
        self.actor_editor_widget = ActorEditor()
        panel = Panel("编辑", self.actor_editor_widget)
        panel.panel_icon = make_icon(":/icons/circle_edit", panel_icon_color)
        self.add_panel(panel, "right")

        logger.info("创建资产浏览器…")
        self.asset_browser_widget = AssetBrowser()
        panel = Panel("资产", self.asset_browser_widget)
        panel.panel_icon = make_icon(":/icons/box", panel_icon_color)
        self.add_panel(panel, "bottom")

        logger.info("创建 Copilot 组件…")
        self.copilot_widget = CopilotPanel(self.remote_scene, self)
        # Configure copilot with server settings from config
        self.copilot_widget.set_server_config(
            self.config_service.copilot_server_url(),
            self.config_service.copilot_timeout()
        )
        panel = Panel("小O", self.copilot_widget)
        panel.panel_icon = make_icon(":/icons/chat_sparkle", panel_icon_color)
        self.add_panel(panel, "right")

        logger.info("创建终端组件…")
        # 添加终端组件
        self.terminal_widget = TerminalWidget()
        panel = Panel("终端", self.terminal_widget)
        panel.panel_icon = make_icon(":/icons/window_console", panel_icon_color)
        self.add_panel(panel, "bottom")

        self.camera_selector_widget = CameraSelector()
        panel = Panel("相机", self.camera_selector_widget)
        panel.panel_icon = make_icon(":/icons/camera", panel_icon_color)
        self.add_panel(panel, "left")

        self.menu_bar = QtWidgets.QMenuBar()
        layout = QtWidgets.QVBoxLayout(self._menu_bar_area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.menu_bar)

        # 为菜单栏添加样式
        self.menu_bar.setStyleSheet("""
            QMenuBar {
                background-color: #3c3c3c;
                color: #ffffff;
                border-bottom: 1px solid #404040;
            }
            QMenuBar::item {
                background-color: transparent;
            }
            QMenuBar::item:selected {
                background-color: #4a4a4a;
            }
            QMenuBar::item:pressed {
                background-color: #2a2a2a;
            }
            QMenu {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #404040;
                border-radius: 3px;
            }
            QMenu::item {
                padding: 6px 20px;
            }
            QMenu::item:selected {
                background-color: #4a4a4a;
            }
        """)

        self.menu_file = self.menu_bar.addMenu("文件")
        self.menu_edit = self.menu_bar.addMenu("编辑")
        self.menu_help = self.menu_bar.addMenu("帮助")

        self.action_create_layout = QtGui.QAction("新建布局…", self)
        self.action_create_layout.setShortcut(QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.New))
        self.action_create_layout.setShortcutContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
        connect(self.action_create_layout.triggered, self.create_scene_layout)
        self.addAction(self.action_create_layout)

        self.action_open_layout = QtGui.QAction("打开布局…", self)
        self.action_open_layout.setShortcut(QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.Open))
        self.action_open_layout.setShortcutContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
        connect(self.action_open_layout.triggered, self.open_scene_layout)
        self.addAction(self.action_open_layout)

        self.action_save_layout = QtGui.QAction("保存布局", self)
        self.action_save_layout.setShortcut(QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.Save))
        self.action_save_layout.setShortcutContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
        connect(self.action_save_layout.triggered, self.save_scene_layout)
        self.addAction(self.action_save_layout)

        self.action_save_layout_as = QtGui.QAction("另存为…", self)
        self.action_save_layout_as.setShortcut(QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.SaveAs))
        self.action_save_layout_as.setShortcutContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
        connect(self.action_save_layout_as.triggered, self.save_scene_layout_as)
        self.addAction(self.action_save_layout_as)

        self.action_exit = QtGui.QAction("退出", self)
        connect(self.action_exit.triggered, self.close)

        self.action_about = QtGui.QAction("关于 OrcaLab", self)
        connect(self.action_about.triggered, self.show_about_dialog)

        # 为主窗体设置背景色

        theme = ThemeService()
        bg_color = theme.get_color_hex("bg")
        bg_hover_color = theme.get_color_hex("bg_hover")
        bg_select_color = theme.get_color_hex("button_bg_pressed")
        text_color = theme.get_color_hex("text")
        scrollbar_handle_bg = theme.get_color_hex("scrollbar_handle_bg")
        scrollbar_handle_bg_hover = theme.get_color_hex("scrollbar_handle_bg_hover")
        split_line_color = theme.get_color_hex("split_line")

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                color: {text_color};
            }}



            QTreeView, QListView {{
                outline: none;
                selection-background-color: #404040;
                alternate-background-color: #333333;
            }}
            QTreeView::item, QListView::item {{
                border: none;
                show-decoration-selected: 1;
            }}
            QTreeView::item:selected, QListView::item:selected {{
                background-color: {bg_select_color};
            }}
            QTreeView::item:hover, QListView::item:hover {{
                background-color: {bg_hover_color};
            }}
            QHeaderView::section {{
                color: #ffffff;
                padding: 4px;
            }}



            QScrollBar {{
                background: transparent;
                margin: 0;
                width: 8px;
                width: 8px;
                border: none;
            }}
            QScrollBar::handle {{
                border: 1px solid transparent;
                border-radius: 2px;
                margin: 1px;
            }}
            QScrollBar::handle:vertical {{
                min-width: 4px;
                min-height: 20px;
                background: {scrollbar_handle_bg};
            }}
            QScrollBar::handle:vertical:hover {{
                background: {scrollbar_handle_bg_hover};
            }}

            QScrollBar::handle:horizontal {{
                min-width: 20px;
                min-height: 4px;
                background: {scrollbar_handle_bg};
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {scrollbar_handle_bg_hover};
            }}
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical,
            QScrollBar::add-page:horizontal,
            QScrollBar::sub-page:horizontal {{
            background: transparent;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical,
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {{
            height: 0;
            width: 0;
            }}

            

            QSplitter::handle {{
                background-color: {split_line_color};
            }}
            QSplitter::handle:horizontal {{
                width: 2px;
            }}
            QSplitter::handle:vertical {{
                height: 2px;
            }}
        """)

        # 初始化按钮状态
        self.tool_bar.action_start.setEnabled(True)
        self.tool_bar.action_stop.setEnabled(False)

        # Window actions.

        action_undo = QtGui.QAction("撤销", self)
        action_undo.setShortcut(QtGui.QKeySequence("Ctrl+Z"))
        action_undo.setShortcutContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
        connect(action_undo.triggered, self.undo)

        action_redo = QtGui.QAction("重做", self)
        action_redo.setShortcut(QtGui.QKeySequence("Ctrl+Shift+Z"))
        action_redo.setShortcutContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
        connect(action_redo.triggered, self.redo)

        self.addActions([action_undo, action_redo])

    async def start_sim(self):
        await SimulationRequestBus().start_simulation()

    async def stop_sim(self):
        await SimulationRequestBus().stop_simulation()

    def _disable_edit(self):
        t = QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents
        self.actor_outline_widget.setEnabled(False)
        self.actor_outline_widget.setAttribute(t, True)
        self.actor_editor_widget.setEnabled(False)
        self.actor_editor_widget.setAttribute(t, True)
        self.asset_browser_widget.setEnabled(False)
        self.asset_browser_widget.setAttribute(t, True)
        self.copilot_widget.setEnabled(False)
        self.copilot_widget.setAttribute(t, True)
        self.menu_edit.setEnabled(False)

        self.manipulator_bar.action_scale.setEnabled(False)
    
    def _enable_edit(self):
        t = QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents
        self.actor_outline_widget.setEnabled(True)
        self.actor_outline_widget.setAttribute(t, False)
        self.actor_editor_widget.setEnabled(True)
        self.actor_editor_widget.setAttribute(t, False)
        self.asset_browser_widget.setEnabled(True)
        self.asset_browser_widget.setAttribute(t, False)
        self.copilot_widget.setEnabled(True)
        self.copilot_widget.setAttribute(t, False)
        self.menu_edit.setEnabled(True)

        self.manipulator_bar.action_scale.setEnabled(True)
    
    @override
    async def on_simulation_state_changed(self, old_state: SimulationState, new_state: SimulationState) -> None:
        if new_state == SimulationState.Launching:
            self._disable_edit()
            self.tool_bar.action_start.setEnabled(False)
            self.tool_bar.action_stop.setEnabled(True)

        if new_state == SimulationState.Stopped:
            self._enable_edit()
            self.tool_bar.action_start.setEnabled(True)
            self.tool_bar.action_stop.setEnabled(False)

    @override
    async def on_asset_downloaded(self, file):
        await self.remote_scene.load_package(file)
        assets = await self.remote_scene.get_actor_assets()
        self.asset_browser_widget.set_assets(assets)

    def prepare_file_menu(self):
        self.menu_file.clear()
        self.menu_file.addAction(self.action_open_layout)
        self.menu_file.addAction(self.action_save_layout)
        self.menu_file.addAction(self.action_save_layout_as)
        self.menu_file.addAction(self.action_create_layout)
        self.menu_file.addSeparator()
        self.menu_file.addAction(self.action_exit)

    def _resolve_path(self, path: str | None) -> str | None:
        if not path:
            return None
        try:
            return str(SystemPath(path).expanduser().resolve())
        except Exception:
            return str(path)

    def _is_default_layout(self, path: str | None) -> bool:
        if not path or not self.default_layout_path:
            return False
        try:
            return SystemPath(path).expanduser().resolve() == SystemPath(self.default_layout_path).expanduser().resolve()
        except Exception:
            return False

    def _write_scene_layout_file(self, filename: str):
        root = self.local_scene.root_actor
        scene_layout_dict = self.actor_to_dict(root)

        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(scene_layout_dict, f, indent=4, ensure_ascii=False)
            logger.info("场景布局已保存至 %s", filename)
        except Exception as e:
            logger.exception("保存场景布局失败: %s", e)
        else:
            self.current_layout_path = self._resolve_path(filename)
            self._infer_scene_and_layout_names()
            self._mark_layout_clean()
            logger.debug("_write_scene_layout_file: 保存完成 path=%s", self.current_layout_path)
            self._update_title()

    def save_scene_layout(self):
        if not self.current_layout_path or self._is_default_layout(self.current_layout_path):
            self.save_scene_layout_as()
            return
        self._write_scene_layout_file(self.current_layout_path)

    def save_scene_layout_as(self):
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "保存场景布局",
            self.cwd,
            "布局文件 (*.json);;所有文件 (*)"
        )

        if not filename:
            return
        if not filename.lower().endswith(".json"):
            filename += ".json"

        self._write_scene_layout_file(filename)
        self.cwd = os.path.dirname(filename)

    def actor_to_dict(self, actor: AssetActor | GroupActor):
        def to_list(v):
            lst = v.tolist() if hasattr(v, "tolist") else v
            return lst
        def compact_array(arr):
            return "[" + ",".join(str(x) for x in arr) + "]"

        data = {
            "name": actor.name,
            "path": self.local_scene.get_actor_path(actor)._p,
            "transform": {
                "position": compact_array(to_list(actor.transform.position)),
                "rotation": compact_array(to_list(actor.transform.rotation)),
                "scale": actor.transform.scale,
            }
        }

        if actor.name == "root":
            new_fields = {"version": "1.0"}
            data = {**new_fields, **data}

        if isinstance(actor, AssetActor):
            data["type"] = "AssetActor"
            data["asset_path"] = actor._asset_path

        if isinstance(actor, GroupActor):
            data["type"] = "GroupActor"
            data["children"] = [self.actor_to_dict(child) for child in actor.children]

        return data
    
    async def create_scene_layout(self):
        def select_file():
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "新建场景布局",
            self.cwd,
            "布局文件 (*.json);;所有文件 (*)"
            )
            return filename

        filename =await asyncWrap(select_file)
        
        if not filename:
            return
        if not filename.lower().endswith(".json"):
            filename += ".json"
        
        if not await asyncWrap(self._confirm_discard_changes):
            return
        
        helper = SceneLayoutHelper(self.local_scene)
        helper.create_empty_layout(filename)

        await helper.clear_layout()

        self.cwd = os.path.dirname(filename)
        self.current_layout_path = filename
        self._infer_scene_and_layout_names()
        self._mark_layout_clean()
        self._update_title()
        logger.debug("create_scene_layout: 用户新建布局 path=%s", filename)
        self.undo_service.command_history = []
        self.undo_service.command_history_index = -1

    def open_scene_layout(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "打开场景布局",
            self.cwd,
            "布局文件 (*.json);;所有文件 (*)"
        )
        if not filename:
            return
        if not self._confirm_discard_changes():
            return
        self.load_scene_layout_sig.emit(filename)
        self.cwd = os.path.dirname(filename)
        self._infer_scene_and_layout_names()
        self._mark_layout_clean()
        self._update_title()
        logger.debug("open_scene_layout: 用户打开 path=%s", filename)

    async def load_scene_layout(self, filename):
        resolved = self._resolve_path(filename)
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.exception("读取场景布局文件失败: %s", e)
            return

        await self.clear_scene_layout(self.local_scene.root_actor)
        await self.create_actor_from_scene_layout(data)
        self.current_layout_path = resolved
        self._infer_scene_and_layout_names()
        self._mark_layout_clean()
        self._update_title()
        self.undo_service.command_history = []
        self.undo_service.command_history_index = -1

    async def clear_scene_layout(self, actor):
        if isinstance(actor, GroupActor):
            for child_actor in actor.children:
                await self.clear_scene_layout(child_actor)
        if actor != self.local_scene.root_actor:
            await SceneEditRequestBus().delete_actor(actor)
        
        await SceneEditRequestBus().set_selection([], undo=False)


    async def create_actor_from_scene_layout(self, actor_data, parent: GroupActor = None):
        name = actor_data["name"]
        actor_type = actor_data.get("type", "BaseActor")
        if actor_type == "AssetActor":
            asset_path = actor_data.get("asset_path", "")
            actor = AssetActor(name=name, asset_path=asset_path)
        else:
            actor = GroupActor(name=name)

        transform_data = actor_data.get("transform", {})
        position = np.array(ast.literal_eval(transform_data["position"]), dtype=float).reshape(3)
        rotation = np.array(ast.literal_eval(transform_data["rotation"]), dtype=float)
        scale = transform_data.get("scale", 1.0)
        transform = Transform(position, rotation, scale)
        actor.transform = transform

        if name == "root":
            actor = self.local_scene.root_actor
        else:
            await SceneEditRequestBus().add_actor(actor=actor, parent_actor=parent)

        if isinstance(actor, GroupActor):
            for child_data in actor_data.get("children", []):
                await self.create_actor_from_scene_layout(child_data, actor)
        self._layout_modified = True
        self._update_title()
        logger.debug("create_actor_from_scene_layout: 标记布局已修改")

    def prepare_edit_menu(self):
        self.menu_edit.clear()

        action_undo = self.menu_edit.addAction("撤销")
        action_undo.setEnabled(can_undo())
        connect(action_undo.triggered, self.undo)

        action_redo = self.menu_edit.addAction("重做")
        action_redo.setEnabled(can_redo())
        connect(action_redo.triggered, self.redo)

    def prepare_help_menu(self):
        self.menu_help.clear()
        self.menu_help.addAction(self.action_about)

    def show_about_dialog(self):
        version = self.config_service._get_package_version()
        
        about_html = f"""
        <div style="font-family: Arial, sans-serif;">
            <h2 style="color: #007acc; margin-bottom: 10px;">OrcaLab</h2>
            <p style="margin: 5px 0;"><b>版本:</b> {version}</p>
            <p style="margin: 5px 0;"><b>版权所有:</b> © 2026 松应科技</p>
            <p style="margin: 5px 0;">
                <b>公司主页:</b> 
                <a href="http://www.orca3d.cn" 
                   style="color: #007acc; text-decoration: none;">
                   http://www.orca3d.cn
                </a>
            </p>
            <p style="margin: 5px 0;">
                <b>GitHub 仓库:</b> 
                <a href="https://github.com/openverse-orca/OrcaLab" 
                   style="color: #007acc; text-decoration: none;">
                   https://github.com/openverse-orca/OrcaLab
                </a>
            </p>
            <p style="margin: 15px 0 5px 0; color: #666; font-size: 11px;">
                云原生机器人仿真平台，提供先进的UI和资产管理功能
            </p>
        </div>
        """
        
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setWindowTitle("关于 OrcaLab")
        msg_box.setTextFormat(QtCore.Qt.TextFormat.RichText)
        msg_box.setText(about_html)
        msg_box.setIconPixmap(QtGui.QPixmap())
        msg_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #2b2b2b;
            }
            QMessageBox QLabel {
                color: #ffffff;
                background-color: #2b2b2b;
            }
            QPushButton {
                background-color: #007acc;
                color: #ffffff;
                border: none;
                border-radius: 3px;
                padding: 6px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
            QPushButton:pressed {
                background-color: #004578;
            }
        """)
        
        msg_box.exec()

    async def undo(self):
        if can_undo():
            await self.undo_service.undo()

    async def redo(self):
        if can_redo():
            await self.undo_service.redo()

    async def get_transform_and_add_item(self, asset_name, x, y):
        t = await self.remote_scene.get_generate_pos(x, y)
        await self.add_item_to_scene_with_transform(asset_name, asset_name, transform=t)

    @override
    async def add_item_to_scene(self, item_name, parent_actor=None, output: List[AssetActor] = None) -> None:
        if parent_actor is None:
            parent_path = Path.root_path()
        else:
            parent_path = self.local_scene.get_actor_path(parent_actor)

        name = make_unique_name(item_name, parent_path)
        try:
            actor = AssetActor(name=name, asset_path=item_name)
        except Exception as e:
            logger.exception("创建 AssetActor 失败: %s", e)
            actor = None
            return
        await SceneEditRequestBus().add_actor(actor, parent_path)
        if output is not None:
            output.append(actor)

    @override
    async def add_item_to_scene_with_transform(self, item_name, item_asset_path, parent_path=None, transform=None, output: List[AssetActor] = None) -> None:
        if parent_path is None:
            parent_path = Path.root_path()

        name = make_unique_name(item_name, parent_path)
        actor = AssetActor(name=name, asset_path=item_asset_path)
        actor.transform = transform
        await SceneEditRequestBus().add_actor(actor, parent_path)
        if output is not None:
            output.append(actor)

    async def on_copilot_add_group(self, group_path: Path):
        group_actor = GroupActor(name=group_path.name())
        await SceneEditRequestBus().add_actor(group_actor, group_path.parent())

    async def add_item_drag(self, item_name, transform):
        name = make_unique_name(item_name, Path.root_path())
        actor = AssetActor(name=name, asset_path=item_name)

        pos = np.array([transform.pos[0], transform.pos[1], transform.pos[2]])
        quat = np.array(
            [transform.quat[0], transform.quat[1], transform.quat[2], transform.quat[3]]
        )
        scale = transform.scale
        actor.transform = Transform(pos, quat, scale)

        await SceneEditRequestBus().add_actor(actor, Path.root_path())

    async def render_thumbnail(self, asset_paths: list[str]):
        await ThumbnailRenderRequestBus().render_thumbnail(asset_paths)

    async def cleanup(self):
        if self._cleanup_completed:
            logger.info("cleanup: 已完成，直接返回")
            return
        logger.info("cleanup: 清理主窗口资源开始")
        logger.debug("cleanup: 当前连接状态 - actor_outline_widget=%s", getattr(self, 'actor_outline_widget', None) is not None)
        try:
            # 1. 首先停止viewport主循环，避免事件循环问题
            await self.cleanup_viewport_resources()

            # 2. 停止仿真进程
            await self.stop_sim()

            # 3. 断开总线连接
            self.disconnect_buses()

            # 4. 清理远程场景（这会终止服务器进程）
            if hasattr(self, 'remote_scene'):
                logger.info("cleanup: 调用 remote_scene.destroy_grpc()…")
                await self.remote_scene.destroy_grpc()
                logger.info("cleanup: remote_scene.destroy_grpc() 完成")

            # 5. 停止URL服务器
            if hasattr(self, 'url_server'):
                await self.url_server.stop()

            # 6. 强制垃圾回收
            import gc
            gc.collect()

            logger.info("cleanup: 主窗口清理完成")
            self._cleanup_completed = True
        except Exception as e:
            logger.exception("清理过程中出现错误: %s", e)
            self._cleanup_completed = True
        finally:
            self._cleanup_in_progress = False

    def closeEvent(self, event):
        """Handle window close event"""
        logger.info("Window close 事件触发 (cleanup_in_progress=%s, layout_modified=%s)", getattr(self, '_cleanup_in_progress', False), self._layout_modified)

        if self._cleanup_completed:
            logger.debug("closeEvent: 清理已完成，接受关闭")
            event.accept()
            return

        if not self._confirm_discard_changes():
            logger.debug("closeEvent: 用户取消关闭")
            event.ignore()
            return

        # Check if we're already in cleanup process to avoid infinite loop
        if hasattr(self, '_cleanup_in_progress') and self._cleanup_in_progress:
            logger.info("清理进行中，接受关闭事件")
            event.accept()
            return

        # Mark cleanup as in progress
        self._cleanup_in_progress = True

        # Ignore the close event initially
        event.ignore()

        # Schedule cleanup to run in the event loop and wait for it
        async def cleanup_and_close():
            try:
                logger.debug("cleanup_and_close: 开始执行 cleanup")
                await self.cleanup()
                logger.info("cleanup_and_close: 清理完成，调用 QApplication.quit()")
                # Use QApplication.quit() instead of self.close() to avoid triggering closeEvent again
                QtWidgets.QApplication.quit()
            except Exception as e:
                logger.exception("清理过程中出现错误: %s", e)
                # Close anyway if cleanup fails
                QtWidgets.QApplication.quit()

        logger.debug("closeEvent: 创建 cleanup_and_close 任务")
        # Create and run the cleanup task
        asyncio.create_task(cleanup_and_close())
        # cleanup will reset the flag; ensure we don't re-enter before task completes
        # event remains ignored; QApplication.quit will drive shutdown

    #
    # ApplicationRequestBus overrides
    #

    @override
    def get_local_scene(self, output: List[LocalScene]):
        output.append(self.local_scene)

    @override
    def get_remote_scene(self, output: List[RemoteScene]):
        output.append(self.remote_scene)

    @override
    def get_widget(self, name: str, output: List[Any]):
        if name == "terminal":
            output.append(self.terminal_widget)

        return

    #
    # UserEventRequestBus overrides
    #

    @override
    def queue_mouse_event(self, x, y, button, action):
        # print(f"Mouse event at ({x}, {y}), button: {button}, action: {action}")
        asyncio.create_task(self.remote_scene.queue_mouse_event(x, y, button.value, action.value))

    @override
    def queue_mouse_wheel_event(self, delta):
        # print(f"Mouse wheel event, delta: {delta}")
        asyncio.create_task(self.remote_scene.queue_mouse_wheel_event(delta))

    @override
    def queue_key_event(self, key, action):
        # print(f"Key event, key: {key}, action: {action}")
        asyncio.create_task(self.remote_scene.queue_key_event(key.value, action.value))

    #
    # CameraRequestBus overrides
    #
    @override
    async def set_viewport_camera(self, camera_index: int) -> None:
        await self.remote_scene.set_active_camera(camera_index)
        CameraNotificationBus().on_viewport_camera_changed(camera_index)

    #
    # CameraNotificationBus overrides
    #
    @override
    def on_cameras_changed(self, cameras: List[CameraBrief], viewport_camera_index: int) -> None:
        self.camera_selector_widget.set_cameras(cameras, viewport_camera_index)

    def _mark_layout_clean(self):
        self._layout_modified = False
        self._update_title()

    def _infer_scene_and_layout_names(self):
        level_info = self.config_service.current_level_info()
        self._current_scene_name = None
        if level_info:
            name = level_info.get("name") or level_info.get("path")
            self._current_scene_name = name

        if self.current_layout_path:
            self._current_layout_name = SystemPath(self.current_layout_path).stem
        else:
            self._current_layout_name = None

    def _update_title(self):
        scene_part = self._current_scene_name or "Unknown Scene"
        layout_part = self._current_layout_name or "Unsaved Layout"
        if self._layout_modified:
            layout_label = f"[* {layout_part}]"
        else:
            layout_label = f"[{layout_part}]"
        self.setWindowTitle(f"{self._base_title}    [{scene_part}]    {layout_label}")

    def _confirm_discard_changes(self) -> bool:
        if not self._layout_modified:
            return True
        logger.debug("_confirm_discard_changes: 布局已修改，弹窗确认")
        message_box = QtWidgets.QMessageBox(self)
        message_box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        message_box.setWindowTitle("未保存的修改")
        message_box.setText("当前布局有未保存的修改")

        cancel_button = message_box.addButton("取消", QtWidgets.QMessageBox.ButtonRole.RejectRole)
        discard_button = message_box.addButton("放弃修改", QtWidgets.QMessageBox.ButtonRole.DestructiveRole)
        save_button = message_box.addButton("保存修改", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        message_box.setDefaultButton(save_button)

        message_box.exec()
        clicked = message_box.clickedButton()

        if clicked == cancel_button:
            return False
        if clicked == save_button:
            self.save_scene_layout()
            return not self._layout_modified
        # 放弃修改
        logger.debug("_confirm_discard_changes: 用户选择放弃修改，重置状态")
        self._mark_layout_clean()
        return True
    
    async def manipulator_move(self, *args):
        await self.remote_scene.change_manipulator_type(1)

    async def manipulator_rotate(self, *args):
        await self.remote_scene.change_manipulator_type(2)

    async def manipulator_scale(self, *args):
        await self.remote_scene.change_manipulator_type(3)
