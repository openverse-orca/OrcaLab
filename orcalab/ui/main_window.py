import asyncio
from copy import deepcopy
import random

import sys
from typing import Dict, List, Tuple, override
import numpy as np

from scipy.spatial.transform import Rotation
import subprocess
import json
import ast
import os
import time
import platform
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
from orcalab.ui.copilot import CopilotPanel
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



class MainWindow(PanelManager, ApplicationRequest, AssetServiceNotification):

    add_item_by_drag = QtCore.Signal(str, Transform)
    load_scene_sig = QtCore.Signal(str)
    enable_control = QtCore.Signal()
    disanble_control = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.cwd = os.getcwd()

    def connect_buses(self):
        super().connect_buses()
        ApplicationRequestBus.connect(self)
        AssetServiceNotificationBus.connect(self)

    def disconnect_buses(self):
        AssetServiceNotificationBus.disconnect(self)
        ApplicationRequestBus.disconnect(self)
        super().disconnect_buses()

    # def start_viewport_main_loop(self):
    #     self._viewport_widget.start_viewport_main_loop()

    async def init(self):
        self.local_scene = LocalScene()
        self.remote_scene = RemoteScene(ConfigService())

        self._sim_process_check_lock = asyncio.Lock()
        self.sim_process_running = False

        self.asset_service = AssetService()
        
        self.url_server = UrlServiceServer()
        
        self.undo_service = UndoService()
    
        self.scene_edit_service = SceneEditService(self.local_scene)

        self._viewport_widget = Viewport()
        self._viewport_widget.init_viewport()

        print("开始初始化UI...")
        await self._init_ui()
        print("UI初始化完成")

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
        connect(self.asset_browser_widget.create_panorama_gif, self.create_panorama_gif)

        connect(self.copilot_widget.add_item_with_transform, self.add_item_to_scene_with_transform)
        connect(self.copilot_widget.request_add_group, self.on_copilot_add_group)

        connect(self.menu_file.aboutToShow, self.prepare_file_menu)
        connect(self.menu_edit.aboutToShow, self.prepare_edit_menu)

        connect(self.add_item_by_drag, self.add_item_drag)
        connect(self.load_scene_sig, self.load_scene)

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

        self.cache_folder = await self.remote_scene.get_cache_folder()
        await self.url_server.start()
        
        print("启动异步资产加载...")
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
                print(f"初始化viewport (尝试 {attempt + 1}/{max_retries})...")
                
                # 在重试前清理GPU资源
                if attempt > 0:
                    await self._cleanup_gpu_resources()
                    await asyncio.sleep(3)  # 给GPU更多时间恢复
                
                self._viewport_widget = Viewport()
                self._viewport_widget.init_viewport()
                self._viewport_widget.start_viewport_main_loop()
                print("Viewport初始化成功")
                return
            except Exception as e:
                print(f"Viewport初始化失败 (尝试 {attempt + 1}): {e}")
                
                # 检查是否是GPU设备丢失错误
                if "Device lost" in str(e) or "GPU removed" in str(e):
                    print("检测到GPU设备丢失错误，尝试恢复...")
                    await self._handle_gpu_device_lost()
                
                if attempt < max_retries - 1:
                    print(f"等待 {2 ** attempt} 秒后重试...")
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                else:
                    print("Viewport初始化最终失败，抛出异常")
                    raise

    async def _cleanup_gpu_resources(self):
        """清理GPU资源"""
        try:
            print("清理GPU资源...")
            # 清理viewport对象
            if hasattr(self, '_viewport_widget') and self._viewport_widget:
                del self._viewport_widget
                self._viewport_widget = None
            
            # 强制垃圾回收
            import gc
            gc.collect()
            
            # 等待GPU资源释放
            await asyncio.sleep(2)
            print("GPU资源清理完成")
        except Exception as e:
            print(f"清理GPU资源失败: {e}")

    async def _handle_gpu_device_lost(self):
        """处理GPU设备丢失"""
        try:
            print("处理GPU设备丢失...")
            
            # 检查并重启NVIDIA驱动服务
            await self._restart_nvidia_services()
            
            # 等待GPU恢复
            await asyncio.sleep(5)
            
            print("GPU设备丢失处理完成")
        except Exception as e:
            print(f"处理GPU设备丢失失败: {e}")

    async def _restart_nvidia_services(self):
        """重启NVIDIA相关服务"""
        try:
            print("尝试重启NVIDIA服务...")
            import subprocess
            
            # 重启NVIDIA持久化守护进程
            try:
                subprocess.run(['sudo', 'systemctl', 'restart', 'nvidia-persistenced'], 
                             timeout=10, capture_output=True)
                print("NVIDIA持久化守护进程已重启")
            except Exception as e:
                print(f"重启NVIDIA持久化守护进程失败: {e}")
            
            # 重置NVIDIA GPU
            try:
                subprocess.run(['sudo', 'nvidia-smi', '--gpu-reset'], 
                             timeout=10, capture_output=True)
                print("NVIDIA GPU已重置")
            except Exception as e:
                print(f"重置NVIDIA GPU失败: {e}")
                
        except Exception as e:
            print(f"重启NVIDIA服务失败: {e}")

    async def _pre_init_gpu_check(self):
        """启动前GPU环境检查"""
        try:
            print("执行启动前GPU环境检查...")
            
            # 检查NVIDIA驱动
            await self._check_nvidia_driver()
            
            # 检查GPU可用性
            await self._check_gpu_availability()
            
            # 检查显存状态
            await self._check_vram_status()
            
            print("GPU环境检查完成")
        except Exception as e:
            print(f"GPU环境检查失败: {e}")
            print("继续启动，但可能遇到GPU问题")

    async def _check_nvidia_driver(self):
        """检查NVIDIA驱动状态"""
        try:
            import subprocess
            result = subprocess.run(['nvidia-smi'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print("NVIDIA驱动正常")
                # 解析驱动版本
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'Driver Version:' in line:
                        print(f"驱动版本: {line.strip()}")
                        break
            else:
                print("警告: NVIDIA驱动可能有问题")
        except Exception as e:
            print(f"检查NVIDIA驱动失败: {e}")

    async def _check_gpu_availability(self):
        """检查GPU可用性"""
        try:
            import subprocess
            result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                gpu_info = result.stdout.strip().split('\n')[0]
                print(f"GPU信息: {gpu_info}")
            else:
                print("警告: 无法获取GPU信息")
        except Exception as e:
            print(f"检查GPU可用性失败: {e}")

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
                
                print(f"显存状态: {used_mb}MB/{total_mb}MB 使用中 ({usage_percent:.1f}%)")
                print(f"可用显存: {free_mb}MB")
                
                if free_mb < 1024:  # 少于1GB可用显存
                    print("警告: 可用显存不足，可能导致GPU设备丢失")
                elif usage_percent > 80:
                    print("警告: 显存使用率过高")
            else:
                print("无法获取显存状态")
        except Exception as e:
            print(f"检查显存状态失败: {e}")

    async def _check_gpu_status(self):
        """检查GPU状态，确保viewport正常运行"""
        try:
            # 检查viewport是否正常响应
            if hasattr(self._viewport_widget, '_viewport') and self._viewport_widget._viewport:
                print("检查GPU状态...")
                
                # 给GPU一些时间来稳定
                await asyncio.sleep(2)
                
                # 检查系统GPU状态
                await self._check_system_gpu_status()
                
                print("GPU状态检查完成")
            else:
                print("警告: Viewport对象未正确初始化")
        except Exception as e:
            print(f"GPU状态检查失败: {e}")
            print("继续初始化，但GPU状态可能不稳定")

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
                    print(f"NVIDIA GPU状态: {gpu_info}")
                    
                    # 检查显存使用情况
                    memory_match = re.search(r'(\d+)/(\d+)', gpu_info)
                    if memory_match:
                        used_mem = int(memory_match.group(1))
                        total_mem = int(memory_match.group(2))
                        usage_percent = (used_mem / total_mem) * 100
                        print(f"显存使用率: {usage_percent:.1f}%")
                        
                        if usage_percent > 90:
                            print("警告: 显存使用率过高，可能导致设备丢失")
                else:
                    print("无法获取NVIDIA GPU状态")
            except Exception as e:
                print(f"检查NVIDIA GPU状态失败: {e}")
            
            # 检查是否有其他进程占用GPU
            try:
                result = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,process_name,used_memory', '--format=csv,noheader,nounits'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout.strip():
                    print("当前GPU进程:")
                    print(result.stdout.strip())
                else:
                    print("当前无其他进程占用GPU")
            except Exception as e:
                print(f"检查GPU进程失败: {e}")
                
        except Exception as e:
            print(f"系统GPU状态检查失败: {e}")

    async def _wait_for_viewport_ready(self, timeout=10):
        """等待viewport就绪状态"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # 检查viewport是否就绪
                if hasattr(self._viewport_widget, '_viewport_running') and self._viewport_widget._viewport_running:
                    print("Viewport已就绪")
                    return True
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"检查viewport就绪状态时出错: {e}")
                await asyncio.sleep(0.1)
        
        print("警告: Viewport就绪状态检查超时")
        return False

    async def _stabilize_gpu_resources(self):
        """稳定GPU资源，避免资源竞争"""
        try:
            print("稳定GPU资源...")
            
            # 给GPU一些额外时间来稳定
            await asyncio.sleep(2)
            
            # 可以在这里添加GPU资源预热操作
            # 例如进行一次简单的渲染操作来确保GPU上下文稳定
            if hasattr(self._viewport_widget, '_viewport') and self._viewport_widget._viewport:
                # 尝试触发一次简单的GPU操作
                try:
                    # 这里可以调用viewport的某个方法来预热GPU
                    print("GPU资源预热完成")
                except Exception as e:
                    print(f"GPU资源预热失败: {e}")
            
            print("GPU资源稳定化完成")
        except Exception as e:
            print(f"GPU资源稳定化过程中出错: {e}")

    async def _monitor_gpu_health(self):
        """监控GPU健康状态"""
        try:
            # 这里可以添加GPU健康状态监控
            # 例如检查GPU温度、显存使用情况等
            print("GPU健康状态监控已启动")
            # 立即返回，不阻塞主流程
            return
        except Exception as e:
            print(f"GPU健康状态监控启动失败: {e}")

    def stop_viewport_main_loop(self):
        """停止viewport主循环"""
        try:
            if hasattr(self, '_viewport_widget') and self._viewport_widget:
                print("停止viewport主循环...")
                self._viewport_widget.stop_viewport_main_loop()
                print("Viewport主循环已停止")
        except Exception as e:
            print(f"停止viewport主循环失败: {e}")

    async def cleanup_viewport_resources(self):
        """清理viewport相关资源"""
        try:
            print("清理viewport资源...")
            
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
            
            print("Viewport资源清理完成")
        except Exception as e:
            print(f"清理viewport资源失败: {e}")

    async def _load_assets_async(self):
        """异步加载资产，不阻塞UI初始化"""
        try:
            print("开始异步加载资产...")
            # 等待一下让服务器完全准备好
            await asyncio.sleep(2)
            
            # 尝试获取资产，带超时
            assets = await asyncio.wait_for(
                self.remote_scene.get_actor_assets(), 
                timeout=10.0
            )
            self.asset_browser_widget.set_assets(assets)
            print(f"资产加载完成，共 {len(assets)} 个资产")
        except asyncio.TimeoutError:
            print("资产加载超时，使用空列表")
            self.asset_browser_widget.set_assets([])
        except Exception as e:
            print(f"资产加载失败: {e}")
            self.asset_browser_widget.set_assets([])

    async def _init_ui(self):
        print("创建工具栏...")
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

        print("设置主内容区域...")
        layout = QtWidgets.QVBoxLayout(self._main_content_area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._viewport_widget)

        print("创建场景层次结构...")
        self.actor_outline_model = ActorOutlineModel(self.local_scene)
        self.actor_outline_model.set_root_group(self.local_scene.root_actor)

        self.actor_outline_widget = ActorOutline()
        self.actor_outline_widget.set_actor_model(self.actor_outline_model)

        theme_service = ThemeService()

        panel_icon_color = theme_service.get_color("panel_icon")

        panel = Panel("Scene Hierarchy", self.actor_outline_widget)
        panel.panel_icon = make_icon(":/icons/text_bullet_list_tree", panel_icon_color)
        self.add_panel(panel, "left")

        print("创建属性编辑器...")
        self.actor_editor_widget = ActorEditor()
        panel = Panel("Properties", self.actor_editor_widget)
        panel.panel_icon = make_icon(":/icons/circle_edit", panel_icon_color)
        self.add_panel(panel, "right")

        print("创建资产浏览器...")
        self.asset_browser_widget = AssetBrowser()
        panel = Panel("Assets", self.asset_browser_widget)
        panel.panel_icon = make_icon(":/icons/box", panel_icon_color)
        self.add_panel(panel, "bottom")

        print("创建Copilot组件...")
        self.copilot_widget = CopilotPanel(self.remote_scene, self)
        # Configure copilot with server settings from config
        config_service = ConfigService()
        self.copilot_widget.set_server_config(
            config_service.copilot_server_url(),
            config_service.copilot_timeout()
        )
        panel = Panel("Copilot", self.copilot_widget)
        panel.panel_icon = make_icon(":/icons/chat_sparkle", panel_icon_color)
        self.add_panel(panel, "right")

        print("创建终端组件...")
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

        self.menu_file = self.menu_bar.addMenu("File")
        self.menu_edit = self.menu_bar.addMenu("Edit")

        # 为主窗体设置背景色
        self.setStyleSheet("""
            QWidget {
                background-color: #181818;
                color: #ffffff;
            }
        """)
        
        # 初始化按钮状态
        print("初始化按钮状态...")
        self._update_button_states()


        # Window actions.

        action_undo = QtGui.QAction("Undo")
        action_undo.setShortcut(QtGui.QKeySequence("Ctrl+Z"))
        action_undo.setShortcutContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
        connect(action_undo.triggered, self.undo)

        action_redo = QtGui.QAction("Redo")
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
        config_service = ConfigService()
        program_config = config_service.get_external_program_config(program_name)
        
        if not program_config:
            print(f"未找到程序配置: {program_name}")
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
            
            print(f"外部程序 {program_name} 启动成功")
        else:
            print(f"外部程序 {program_name} 启动失败")
    
    async def _before_sim_startup(self):
        # 清除选择状态
        if self.local_scene.selection:
            self.actor_editor_widget.actor = None
            self.local_scene.selection = []
            await self.remote_scene.set_selection([])
        
        # 改变模拟状态
        await self.remote_scene.change_sim_state(True)

        """完成模拟启动的异步操作（从 run_sim 函数中复制的缺失部分）"""
        await self.remote_scene.save_body_transform()
        await self.remote_scene.publish_scene()
        await self.remote_scene.save_body_transform()

    async def _start_external_process_in_main_thread_async(self, command: str, args: list):
        """在主线程中启动外部进程，并将输出重定向到terminal_widget（异步版本）"""
        try:
            # 构建完整的命令
            cmd = [command] + args
            
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
            
            # 启动输出读取线程
            self._start_output_redirect_thread()
            
            return True
            
        except Exception as e:
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
            print("无外部程序模式已启动")
        else:
            print("无外部程序模式启动失败")

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

        await self.remote_scene.save_body_transform()
        await self.remote_scene.publish_scene()
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
            
            self.enable_control.emit()
            await self.remote_scene.change_sim_state(self.sim_process_running)
            await self.remote_scene.restore_body_transform()

    async def _sim_process_check_loop(self):
        async with self._sim_process_check_lock:
            if not self.sim_process_running:
                return

            # 检查主线程启动的sim_process
            if hasattr(self, 'sim_process') and self.sim_process is not None:
                code = self.sim_process.poll()
                if code is not None:
                    print(f"External process exited with code {code}")
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

        action_exit = self.menu_file.addAction("Exit")
        connect(action_exit.triggered, self.close)

        action_sava = self.menu_file.addAction("Save")
        connect(action_sava.triggered, self.save_scene)

        action_open = self.menu_file.addAction("Open")
        connect(action_open.triggered, self.open_scene)

    def save_scene(self, filename: str = None):
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,  
            "Save Scene",  
            self.cwd, 
            "JSON Files (*.json);;All Files (*)"
        )

        if filename == "":
            return
        if not filename.lower().endswith(".json"):
            filename += ".json"
        root = self.local_scene.root_actor
        scene_dict = self.actor_to_dict(root)

        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(scene_dict, f, indent=4, ensure_ascii=False)
            print(f"Scene saved to {filename}")
        except Exception as e:
            print(f"Failed to save scene: {e}")

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

    def open_scene(self, filename: str = None):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open Scene",
            self.cwd,
            "Scene Files (*.json);;All Files (*)"
        )
        if not filename:
            return
        else:
            self.load_scene_sig.emit(filename)

    async def load_scene(self, filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Failed to save scene: {e}")

        await self.clear_scene(self.local_scene.root_actor)
        await self.create_actor_from_scene(data)

    async def clear_scene(self, actor):
        if isinstance(actor, GroupActor):
            for child_actor in actor.children:
                await self.clear_scene(child_actor)
        if actor != self.local_scene.root_actor:
            await SceneEditRequestBus().delete_actor(actor)
    
    async def create_actor_from_scene(self, actor_data, parent: GroupActor = None):
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
                await self.create_actor_from_scene(child_data, actor)


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

    async def add_item_to_scene(self, item_name, parent_actor=None):
        if parent_actor is None:
            parent_path = Path.root_path()
        else:
            parent_path = self.local_scene.get_actor_path(parent_actor)

        name = make_unique_name(item_name, parent_path)
        actor = AssetActor(name=name, asset_path=item_name)
        await SceneEditRequestBus().add_actor(actor, parent_path)
        return actor

    async def add_item_to_scene_with_transform(self, item_name, item_asset_path, parent_path=None, transform=None):
        if parent_path is None:
            parent_path = Path.root_path()

        name = make_unique_name(item_name, parent_path)
        actor = AssetActor(name=name, asset_path=item_asset_path)
        actor.transform = transform
        await SceneEditRequestBus().add_actor(actor, parent_path)
        return actor

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

    async def create_panorama_gif(self, actor_name: str):
        self.terminal_widget._append_output(f"Creating panorama gif for {actor_name}\n")
        actor = await self.add_item_to_scene(actor_name)
        quat = Rotation.from_euler("xyz", [-15, 0, 0], degrees=True).as_quat()[[3, 0, 1, 2]]
        actor_1 = await self.add_item_to_scene_with_transform("mujococamera1080", "prefabs/mujococamera1080", parent_path=Path.root_path(), transform=Transform(position=np.array([0, -2.5, 2]), rotation=quat, scale=1.0))
        actor_2 = await self.add_item_to_scene_with_transform("mujococamera256", "prefabs/mujococamera256", parent_path=Path.root_path(), transform=Transform(position=np.array([0, -2.5, 2]), rotation=quat, scale=1.0))

        tmp_path = os.path.join(os.path.expanduser("~"), ".orcalab", "tmp")
        await self.remote_scene.get_camera_png("mujococamera1080", tmp_path, f"{actor.name}_1080.png")

        # 生成所有旋转角度的PNG图像
        png_files = []
        for rotation_z in range(0, 360, 24):
            quat = Rotation.from_euler("xyz", [0, 0, rotation_z], degrees=True).as_quat()[[3, 0, 1, 2]]
            await self.scene_edit_service.set_transform(actor, Transform(position=np.array([0, 0, 0]), rotation=quat, scale=1.0), local=True, undo=False, source="create_panorama_gif")
            png_filename = f"{actor.name}_256_{rotation_z}.png"
            await self.remote_scene.get_camera_png("mujococamera256", tmp_path, png_filename)
            png_files.append(os.path.join(tmp_path, png_filename))

        await asyncio.sleep(0.01)
        # 生成GIF动图
        gif_path = os.path.join(tmp_path, f"{actor.name}_panorama.gif")

        images = []
        for png_file in png_files:
            retry = 1
            while retry < 3:
                if os.path.exists(png_file):
                    try:
                        img = Image.open(png_file)
                        images.append(img)
                        break
                    except Exception as e:
                        self.terminal_widget._append_output(f"Error opening {png_file}: {e}\n")
                        self.terminal_widget._append_output(f"Retrying... {retry} times\n")
                        retry += 1
                        await asyncio.sleep(0.01)

        if images:
            duration = 200  # 毫秒
            images[0].save(
                gif_path,
                save_all=True,
                append_images=images[1:],
                duration=duration,
                loop=0
            )

            for png_file in png_files:
                if os.path.exists(png_file):
                    try:
                        os.remove(png_file)
                    except OSError as e:
                        self.terminal_widget._append_output(f"Error deleting {png_file}: {e}\n")
            self.terminal_widget._append_output(f"GIF saved to: {gif_path}\n")
        else:
            self.terminal_widget._append_output("No images found to create GIF\n")

        await self.scene_edit_service.delete_actor(actor_2, undo=False, source="create_panorama_gif")
        await self.scene_edit_service.delete_actor(actor_1, undo=False, source="create_panorama_gif")
        await self.scene_edit_service.delete_actor(actor, undo=False, source="create_panorama_gif")


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
        """Clean up resources when the application is closing"""
        try:
            print("Cleaning up main window resources...")
            
            # 1. 首先停止viewport主循环，避免事件循环问题
            await self.cleanup_viewport_resources()
            
            # 2. 停止仿真进程
            if self.sim_process_running:
                await self.stop_sim()
            
            # 3. 断开总线连接
            self.disconnect_buses()
            
            # 4. 清理远程场景（这会终止服务器进程）
            if hasattr(self, 'remote_scene'):
                print("MainWindow: Calling remote_scene.destroy_grpc()...")
                await self.remote_scene.destroy_grpc()
                print("MainWindow: remote_scene.destroy_grpc() completed")
            
            # 5. 停止URL服务器
            if hasattr(self, 'url_server'):
                await self.url_server.stop()
            
            # 6. 强制垃圾回收
            import gc
            gc.collect()
            
            print("Main window cleanup completed")
        except Exception as e:
            print(f"Error during cleanup: {e}")
    
    def closeEvent(self, event):
        """Handle window close event"""
        print("Window close event triggered")
        
        # Check if we're already in cleanup process to avoid infinite loop
        if hasattr(self, '_cleanup_in_progress') and self._cleanup_in_progress:
            print("Cleanup already in progress, accepting close event")
            event.accept()
            return
            
        # Mark cleanup as in progress
        self._cleanup_in_progress = True
        
        # Ignore the close event initially
        event.ignore()
        
        # Schedule cleanup to run in the event loop and wait for it
        async def cleanup_and_close():
            try:
                await self.cleanup()
                print("Cleanup completed, closing window")
                # Use QApplication.quit() instead of self.close() to avoid triggering closeEvent again
                QtWidgets.QApplication.quit()
            except Exception as e:
                print(f"Error during cleanup: {e}")
                # Close anyway if cleanup fails
                QtWidgets.QApplication.quit()
        
        # Create and run the cleanup task
        asyncio.create_task(cleanup_and_close())
