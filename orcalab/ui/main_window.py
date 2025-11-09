import asyncio
from copy import deepcopy
import random

import sys
from typing import Dict, List, Tuple, override
import numpy as np
import logging

from scipy.spatial.transform import Rotation
import subprocess
import json
import ast
import os
import time
import platform
from pathlib import Path as SystemPath
from PySide6 import QtCore, QtWidgets, QtGui
from PIL import Image

from orcalab.actor import AssetActor, BaseActor, GroupActor
from orcalab.local_scene import LocalScene
from orcalab.path import Path
from orcalab.pyside_util import connect
from orcalab.remote_scene import RemoteScene
from orcalab.ui.actor_editor import ActorEditor
from orcalab.ui.actor_outline import ActorOutline
from orcalab.ui.actor_outline_model import ActorOutlineModel
from orcalab.ui.asset_browser.asset_browser import AssetBrowser
from orcalab.ui.asset_browser.thumbnail_render_bus import ThumbnailRenderRequestBus
from orcalab.ui.copilot import CopilotPanel
from orcalab.ui.image_utils import ImageProcessor
from orcalab.ui.icon_util import make_icon
from orcalab.ui.theme_service import ThemeService
from orcalab.ui.tool_bar import ToolBar
from orcalab.ui.launch_dialog import LaunchDialog
from orcalab.ui.terminal_widget import TerminalWidget
from orcalab.ui.viewport import Viewport
from orcalab.ui.panel_manager import PanelManager
from orcalab.ui.panel import Panel
from orcalab.math import Transform
from orcalab.config_service import ConfigService
from orcalab.undo_service.undo_service import SelectionCommand, UndoService
from orcalab.scene_edit_service import SceneEditService
from orcalab.scene_edit_bus import SceneEditRequestBus, make_unique_name
from orcalab.undo_service.undo_service_bus import can_redo, can_undo
from orcalab.url_service.url_service import UrlServiceServer
from orcalab.asset_service import AssetService
from orcalab.asset_service_bus import (
    AssetServiceNotification,
    AssetServiceNotificationBus,
)
from orcalab.application_bus import ApplicationRequest, ApplicationRequestBus
from orcalab.http_service.http_service import HttpService

from orcalab.ui.user_event_bus import UserEventRequest, UserEventRequestBus


logger = logging.getLogger(__name__)


class MainWindow(PanelManager, ApplicationRequest, AssetServiceNotification, UserEventRequest):

    add_item_by_drag = QtCore.Signal(str, Transform)
    load_scene_layout_sig = QtCore.Signal(str)
    enable_control = QtCore.Signal()
    disanble_control = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.cwd = os.getcwd()
        self._base_title = "orcalab 25.11.2"
        self.config_service = ConfigService()
        self.default_layout_path: str | None = None
        self.current_layout_path: str | None = None
        self._cleanup_in_progress = False
        self._cleanup_completed = False

    def connect_buses(self):
        super().connect_buses()
        ApplicationRequestBus.connect(self)
        AssetServiceNotificationBus.connect(self)
        UserEventRequestBus.connect(self)
        logger.debug("connect_buses: ApplicationRequestBus=%s AssetServiceNotificationBus=%s UserEventRequestBus=%s", True, True, True)

    def disconnect_buses(self):
        UserEventRequestBus.disconnect(self)
        AssetServiceNotificationBus.disconnect(self)
        ApplicationRequestBus.disconnect(self)
        super().disconnect_buses()
        logger.debug("disconnect_buses: 子总线已断开")

    # def start_viewport_main_loop(self):
    #     self._viewport_widget.start_viewport_main_loop()

    async def init(self):
        self.local_scene = LocalScene()
        self.remote_scene = RemoteScene(self.config_service)

        self._sim_process_check_lock = asyncio.Lock()
        self.sim_process_running = False

        self.asset_service = AssetService()

        self.url_server = UrlServiceServer()

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
        self._viewport_widget.init_viewport()

        self._current_scene_name: str | None = None
        self._current_layout_name: str | None = None
        self._layout_modified: bool = False

        logger.info("开始初始化 UI…")
        await self._init_ui()
        logger.info("UI 初始化完成")

        self.resize(1200, 800)
        self.restore_default_layout()
        self.show()

        self._viewport_widget.start_viewport_main_loop()

        # # 启动前检查GPU环境
        # await self._pre_init_gpu_check()

        # # 分阶段初始化viewport，添加错误恢复机制
        # await self._init_viewport_with_retry()

        # 等待viewport完全启动并检查就绪状态
        # print("等待viewport启动...")
        # await asyncio.sleep(5)

        # # 等待viewport就绪状态
        # viewport_ready = await self._wait_for_viewport_ready()
        # if not viewport_ready:
        #     print("警告: Viewport可能未完全就绪，但继续初始化...")

        # 检查GPU状态
        # await self._check_gpu_status()

        # 确保GPU资源稳定后再继续
        # await self._stabilize_gpu_resources()
        # print("Viewport启动完成，继续初始化...")

        # print("连接总线...")

        connect(self.actor_outline_model.add_item, self.add_item_to_scene)

        connect(self.asset_browser_widget.add_item, self.add_item_to_scene)

        connect(self.copilot_widget.add_item_with_transform, self.add_item_to_scene_with_transform)
        connect(self.copilot_widget.request_add_group, self.on_copilot_add_group)

        connect(self.menu_file.aboutToShow, self.prepare_file_menu)
        connect(self.menu_edit.aboutToShow, self.prepare_edit_menu)

        connect(self.add_item_by_drag, self.add_item_drag)
        connect(self.load_scene_layout_sig, self.load_scene_layout)

        connect(self.enable_control, self.enable_widgets)
        connect(self.disanble_control, self.disable_widgets)
        connect(self._viewport_widget.assetDropped, self.get_transform_and_add_item)

        self.actor_outline_widget.connect_bus()
        self.actor_outline_model.connect_bus()
        self.actor_editor_widget.connect_bus()

        self.undo_service.connect_bus()
        self.scene_edit_service.connect_bus()
        self.remote_scene.connect_bus()

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

        # print("UI初始化完成")
        
        # # 启动GPU健康监控
        # print("启动GPU健康监控...")
        # await self._monitor_gpu_health()
        # print("GPU健康监控启动完成")

    async def _init_viewport_with_retry(self, max_retries=3):
        """带重试机制的viewport初始化"""
        for attempt in range(max_retries):
            try:
                logger.info("初始化 viewport（尝试 %s/%s）…", attempt + 1, max_retries)
                
                # 在重试前清理GPU资源
                if attempt > 0:
                    await self._cleanup_gpu_resources()
                    await asyncio.sleep(3)  # 给GPU更多时间恢复
                
                self._viewport_widget = Viewport()
                self._viewport_widget.init_viewport()
                self._viewport_widget.start_viewport_main_loop()
                logger.info("Viewport 初始化成功")
                return
            except Exception as e:
                logger.exception("Viewport 初始化失败（尝试 %s）：%s", attempt + 1, e)
                
                # 检查是否是GPU设备丢失错误
                if "Device lost" in str(e) or "GPU removed" in str(e):
                    logger.warning("检测到 GPU 设备丢失错误，尝试恢复…")
                    await self._handle_gpu_device_lost()
                
                if attempt < max_retries - 1:
                    logger.info("等待 %s 秒后重试…", 2 ** attempt)
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                else:
                    logger.error("Viewport 初始化最终失败，准备抛出异常")
                    raise

    async def _cleanup_gpu_resources(self):
        """清理GPU资源"""
        try:
            logger.info("清理 GPU 资源…")
            # 清理viewport对象
            if hasattr(self, '_viewport_widget') and self._viewport_widget:
                del self._viewport_widget
                self._viewport_widget = None
            
            # 强制垃圾回收
            import gc
            gc.collect()
            
            # 等待GPU资源释放
            await asyncio.sleep(2)
            logger.info("GPU 资源清理完成")
        except Exception as e:
            logger.exception("清理 GPU 资源失败: %s", e)

    async def _handle_gpu_device_lost(self):
        """处理GPU设备丢失"""
        try:
            logger.info("处理 GPU 设备丢失…")
            
            # 检查并重启NVIDIA驱动服务
            await self._restart_nvidia_services()
            
            # 等待GPU恢复
            await asyncio.sleep(5)
            
            logger.info("GPU 设备丢失处理完成")
        except Exception as e:
            logger.exception("处理 GPU 设备丢失失败: %s", e)

    async def _restart_nvidia_services(self):
        """重启NVIDIA相关服务"""
        try:
            logger.info("尝试重启 NVIDIA 服务…")
            import subprocess
            
            # 重启NVIDIA持久化守护进程
            try:
                subprocess.run(['sudo', 'systemctl', 'restart', 'nvidia-persistenced'], 
                             timeout=10, capture_output=True)
                logger.info("NVIDIA 持久化守护进程已重启")
            except Exception as e:
                logger.exception("重启 NVIDIA 持久化守护进程失败: %s", e)
            
            # 重置NVIDIA GPU
            try:
                subprocess.run(['sudo', 'nvidia-smi', '--gpu-reset'], 
                             timeout=10, capture_output=True)
                logger.info("NVIDIA GPU 已重置")
            except Exception as e:
                logger.exception("重置 NVIDIA GPU 失败: %s", e)
                
        except Exception as e:
            logger.exception("重启 NVIDIA 服务失败: %s", e)

    async def _pre_init_gpu_check(self):
        """启动前GPU环境检查"""
        try:
            logger.info("执行启动前 GPU 环境检查…")
            
            # 检查NVIDIA驱动
            await self._check_nvidia_driver()
            
            # 检查GPU可用性
            await self._check_gpu_availability()
            
            # 检查显存状态
            await self._check_vram_status()
            
            logger.info("GPU 环境检查完成")
        except Exception as e:
            logger.exception("GPU 环境检查失败: %s", e)
            logger.warning("继续启动，但可能遇到 GPU 问题")

    async def _check_nvidia_driver(self):
        """检查NVIDIA驱动状态"""
        try:
            import subprocess
            result = subprocess.run(['nvidia-smi'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                logger.info("NVIDIA 驱动正常")
                # 解析驱动版本
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'Driver Version:' in line:
                        logger.info("驱动版本: %s", line.strip())
                        break
            else:
                logger.warning("NVIDIA 驱动可能有问题")
        except Exception as e:
            logger.exception("检查 NVIDIA 驱动失败: %s", e)

    async def _check_gpu_availability(self):
        """检查GPU可用性"""
        try:
            import subprocess
            result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                gpu_info = result.stdout.strip().split('\n')[0]
                logger.info("GPU 信息: %s", gpu_info)
            else:
                logger.warning("无法获取 GPU 信息")
        except Exception as e:
            logger.exception("检查 GPU 可用性失败: %s", e)

    async def _check_vram_status(self):
        """检查显存状态"""
        try:
            import subprocess
            result = subprocess.run(['nvidia-smi', '--query-gpu=memory.used,memory.total', '--format=csv,noheader,nounits'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                memory_info = result.stdout.strip().split('\n')[0]
                used, total = memory_info.split(', ')
                used_mb = int(used)
                total_mb = int(total)
                free_mb = total_mb - used_mb
                usage_percent = (used_mb / total_mb) * 100
                
                logger.info("显存状态: %sMB/%sMB 使用中 (%.1f%%)", used_mb, total_mb, usage_percent)
                logger.info("可用显存: %sMB", free_mb)
                
                if free_mb < 1024:  # 少于1GB可用显存
                    logger.warning("可用显存不足，可能导致 GPU 设备丢失")
                elif usage_percent > 80:
                    logger.warning("显存使用率过高")
            else:
                logger.warning("无法获取显存状态")
        except Exception as e:
            logger.exception("检查显存状态失败: %s", e)

    async def _check_gpu_status(self):
        """检查GPU状态，确保viewport正常运行"""
        try:
            # 检查viewport是否正常响应
            if hasattr(self._viewport_widget, '_viewport') and self._viewport_widget._viewport:
                logger.info("检查 GPU 状态…")
                
                # 给GPU一些时间来稳定
                await asyncio.sleep(2)
                
                # 检查系统GPU状态
                await self._check_system_gpu_status()
                
                logger.info("GPU 状态检查完成")
            else:
                logger.warning("Viewport 对象未正确初始化")
        except Exception as e:
            logger.exception("GPU 状态检查失败: %s", e)
            logger.warning("继续初始化，但 GPU 状态可能不稳定")

    async def _check_system_gpu_status(self):
        """检查系统GPU状态"""
        try:
            import subprocess
            import re
            
            # 检查NVIDIA GPU状态
            try:
                result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.used,memory.total,temperature.gpu', '--format=csv,noheader,nounits'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    gpu_info = result.stdout.strip().split('\n')[0]
                    logger.info("NVIDIA GPU 状态: %s", gpu_info)
                    
                    # 检查显存使用情况
                    memory_match = re.search(r'(\d+)/(\d+)', gpu_info)
                    if memory_match:
                        used_mem = int(memory_match.group(1))
                        total_mem = int(memory_match.group(2))
                        usage_percent = (used_mem / total_mem) * 100
                        logger.info("显存使用率: %.1f%%", usage_percent)
                        
                        if usage_percent > 90:
                            logger.warning("显存使用率过高，可能导致设备丢失")
                else:
                    logger.warning("无法获取 NVIDIA GPU 状态")
            except Exception as e:
                logger.exception("检查 NVIDIA GPU 状态失败: %s", e)
            
            # 检查是否有其他进程占用GPU
            try:
                result = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,process_name,used_memory', '--format=csv,noheader,nounits'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout.strip():
                    logger.info("当前 GPU 进程:\n%s", result.stdout.strip())
                else:
                    logger.info("当前无其他进程占用 GPU")
            except Exception as e:
                logger.exception("检查 GPU 进程失败: %s", e)
                
        except Exception as e:
            logger.exception("系统 GPU 状态检查失败: %s", e)

    async def _wait_for_viewport_ready(self, timeout=10):
        """等待viewport就绪状态"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # 检查viewport是否就绪
                if hasattr(self._viewport_widget, '_viewport_running') and self._viewport_widget._viewport_running:
                    logger.info("Viewport 已就绪")
                    return True
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.exception("检查 viewport 就绪状态时出错: %s", e)
                await asyncio.sleep(0.1)
        
        logger.warning("Viewport 就绪状态检查超时")
        return False

    async def _stabilize_gpu_resources(self):
        """稳定GPU资源，避免资源竞争"""
        try:
            logger.info("稳定 GPU 资源…")
            
            # 给GPU一些额外时间来稳定
            await asyncio.sleep(2)
            
            # 可以在这里添加GPU资源预热操作
            # 例如进行一次简单的渲染操作来确保GPU上下文稳定
            if hasattr(self._viewport_widget, '_viewport') and self._viewport_widget._viewport:
                # 尝试触发一次简单的GPU操作
                try:
                    # 这里可以调用viewport的某个方法来预热GPU
                    logger.info("GPU 资源预热完成")
                except Exception as e:
                    logger.exception("GPU 资源预热失败: %s", e)
            
            logger.info("GPU 资源稳定化完成")
        except Exception as e:
            logger.exception("GPU 资源稳定化过程中出错: %s", e)

    async def _monitor_gpu_health(self):
        """监控GPU健康状态"""
        try:
            # 这里可以添加GPU健康状态监控
            # 例如检查GPU温度、显存使用情况等
            logger.info("GPU 健康状态监控已启动")
            # 立即返回，不阻塞主流程
            return
        except Exception as e:
            logger.exception("GPU 健康状态监控启动失败: %s", e)

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
        connect(self.tool_bar.action_start.triggered, self.show_launch_dialog)
        connect(self.tool_bar.action_stop.triggered, self.stop_sim)

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

        panel = Panel("Scene Hierarchy", self.actor_outline_widget)
        panel.panel_icon = make_icon(":/icons/text_bullet_list_tree", panel_icon_color)
        self.add_panel(panel, "left")

        logger.info("创建属性编辑器…")
        self.actor_editor_widget = ActorEditor()
        panel = Panel("Properties", self.actor_editor_widget)
        panel.panel_icon = make_icon(":/icons/circle_edit", panel_icon_color)
        self.add_panel(panel, "right")

        logger.info("创建资产浏览器…")
        self.asset_browser_widget = AssetBrowser()
        panel = Panel("Assets", self.asset_browser_widget)
        panel.panel_icon = make_icon(":/icons/box", panel_icon_color)
        self.add_panel(panel, "bottom")

        logger.info("创建 Copilot 组件…")
        self.copilot_widget = CopilotPanel(self.remote_scene, self)
        # Configure copilot with server settings from config
        self.copilot_widget.set_server_config(
            self.config_service.copilot_server_url(),
            self.config_service.copilot_timeout()
        )
        panel = Panel("Copilot", self.copilot_widget)
        panel.panel_icon = make_icon(":/icons/chat_sparkle", panel_icon_color)
        self.add_panel(panel, "right")

        logger.info("创建终端组件…")
        # 添加终端组件
        self.terminal_widget = TerminalWidget()
        panel = Panel("Terminal", self.terminal_widget)
        panel.panel_icon = make_icon(":/icons/window_console", panel_icon_color)
        self.add_panel(panel, "bottom")

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
                padding: 2px;
            }
            QMenuBar::item {
                background-color: transparent;
                padding: 4px 8px;
                border-radius: 3px;
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

        # 为主窗体设置背景色
        self.setStyleSheet("""
            QWidget {
                background-color: #181818;
                color: #ffffff;
            }
        """)
        
        # 初始化按钮状态
        logger.info("初始化按钮状态…")
        self._update_button_states()


        # Window actions.

        action_undo = QtGui.QAction("Undo", self)
        action_undo.setShortcut(QtGui.QKeySequence("Ctrl+Z"))
        action_undo.setShortcutContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
        connect(action_undo.triggered, self.undo)

        action_redo = QtGui.QAction("Redo", self)
        action_redo.setShortcut(QtGui.QKeySequence("Ctrl+Shift+Z"))
        action_redo.setShortcutContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
        connect(action_redo.triggered, self.redo)

        self.addActions([action_undo, action_redo])

    def show_launch_dialog(self):
        """显示启动对话框（同步版本）"""
        if self.sim_process_running:
            return
        
        dialog = LaunchDialog(self)
        
        # 连接信号直接到异步处理方法
        dialog.program_selected.connect(self._handle_program_selected_signal)
        dialog.no_external_program.connect(self._handle_no_external_program_signal)
        

        # 直接在主线程中执行对话框
        return dialog.exec()
    
    def _handle_program_selected_signal(self, program_name: str):
        """处理程序选择信号的包装函数"""
        asyncio.create_task(self._on_external_program_selected_async(program_name))
    
    def _handle_no_external_program_signal(self):
        """处理无外部程序信号的包装函数"""
        asyncio.create_task(self._on_no_external_program_async())
    
    async def _on_external_program_selected_async(self, program_name: str):
        """外部程序选择处理（异步版本）"""
        program_config = self.config_service.get_external_program_config(program_name)
        
        if not program_config:
            logger.error("未找到程序配置: %s", program_name)
            return

        await self._before_sim_startup()
        await asyncio.sleep(1)
        
        # 启动外部程序 - 改为在主线程直接启动
        command = program_config.get('command', 'python')
        args = []
        for arg in program_config.get('args', []):
            args.append(arg)
        
        success = await self._start_external_process_in_main_thread_async(command, args)
        
        if success:
            self.sim_process_running = True
            self.disanble_control.emit()
            self._update_button_states()
            
            # 添加缺失的同步操作（从 run_sim 函数中复制）
            await self._complete_sim_startup()
            
            logger.info("外部程序 %s 启动成功", program_name)
        else:
            logger.error("外部程序 %s 启动失败", program_name)
            self.terminal_widget._append_output(f"外部程序 {program_name} 启动失败，请检查命令配置或日志输出。\n")
            try:
                await self.remote_scene.restore_body_transform()
                await self.remote_scene.change_sim_state(False)
            except Exception as e:
                logger.exception("回滚模拟状态时发生错误: %s", e)
            finally:
                self.sim_process_running = False
                self.enable_control.emit()
                self._update_button_states()
    
    async def _before_sim_startup(self):
        # 清除选择状态
        if self.local_scene.selection:
            self.actor_editor_widget.actor = None
            self.local_scene.selection = []
            await self.remote_scene.set_selection([])
        
        # 改变模拟状态
        await self.remote_scene.change_sim_state(True)

        """完成模拟启动的异步操作（从 run_sim 函数中复制的缺失部分）"""
        await self.remote_scene.publish_scene()
        await asyncio.sleep(.1)
        await self.remote_scene.save_body_transform()

    async def _start_external_process_in_main_thread_async(self, command: str, args: list):
        """在主线程中启动外部进程，并将输出重定向到terminal_widget（异步版本）"""
        try:
            # 构建完整的命令
            resolved_command = command
            if command in ("python", "python3"):
                resolved_command = sys.executable or command
            cmd = [resolved_command] + args
            
            # 启动进程，将输出重定向到terminal_widget
            self.sim_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                env=os.environ.copy()
            )
            
            # 在terminal_widget中显示启动信息
            self.terminal_widget._append_output(f"启动进程: {' '.join(cmd)}\n")
            self.terminal_widget._append_output(f"工作目录: {os.getcwd()}\n")
            self.terminal_widget._append_output("-" * 50 + "\n")
            logger.info("启动外部程序: %s", " ".join(cmd))
            
            # 启动输出读取线程
            self._start_output_redirect_thread()
            
            return True
            
        except Exception as e:
            logger.exception("启动外部程序失败: %s", e)
            self.terminal_widget._append_output(f"启动进程失败: {str(e)}\n")
            return False
    
    def _start_output_redirect_thread(self):
        """启动输出重定向线程"""
        import threading
        
        def read_output():
            """在后台线程中读取进程输出并重定向到terminal_widget"""
            try:
                while self.sim_process and self.sim_process.poll() is None:
                    line = self.sim_process.stdout.readline()
                    if line:
                        # 使用信号槽机制确保在主线程中更新UI
                        QtCore.QMetaObject.invokeMethod(
                            self.terminal_widget, "_append_output_safe",
                            QtCore.Qt.ConnectionType.QueuedConnection,
                            QtCore.Q_ARG(str, line)
                        )
                    else:
                        break
                
                # 读取剩余输出
                if self.sim_process:
                    remaining_output = self.sim_process.stdout.read()
                    if remaining_output:
                        QtCore.QMetaObject.invokeMethod(
                            self.terminal_widget, "_append_output_safe",
                            QtCore.Qt.ConnectionType.QueuedConnection,
                            QtCore.Q_ARG(str, remaining_output)
                        )
                    
                    # 检查进程退出码
                    return_code = self.sim_process.poll()
                    if return_code is not None:
                        QtCore.QMetaObject.invokeMethod(
                            self.terminal_widget, "_append_output_safe",
                            QtCore.Qt.ConnectionType.QueuedConnection,
                            QtCore.Q_ARG(str, f"\n进程退出，返回码: {return_code}\n")
                        )
                        
            except Exception as e:
                QtCore.QMetaObject.invokeMethod(
                    self.terminal_widget, "_append_output_safe",
                    QtCore.Qt.ConnectionType.QueuedConnection,
                    QtCore.Q_ARG(str, f"读取输出时出错: {str(e)}\n")
                )
        
        # 启动输出读取线程
        self.output_thread = threading.Thread(target=read_output, daemon=True)
        self.output_thread.start()

    async def _complete_sim_startup(self):
        """完成模拟启动的异步操作（从 run_sim 函数中复制的缺失部分）"""        
        # 启动检查循环
        asyncio.create_task(self._sim_process_check_loop())
        
        # 设置同步状态
        await self.remote_scene.set_sync_from_mujoco_to_scene(True)
    
    async def _on_no_external_program_async(self):
        """无外部程序处理（异步版本）"""

        await self._before_sim_startup()
        await asyncio.sleep(1)

        # 启动一个虚拟的等待进程，保持终端活跃状态
        # 使用 sleep 命令创建一个长期运行的进程，这样 _sim_process_check_loop 就不会立即退出
        success = await self._start_external_process_in_main_thread_async(sys.executable, ["-c", "import time; time.sleep(99999999)"])
        
        if success:
            # 设置运行状态
            self.sim_process_running = True
            self.disanble_control.emit()
            self._update_button_states()
            
            # 添加缺失的同步操作（从 run_sim 函数中复制）
            await self._complete_sim_startup()
            
            # 在终端显示提示信息
            self.terminal_widget._append_output("已切换到运行模式，等待外部程序连接...\n")
            self.terminal_widget._append_output("模拟地址: localhost:50051\n")
            self.terminal_widget._append_output("请手动启动外部程序并连接到上述地址\n")
            self.terminal_widget._append_output("注意：当前运行的是虚拟等待进程，可以手动停止\n")
            logger.info("无外部程序模式已启动")
        else:
            logger.error("无外部程序模式启动失败")

    async def run_sim(self):
        """保留原有的run_sim方法以兼容性"""
        if self.sim_process_running:
            return

        self.sim_process_running = True
        self.disanble_control.emit()
        self._update_button_states()
        if self.local_scene.selection:
            self.actor_editor_widget.actor = None
            self.local_scene.selection = []
            await self.remote_scene.set_selection([])
        await self.remote_scene.change_sim_state(self.sim_process_running)
        await self.remote_scene.publish_scene()
        await asyncio.sleep(.1)
        await self.remote_scene.save_body_transform()

        cmd = [
            "python",
            "-m",
            "orcalab.sim_process",
            "--sim_addr",
            self.remote_scene.sim_grpc_addr,
        ]
        self.sim_process = subprocess.Popen(cmd)
        asyncio.create_task(self._sim_process_check_loop())

        # await asyncio.sleep(2)
        await self.remote_scene.set_sync_from_mujoco_to_scene(True)

    async def stop_sim(self):
        if not self.sim_process_running:
            return

        async with self._sim_process_check_lock:
            await self.remote_scene.publish_scene()
            await self.remote_scene.restore_body_transform()
            await self.remote_scene.set_sync_from_mujoco_to_scene(False)
            self.sim_process_running = False
            self._update_button_states()
            
            # 停止主线程启动的sim_process
            if hasattr(self, 'sim_process') and self.sim_process is not None:
                self.terminal_widget._append_output("\n" + "-" * 50 + "\n")
                self.terminal_widget._append_output("正在停止进程...\n")
                
                self.sim_process.terminate()
                try:
                    self.sim_process.wait(timeout=5)
                    self.terminal_widget._append_output("进程已正常终止\n")
                except subprocess.TimeoutExpired:
                    self.sim_process.kill()
                    self.sim_process.wait()
                    self.terminal_widget._append_output("进程已强制终止\n")
                
                self.sim_process = None
            
            # await asyncio.sleep(0.5)
            await self.remote_scene.restore_body_transform()
            self.enable_control.emit()
            await self.remote_scene.change_sim_state(self.sim_process_running)

    async def _sim_process_check_loop(self):
        async with self._sim_process_check_lock:
            if not self.sim_process_running:
                return

            # 检查主线程启动的sim_process
            if hasattr(self, 'sim_process') and self.sim_process is not None:
                code = self.sim_process.poll()
                if code is not None:
                    logger.info("外部进程已退出，返回码 %s", code)
                    self.sim_process_running = False
                    self._update_button_states()
                    await self.remote_scene.set_sync_from_mujoco_to_scene(False)
                    await self.remote_scene.change_sim_state(self.sim_process_running)
                    self.enable_control.emit()
                    return

        frequency = 0.5  # Hz
        await asyncio.sleep(1 / frequency)
        asyncio.create_task(self._sim_process_check_loop())

    @override
    def get_cache_folder(self, output: list[str]) -> None:
        output.append(self.cache_folder)

    @override
    async def on_asset_downloaded(self, file):
       await self.remote_scene.load_package(file)
       assets = await self.remote_scene.get_actor_assets()
       self.asset_browser_widget.set_assets(assets)


    def prepare_file_menu(self):
        self.menu_file.clear()
        self.menu_file.addAction(self.action_open_layout)
        self.menu_file.addSeparator()
        self.menu_file.addAction(self.action_save_layout)
        self.menu_file.addAction(self.action_save_layout_as)
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

    def open_scene_layout(self, filename: str = None):
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

    async def clear_scene_layout(self, actor):
        if isinstance(actor, GroupActor):
            for child_actor in actor.children:
                await self.clear_scene_layout(child_actor)
        if actor != self.local_scene.root_actor:
            await SceneEditRequestBus().delete_actor(actor)
    
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

        action_undo = self.menu_edit.addAction("Undo")
        action_undo.setEnabled(can_undo())
        connect(action_undo.triggered, self.undo)
        
        action_redo = self.menu_edit.addAction("Redo")
        action_redo.setEnabled(can_redo())
        connect(action_redo.triggered, self.redo)

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


    def enable_widgets(self):
        self.actor_outline_widget.setEnabled(True)
        self.actor_outline_widget.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
        self.actor_editor_widget.setEnabled(True)
        self.actor_editor_widget.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
        self.asset_browser_widget.setEnabled(True)
        self.asset_browser_widget.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
        self.copilot_widget.setEnabled(True)
        self.copilot_widget.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
        # self.terminal_widget.setEnabled(True)
        # self.terminal_widget.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
        self.menu_edit.setEnabled(True)
        self._update_button_states()

    def disable_widgets(self):
        self.actor_outline_widget.setEnabled(False)
        self.actor_outline_widget.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.actor_editor_widget.setEnabled(False)
        self.actor_editor_widget.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.asset_browser_widget.setEnabled(False)
        self.asset_browser_widget.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.copilot_widget.setEnabled(False)
        self.copilot_widget.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        # Terminal widget should remain interactive during simulation
        # self.terminal.setEnabled(False)
        # self.terminal.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.menu_edit.setEnabled(False)
        self._update_button_states()
    
    def _update_button_states(self):
        """更新run和stop按钮的状态"""
        if self.sim_process_running:
            # 运行状态：禁用run按钮，启用stop按钮
            self.tool_bar.action_start.setEnabled(False)
            self.tool_bar.action_stop.setEnabled(True)
        else:
            # 停止状态：启用run按钮，禁用stop按钮
            self.tool_bar.action_start.setEnabled(True)
            self.tool_bar.action_stop.setEnabled(False)
    
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
            if self.sim_process_running:
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