import asyncio
from copy import deepcopy
import random

from typing import Dict, Tuple, override
import numpy as np

from scipy.spatial.transform import Rotation
import subprocess
import json
import ast
import os
import time
import platform
from PySide6 import QtCore, QtWidgets, QtGui
import PySide6.QtAsyncio as QtAsyncio

from orcalab.actor import AssetActor, BaseActor, GroupActor
from orcalab.local_scene import LocalScene
from orcalab.path import Path
from orcalab.pyside_util import connect
from orcalab.remote_scene import RemoteScene
from orcalab.ui.actor_editor import ActorEditor
from orcalab.ui.actor_outline import ActorOutline
from orcalab.ui.rename_dialog import RenameDialog
from orcalab.ui.actor_outline_model import ActorOutlineModel
from orcalab.ui.asset_browser import AssetBrowser
from orcalab.ui.copilot import CopilotPanel
from orcalab.ui.tool_bar import ToolBar
from orcalab.ui.launch_dialog import LaunchDialog
from orcalab.ui.terminal_widget import TerminalWidget
from orcalab.math import Transform
from orcalab.config_service import ConfigService
from orcalab.url_service.url_service import UrlServiceServer
from orcalab.asset_service import AssetService
from orcalab.asset_service_bus import (
    AssetServiceNotification,
    AssetServiceNotificationBus,
)
from orcalab.application_bus import ApplicationRequest, ApplicationRequestBus

class MainWindow(QtWidgets.QWidget, ApplicationRequest, AssetServiceNotification):

    enable_control = QtCore.Signal()
    disanble_control = QtCore.Signal()

    def __init__(self):
        super().__init__()

    def connect_buses(self):
        ApplicationRequestBus.connect(self)
        AssetServiceNotificationBus.connect(self)

    def disconnect_buses(self):
        AssetServiceNotificationBus.disconnect(self)
        ApplicationRequestBus.disconnect(self)

    async def init(self):

        self.asset_service = AssetService()

        self.url_server = UrlServiceServer()
        await self.url_server.start()

        self.local_scene = LocalScene()

        self.remote_scene = RemoteScene(ConfigService())

        await self.remote_scene.init_grpc()
        await self.remote_scene.set_sync_from_mujoco_to_scene(False)
        await self.remote_scene.set_selection([])
        await self.remote_scene.clear_scene()

        self.cache_folder = await self.remote_scene.get_cache_folder()

        self._query_pending_operation_lock = asyncio.Lock()
        self._query_pending_operation_running = False
        await self._start_query_pending_operation_loop()

        self.start_transform = None
        self.end_transform = None

        self._sim_process_check_lock = asyncio.Lock()
        self.sim_process_running = False

        self.connect_buses()

    async def _init_ui(self):
        self.tool_bar = ToolBar()
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

        self.actor_outline_model = ActorOutlineModel(self.local_scene)
        self.actor_outline_model.set_root_group(self.local_scene.root_actor)

        # 创建带样式的面板
        self.actor_outline_widget = ActorOutline()
        self.actor_outline = self._create_styled_panel("Scene Hierarchy", self.actor_outline_widget)
        self.actor_outline_widget.set_actor_model(self.actor_outline_model)

        self.actor_editor_widget = ActorEditor()
        self.actor_editor = self._create_styled_panel("Properties", self.actor_editor_widget)

        self.asset_browser_widget = AssetBrowser()
        self.asset_browser = self._create_styled_panel("Assets", self.asset_browser_widget)
        assets = await self.remote_scene.get_actor_assets()
        self.asset_browser_widget.set_assets(assets)

        self.copilot_widget = CopilotPanel(self.remote_scene, self)
        # Configure copilot with server settings from config
        config_service = ConfigService()
        self.copilot_widget.set_server_config(
            config_service.copilot_server_url(),
            config_service.copilot_timeout()
        )
        self.copilot = self._create_styled_panel("Copilot", self.copilot_widget)

        # 添加终端组件
        self.terminal_widget = TerminalWidget()
        self.terminal = self._create_styled_panel("Terminal", self.terminal_widget)

        self.menu_bar = QtWidgets.QMenuBar()
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

        layout1 = QtWidgets.QHBoxLayout()
        layout1.setSpacing(8)  # 增加面板间距
        layout1.addWidget(self.actor_outline, 1)
        layout1.addWidget(self.actor_editor, 1)
        layout1.addWidget(self.asset_browser, 1)
        layout1.addWidget(self.copilot, 1)

        # 第二行布局：终端组件
        layout1_2 = QtWidgets.QHBoxLayout()
        layout1_2.setSpacing(8)
        layout1_2.addWidget(self.terminal, 1)

        layout2 = QtWidgets.QVBoxLayout()
        layout2.setContentsMargins(8, 8, 8, 8)  # 设置外边距
        layout2.addWidget(self.menu_bar)
        layout2.addWidget(self.tool_bar)
        layout2.addLayout(layout1)
        layout2.addLayout(layout1_2)

        self.setLayout(layout2)
        
        # 为主窗体设置背景色
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
            }
        """)
        
        # 初始化按钮状态
        self._update_button_states()

    def _create_styled_panel(self, title: str, content_widget: QtWidgets.QWidget) -> QtWidgets.QWidget:
        """创建带标题和样式的面板"""
        # 创建主容器
        panel = QtWidgets.QWidget()
        panel.setObjectName(f"panel_{title.lower().replace(' ', '_')}")
        
        # 设置面板样式
        panel.setStyleSheet(f"""
            QWidget#{panel.objectName()} {{
                background-color: #2b2b2b;
                border: 1px solid #404040;
                border-radius: 4px;
            }}
        """)
        
        # 创建垂直布局
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 创建标题栏
        title_bar = QtWidgets.QLabel(title)
        title_bar.setObjectName("title_bar")
        title_bar.setStyleSheet("""
            QLabel#title_bar {
                background-color: #3c3c3c;
                color: #ffffff;
                padding: 6px 12px;
                border-bottom: 1px solid #404040;
                font-weight: bold;
                font-size: 12px;
            }
        """)
        title_bar.setFixedHeight(28)
        
        # 设置内容区域样式
        content_widget.setStyleSheet("""
            QTreeView, QListView, QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
                border: none;
                selection-background-color: #404040;
                alternate-background-color: #333333;
            }
            QTreeView::item:selected, QListView::item:selected {
                background-color: #404040;
                color: #ffffff;
            }
            QTreeView::item:hover, QListView::item:hover {
                background-color: #353535;
            }
            QHeaderView::section {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #404040;
                padding: 4px;
            }
        """)
        
        # 添加到布局
        layout.addWidget(title_bar)
        layout.addWidget(content_widget)
        
        return panel

    async def _start_query_pending_operation_loop(self):
        async with self._query_pending_operation_lock:
            if self._query_pending_operation_running:
                return
            asyncio.create_task(self._query_pending_operation_loop())
            self._query_pending_operation_running = True

    async def _stop_query_pending_operation_loop(self):
        async with self._query_pending_operation_lock:
            self._query_pending_operation_running = False

    async def _query_pending_operation_loop(self):
        async with self._query_pending_operation_lock:
            if not self._query_pending_operation_running:
                return

            operations = await self.remote_scene.query_pending_operation_loop()
            if not self.sim_process_running:
                for op in operations:
                    await self._process_pending_operation(op)

        # frequency = 30  # Hz
        # await asyncio.sleep(1 / frequency)
        asyncio.create_task(self._query_pending_operation_loop())

    async def _process_pending_operation(self, op: str):
        sltc = "start_local_transform_change:"
        if op.startswith(sltc):
            actor_path = Path(op[len(sltc) :])

            if actor_path not in self.local_scene:
                raise Exception(f"actor not exist")

            actor = self.local_scene[actor_path]
            self.start_transform = actor.transform

        eltc = "end_local_transform_change:"
        if op.startswith(eltc):
            actor_path = Path(op[len(eltc) :])

            if actor_path not in self.local_scene:
                raise Exception(f"actor not exist")

            actor = self.local_scene[actor_path]
            self.end_transform = actor.transform
            self.transform_change.emit(actor_path, True)

        swtc = "start_world_transform_change:"
        if op.startswith(swtc):
            actor_path = Path(op[len(swtc) :])

            if actor_path not in self.local_scene:
                raise Exception(f"actor not exist")

            actor = self.local_scene[actor_path]
            self.start_transform = actor.world_transform

        ewtc = "end_world_transform_change:"
        if op.startswith(ewtc):
            actor_path = Path(op[len(ewtc) :])

            if actor_path not in self.local_scene:
                raise Exception(f"actor not exist")

            actor = self.local_scene[actor_path]
            self.end_transform = actor.world_transform
            self.transform_change.emit(actor_path, False)

        local_transform_change = "local_transform_change:"
        if op.startswith(local_transform_change):
            actor_path = Path(op[len(local_transform_change) :])

            if actor_path not in self.local_scene:
                raise Exception(f"actor not exist")

            transform = await self.remote_scene.get_pending_actor_transform(
                actor_path, True
            )
            self.set_transform_from_scene(actor_path, transform, True)
            await self.remote_scene.set_actor_transform(actor_path, transform, True)

        world_transform_change = "world_transform_change:"
        if op.startswith(world_transform_change):
            actor_path = Path(op[len(world_transform_change) :])

            if not actor_path in self.local_scene:
                raise Exception(f"actor not exist")

            transform = await self.remote_scene.get_pending_actor_transform(
                actor_path, False
            )

            self.set_transform_from_scene(actor_path, transform, False)
            await self.remote_scene.set_actor_transform(actor_path, transform, False)

        selection_change = "selection_change"
        if op.startswith(selection_change):
            actor_paths = await self.remote_scene.get_pending_selection_change()

            paths = []
            for p in actor_paths:
                paths.append(Path(p))

            await self.set_selection_from_remote_scene(paths)

        add_item = "add_item"
        if op.startswith(add_item):
            [transform, name] = await self.remote_scene.get_pending_add_item()
            self.add_item_by_drag.emit(name, transform)

    def show_launch_dialog(self):
        """显示启动对话框（同步版本）"""
        if self.sim_process_running:
            return
        
        dialog = LaunchDialog(self)
        
        # 连接信号直接到异步处理方法
        dialog.program_selected.connect(self._handle_program_selected_signal)
        dialog.no_external_program.connect(self._handle_no_external_program_signal)
        
        # 如果是windows平台
        if platform.system() == "Windows":
            from qasync import asyncWrap
            def show_dialog():
                return dialog.exec()
            asyncWrap(show_dialog)
        else:
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
        """完成模拟启动的异步操作（从 run_sim 函数中复制的缺失部分）"""
        await self.remote_scene.publish_scene()
        await self.remote_scene.save_body_transform()

        # 清除选择状态
        if self.local_scene.selection:
            self.actor_editor_widget.actor = None
            self.local_scene.selection = []
            await self.remote_scene.set_selection([])
        
        # 改变模拟状态
        await self.remote_scene.change_sim_state(True)

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
        success = await self._start_external_process_in_main_thread_async("sleep", ["infinity"])
        
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
        self.sim_process_running = True
        self.disanble_control.emit()
        self._update_button_states()
        if self.local_scene.selection:
            self.actor_editor_widget.actor = None
            self.local_scene.selection = []
            await self.remote_scene.set_selection([])
        await self.remote_scene.change_sim_state(self.sim_process_running)
        asyncio.create_task(self._sim_process_check_loop())

        # await asyncio.sleep(2)
        await self.remote_scene.set_sync_from_mujoco_to_scene(True)

    async def stop_sim(self):
        if not self.sim_process_running:
            return

        async with self._sim_process_check_lock:
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

    async def set_selection(self, actors: list[BaseActor | Path], source: str = ""):
        actors, actor_paths = self.local_scene.get_actor_and_path_list(actors)

        if source != "outline":
            self.actor_outline_widget.set_actor_selection(actors)

        if source != "remote":
            await self.remote_scene.set_selection(actor_paths)

        self.local_scene.selection = actor_paths

        # sync editor
        if len(actors) == 0:
            self.actor_editor_widget.actor = None
        else:
            self.actor_editor_widget.actor = actors[0]

    def make_unique_name(self, base_name: str, parent: BaseActor | Path) -> str:
        parent, _ = self.local_scene.get_actor_and_path(parent)
        assert isinstance(parent, GroupActor)

        existing_names = {child.name for child in parent.children}

        counter = 1
        new_name = f"{base_name}_{counter}"
        while new_name in existing_names:
            counter += 1
            new_name = f"{base_name}_{counter}"

        return new_name

    async def add_actor(self, actor: BaseActor, parent_actor: GroupActor | Path):
        ok, err = self.local_scene.can_add_actor(actor, parent_actor)
        if not ok:
            raise Exception(err)

        parent_actor, parent_actor_path = self.local_scene.get_actor_and_path(
            parent_actor
        )

        model = self.actor_outline_model
        parent_index = model.get_index_from_actor(parent_actor)
        child_count = len(parent_actor.children)

        model.beginInsertRows(parent_index, child_count, child_count)

        self.local_scene.add_actor(actor, parent_actor_path)

        model.endInsertRows()

        await self.remote_scene.add_actor(actor, parent_actor_path)

    async def delete_actor(self, actor) -> Tuple[BaseActor, GroupActor | None]:
        ok, err = self.local_scene.can_delete_actor(actor)
        if not ok:
            return

        actor, actor_path = self.local_scene.get_actor_and_path(actor)

        model = self.actor_outline_model
        index = model.get_index_from_actor(actor)
        parent_index = index.parent()

        model.beginRemoveRows(parent_index, index.row(), index.row())

        self.local_scene.delete_actor(actor)

        model.endRemoveRows()

        await self.remote_scene.delete_actor(actor_path)

    async def rename_actor(self, actor: BaseActor, new_name: str):
        ok, err = self.local_scene.can_rename_actor(actor, new_name)
        if not ok:
            raise Exception(err)

        actor, actor_path = self.local_scene.get_actor_and_path(actor)

        model = self.actor_outline_model
        index = model.get_index_from_actor(actor)

        self.local_scene.rename_actor(actor, new_name)

        model.dataChanged.emit(index, index)

        await self.remote_scene.rename_actor(actor_path, new_name)

    async def reparent_actor(
        self, actor: BaseActor | Path, new_parent: BaseActor | Path, row: int
    ):
        ok, err = self.local_scene.can_reparent_actor(actor, new_parent)
        if not ok:
            raise Exception(err)

        actor, actor_path = self.local_scene.get_actor_and_path(actor)
        new_parent, new_parent_path = self.local_scene.get_actor_and_path(new_parent)

        model = self.actor_outline_model

        model.beginResetModel()
        self.local_scene.reparent_actor(actor, new_parent, row)
        model.endResetModel()

        await self.remote_scene.reparent_actor(actor_path, new_parent_path)

    async def on_transform_edit(self):
        actor = self.actor_editor_widget.actor
        if actor is None:
            return

        transform = self.actor_editor_widget.transform
        if transform is None:
            return

        actor.transform = transform

        actor_path = self.local_scene.get_actor_path(actor)
        if actor_path is None:
            raise Exception("Invalid actor.")

        await self.remote_scene.set_actor_transform(actor_path, transform, True)

    def record_start_transform(self):
        actor = self.actor_editor_widget.actor
        if actor is None:
            return
        self.start_transform = actor.transform

    def record_stop_transform(self):
        actor = self.actor_editor_widget.actor
        if actor is None:
            return
        self.end_transform = actor.transform
        actor_path = self.local_scene.get_actor_path(actor)
        self.transform_change.emit(actor_path, True)

    def set_transform_from_scene(
        self, actor_path: Path, transform: Transform, local: bool
    ):
        actor = self.local_scene[actor_path]

        if local == True:
            actor.transform = transform
        else:
            actor.world_transform = transform

        if self.actor_editor_widget.actor == actor:
            self.actor_editor_widget.update_ui()

    @override
    def get_cache_folder(self, output: list[str]) -> None:
        output.append(self.cache_folder)

    @override
    async def on_asset_downloaded(self, file):
       await self.remote_scene.load_package(file)
       assets = await self.remote_scene.get_actor_assets()
       self.asset_browser_widget.set_assets(assets)


# 不要存Actor对象，只存Path。
# Actor可能被删除和创建，前后的Actor是不相等的。
# DeleteActorCommand中存的Actor不会再次放到LocalScene中，
# 而是作为模板使用。


class SelectionCommand:
    def __init__(self):
        self.old_selection = []
        self.new_selection = []

    def __repr__(self):
        return f"SelectionCommand(old_selection={self.old_selection}, new_selection={self.new_selection})"


class CreateGroupCommand:
    def __init__(self):
        self.path: Path = None

    def __repr__(self):
        return f"CreateGroupCommand(path={self.path})"


class CreateActorCommand:
    def __init__(self):
        self.actor = None
        self.path: Path = None
        self.row = -1

    def __repr__(self):
        return f"CreteActorCommand(path={self.path})"


class DeleteActorCommand:
    def __init__(self):
        self.actor: BaseActor = None
        self.path: Path = None
        self.row = -1

    def __repr__(self):
        return f"DeleteActorCommand(path={self.path})"


class RenameActorCommand:
    def __init__(self):
        self.old_path: Path = None
        self.new_path: Path = None

    def __repr__(self):
        return f"RenameActorCommand(old_path={self.old_path}, new_path={self.new_path})"


class ReparentActorCommand:
    def __init__(self):
        self.old_path = None
        self.old_row = -1
        self.new_path = None
        self.new_row = -1

    def __repr__(self):
        return f"ReparentActorCommand(old_path={self.old_path}, old_row={self.old_row}, new_path={self.new_path}, new_row={self.new_row})"


class TransformCommand:
    def __init__(self):
        self.actor_path = None
        self.old_transform = None
        self.new_transform = None
        self.local = None

    def __repr__(self):
        return f"TransformCommand(actor_path={self.actor_path})"


# Add undo/redo functionality
class MainWindow1(MainWindow):

    add_item_by_drag = QtCore.Signal(str, Transform)
    transform_change = QtCore.Signal(Path, bool)
    load_scene_sig = QtCore.Signal(str)

    def __init__(self):
        super().__init__()

        self.command_history = []
        self.command_history_index = -1
        self.cwd = os.getcwd()

    async def init(self):
        await super().init()

        await super()._init_ui()

        connect(self.actor_outline_model.request_reparent, self.reparent_from_outline)
        connect(self.actor_outline_model.add_item, self.add_item_to_scene)

        connect(
            self.actor_outline_widget.actor_selection_changed,
            self.set_selection_from_outline,
        )
        connect(self.actor_outline_widget.request_add_group, self.add_group_actor_from_outline)
        connect(self.actor_outline_widget.request_delete, self.delete_actor_from_outline)
        connect(self.actor_outline_widget.request_rename, self.open_rename_dialog)

        connect(self.actor_editor_widget.transform_changed, self.on_transform_edit)
        connect(self.actor_editor_widget.start_drag, self.record_start_transform)
        connect(self.actor_editor_widget.stop_drag, self.record_stop_transform)

        connect(self.asset_browser_widget.add_item, self.add_item_to_scene)

        connect(self.copilot_widget.add_item_with_transform, self.add_item_to_scene_with_transform)
        connect(self.copilot_widget.request_add_group, self.on_copilot_add_group)

        connect(self.menu_file.aboutToShow, self.prepare_file_menu)
        connect(self.menu_edit.aboutToShow, self.prepare_edit_menu)

        connect(self.add_item_by_drag, self.add_item_drag)
        connect(self.transform_change, self.transform_change_command)
        connect(self.load_scene_sig, self.load_scene)

        connect(self.enable_control, self.enable_widgets)
        connect(self.disanble_control, self.disable_widgets)

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

        self.resize(800, 400)
        self.show()

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
            },
            "world_transform": {
                "world_position": compact_array(to_list(actor.world_transform.position)),
                "world_rotation": compact_array(to_list(actor.world_transform.rotation)),
                "world_scale": actor.world_transform.scale,
            },
        }

        if actor.name == "root":
            new_fields = {"version": "1.0"}
            data = {**new_fields, **data}

        if isinstance(actor, AssetActor):
            data["type"] = "AssetActor"
            data["spawnable_name"] = actor._spawnable_name
            
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
            await self.delete_actor(actor)
    
    async def create_actor_from_scene(self, actor_data, parent: GroupActor = None):
        name = actor_data["name"]
        actor_type = actor_data.get("type", "BaseActor")
        if actor_type == "AssetActor":
            spawnable_name = actor_data.get("spawnable_name", "")
            actor = AssetActor(name=name, spawnable_name=spawnable_name)
        else:
            actor = GroupActor(name=name)

        transform_data = actor_data.get("transform", {})
        position = np.array(ast.literal_eval(transform_data["position"]), dtype=float).reshape(3)
        rotation = np.array(ast.literal_eval(transform_data["rotation"]), dtype=float)
        scale = transform_data.get("scale", 1.0)
        transform = Transform(position, rotation, scale)
        actor.transform = transform

        world_transform_data = actor_data.get("world_transform", {})
        world_position = np.array(ast.literal_eval(world_transform_data["world_position"]), dtype=float).reshape(3)
        world_rotation = np.array(ast.literal_eval(world_transform_data["world_rotation"]), dtype=float)
        world_scale = world_transform_data.get("scale", 1.0)
        world_transform = Transform(world_position, world_rotation, world_scale)
        actor.world_transform = world_transform
        
        if name == "root":
            actor = self.local_scene.root_actor
        else:
            await self.add_actor(actor=actor, parent_actor=parent)

        if isinstance(actor, GroupActor):
            for child_data in actor_data.get("children", []):
                await self.create_actor_from_scene(child_data, actor)


    def prepare_edit_menu(self):
        self.menu_edit.clear()

        action_undo = self.menu_edit.addAction("Undo")
        connect(action_undo.triggered, self.undo)

        if self.command_history_index >= 0:
            action_undo.setEnabled(True)
        else:
            action_undo.setEnabled(False)

        action_redo = self.menu_edit.addAction("Redo")
        connect(action_redo.triggered, self.redo)

        if self.command_history_index + 1 < len(self.command_history):
            action_redo.setEnabled(True)
        else:
            action_redo.setEnabled(False)

    def add_command(self, command):
        # Remove commands after the current index
        self.command_history = self.command_history[: self.command_history_index + 1]
        self.command_history.append(command)

        self.command_history_index = self.command_history_index + 1

        print(f"Added command: {command}")

    async def undo(self):
        if self.command_history_index < 0:
            return

        command = self.command_history[self.command_history_index]
        self.command_history_index -= 1

        match command:
            case SelectionCommand():
                await self.set_selection(command.old_selection)
            case CreateGroupCommand():
                await self.delete_actor(command.path)
            case CreateActorCommand():
                await self.delete_actor(command.path)
            case DeleteActorCommand():
                actor = command.actor
                parent_path = command.path.parent()
                await self.undo_delete_recursive(actor, parent_path)
            case RenameActorCommand():
                actor, _ = self.local_scene.get_actor_and_path(command.new_path)
                await self.rename_actor(actor, command.old_path.name())
            case ReparentActorCommand():
                actor, _ = self.local_scene.get_actor_and_path(command.new_path)
                old_parent_path = command.old_path.parent()
                await self.reparent_actor(actor, old_parent_path, command.old_row)
            case TransformCommand():
                self.set_transform_from_scene(
                    command.actor_path, command.old_transform, command.local
                )
                await self.remote_scene.set_actor_transform(
                    command.actor_path, command.old_transform, command.local
                )
            case _:
                raise Exception("Unknown command type.")

    async def redo(self):
        if self.command_history_index + 1 >= len(self.command_history):
            return

        command = self.command_history[self.command_history_index + 1]
        self.command_history_index += 1

        match command:
            case SelectionCommand():
                await self.set_selection(command.new_selection)
            case CreateGroupCommand():
                parent = command.path.parent()
                name = command.path.name()
                actor = GroupActor(name=name)
                await self.add_actor(actor, parent)
            case CreateActorCommand():
                parent = command.path.parent()
                actor = deepcopy(command.actor)
                await self.add_actor(actor, parent)
            case DeleteActorCommand():
                await self.delete_actor(command.path)
            case RenameActorCommand():
                actor, _ = self.local_scene.get_actor_and_path(command.old_path)
                await self.rename_actor(actor, command.new_path.name())
            case ReparentActorCommand():
                actor, _ = self.local_scene.get_actor_and_path(command.old_path)
                new_parent_path = command.new_path.parent()
                await self.reparent_actor(actor, new_parent_path, command.new_row)
            case TransformCommand():
                self.set_transform_from_scene(
                    command.actor_path, command.new_transform, command.local
                )
                await self.remote_scene.set_actor_transform(
                    command.actor_path, command.new_transform, command.local
                )
            case _:
                raise Exception("Unknown command type.")

    async def undo_delete_recursive(self, actor: BaseActor, parent_path: Path):
        if isinstance(actor, GroupActor):
            new_actor = GroupActor(name=actor.name)
            new_actor.transform = actor.transform

            await self.add_actor(new_actor, parent_path)

            this_path = parent_path / actor.name
            for child in actor.children:
                await self.undo_delete_recursive(child, this_path)
        else:
            new_actor = deepcopy(actor)
            await self.add_actor(new_actor, parent_path)

    async def add_group_actor_from_outline(self, parent_actor: BaseActor | Path):
        parent_actor, parent_actor_path = self.local_scene.get_actor_and_path(
            parent_actor
        )

        if not isinstance(parent_actor, GroupActor):
            parent_actor = parent_actor.parent
            parent_actor_path = parent_actor_path.parent()

        assert isinstance(parent_actor, GroupActor)

        new_group_name = self.make_unique_name("group", parent_actor)
        actor = GroupActor(name=new_group_name)
        await self.add_actor(actor, parent_actor)

        command = CreateGroupCommand()
        command.path = parent_actor_path / new_group_name
        self.add_command(command)

    async def delete_actor_from_outline(self, actor: BaseActor | Path):
        actor, actor_path = self.local_scene.get_actor_and_path(actor)

        parent_actor = actor.parent
        index = parent_actor.children.index(actor)
        assert index != -1

        command = DeleteActorCommand()
        command.actor = actor
        command.path = actor_path
        command.row = index

        await self.delete_actor(actor)

        self.add_command(command)

    async def set_selection_from_outline(self, actors):
        _, actor_paths = self.local_scene.get_actor_and_path_list(actors)
        if self.local_scene.selection != actor_paths:
            command = SelectionCommand()
            command.new_selection = actor_paths
            command.old_selection = self.local_scene.selection
            self.add_command(command)
            await self.set_selection(actor_paths, "outline")

    async def set_selection_from_remote_scene(self, actor_paths: list[Path]):
        if self.local_scene.selection != actor_paths:
            command = SelectionCommand()
            command.new_selection = actor_paths
            command.old_selection = self.local_scene.selection
            self.add_command(command)
            await self.set_selection(actor_paths, "remote")

    async def reparent_from_outline(
        self, actor: BaseActor | Path, new_parent: BaseActor | Path, row: int
    ):
        actor, actor_path = self.local_scene.get_actor_and_path(actor)
        new_parent, new_parent_path = self.local_scene.get_actor_and_path(new_parent)
        old_parent = actor.parent
        old_index = old_parent.children.index(actor)
        assert old_index != -1

        command = ReparentActorCommand()
        command.old_path = actor_path
        command.old_row = old_index
        command.new_path = new_parent_path / actor.name
        command.new_row = row

        await self.reparent_actor(actor, new_parent, row)
        self.add_command(command)

    async def open_rename_dialog(self, actor: BaseActor):
        actor_path = self.local_scene.get_actor_path(actor)
        if actor_path is None:
            raise Exception("Invalid actor.")

        dialog = RenameDialog(actor_path, self.local_scene.can_rename_actor, self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            new_name = dialog.new_name
            await self.rename_undoable(actor, new_name)

    async def rename_undoable(self, actor: BaseActor | Path, new_name: str):
        _, actor_path = self.local_scene.get_actor_and_path(actor)
        command = RenameActorCommand()
        command.old_path = actor_path
        command.new_path = actor_path.parent() / new_name

        await self.rename_actor(actor, new_name)

        self.add_command(command)

    async def add_item_to_scene(self, item_name, parent_actor=None):
        if parent_actor is None:
            parent_path = Path.root_path()
        else:
            parent_path = self.local_scene.get_actor_path(parent_actor)
        name = self.make_unique_name(item_name, parent_path)
        actor = AssetActor(name=name, spawnable_name=item_name)

        await self.add_actor(actor, parent_path)

        command = CreateActorCommand()
        command.actor = deepcopy(actor)
        command.path = parent_path / name
        self.add_command(command)

    async def add_item_to_scene_with_transform(self, item_name, item_spawnable_name, parent_path=None, transform=None):
        if parent_path is None:
            parent_path = Path.root_path()

        name = self.make_unique_name(item_name, parent_path)
        actor = AssetActor(name=name, spawnable_name=item_spawnable_name)
        actor.transform = transform
        await self.add_actor(actor, parent_path)
        command = CreateActorCommand()
        command.actor = deepcopy(actor)
        command.path = parent_path / name
        self.add_command(command)

    async def on_copilot_add_group(self, group_path: Path):
        group_actor = GroupActor(name=group_path.name())
        await self.add_actor(group_actor, group_path.parent())

        command = CreateGroupCommand()
        command.path = group_path
        self.add_command(command)

    async def add_item_drag(self, item_name, transform):
        name = self.make_unique_name(item_name, Path.root_path())
        actor = AssetActor(name=name, spawnable_name=item_name)

        pos = np.array([transform.pos[0], transform.pos[1], transform.pos[2]])
        quat = np.array(
            [transform.quat[0], transform.quat[1], transform.quat[2], transform.quat[3]]
        )
        scale = transform.scale
        actor.transform = Transform(pos, quat, scale)

        await self.add_actor(actor, Path.root_path())

        command = CreateActorCommand()
        command.actor = deepcopy(actor)
        command.path = Path.root_path() / name
        self.add_command(command)

    async def transform_change_command(self, actor_path, local):
        command = TransformCommand()
        command.actor_path = actor_path
        command.old_transform = self.start_transform
        command.new_transform = self.end_transform
        command.local = local
        self.add_command(command)
        print(command)

    def enable_widgets(self):
        self.actor_outline.setEnabled(True)
        self.actor_outline.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
        self.actor_editor.setEnabled(True)
        self.actor_editor.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
        self.asset_browser.setEnabled(True)
        self.asset_browser.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
        self.copilot.setEnabled(True)
        self.copilot.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
        self.terminal.setEnabled(True)
        self.terminal.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
        self.menu_edit.setEnabled(True)
        self._update_button_states()

    def disable_widgets(self):
        self.actor_outline.setEnabled(False)
        self.actor_outline.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.actor_editor.setEnabled(False)
        self.actor_editor.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.asset_browser.setEnabled(False)
        self.asset_browser.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.copilot.setEnabled(False)
        self.copilot.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
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
            
            # Stop simulation if running
            if self.sim_process_running:
                await self.stop_sim()
            
            # Stop query pending operation loop
            await self._stop_query_pending_operation_loop()
            
            # Disconnect buses
            self.disconnect_buses()
            
            # Clean up remote scene (this will terminate server process)
            if hasattr(self, 'remote_scene'):
                print("MainWindow: Calling remote_scene.destroy_grpc()...")
                await self.remote_scene.destroy_grpc()
                print("MainWindow: remote_scene.destroy_grpc() completed")
            
            # Stop URL server
            if hasattr(self, 'url_server'):
                await self.url_server.stop()
            
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
