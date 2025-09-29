import asyncio
from copy import deepcopy
import random

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

from orcalab.actor import AssetActor, BaseActor, GroupActor
from orcalab.local_scene import LocalScene
from orcalab.path import Path
from orcalab.pyside_util import connect
from orcalab.remote_scene import RemoteScene
from orcalab.ui.actor_editor import ActorEditor
from orcalab.ui.actor_outline import ActorOutline
from orcalab.ui.actor_outline_model import ActorOutlineModel
from orcalab.ui.asset_browser import AssetBrowser
from orcalab.ui.copilot import CopilotPanel
from orcalab.ui.tool_bar import ToolBar
from orcalab.ui.launch_dialog import LaunchDialog
from orcalab.ui.terminal_widget import TerminalWidget
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

        self.undo_service = UndoService()
        self.local_scene = LocalScene()

        self.scene_edit_service = SceneEditService(self.local_scene)

        self.remote_scene = RemoteScene(ConfigService())

        await self.remote_scene.init_grpc()
        await self.remote_scene.set_sync_from_mujoco_to_scene(False)
        await self.remote_scene.set_selection([])
        await self.remote_scene.clear_scene()

        self.cache_folder = await self.remote_scene.get_cache_folder()



        self._sim_process_check_lock = asyncio.Lock()
        self.sim_process_running = False

        self.undo_service.connect_bus()
        self.scene_edit_service.connect_bus()
        self.remote_scene.connect_bus()

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


        self.actor_outline_widget.connect_bus()
        self.actor_outline_model.connect_bus()
        self.actor_editor_widget.connect_bus()

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

        self.sim_process_running = True
        self.disanble_control.emit()
        self._update_button_states()
        if self.local_scene.selection:
            self.actor_editor_widget.actor = None
            self.local_scene.selection = []
            await self.remote_scene.set_selection([])
        await self.remote_scene.change_sim_state(self.sim_process_running)

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


# Add undo/redo functionality
class MainWindow1(MainWindow):

    add_item_by_drag = QtCore.Signal(str, Transform)
    # transform_change = QtCore.Signal(Path, bool)
    load_scene_sig = QtCore.Signal(str)
    # rename_sig = QtCore.Signal(BaseActor, str)

    def __init__(self):
        super().__init__()
        self.cwd = os.getcwd()

    async def init(self):
        await super().init()

        await super()._init_ui()

        connect(self.actor_outline_model.add_item, self.add_item_to_scene)

        connect(self.asset_browser_widget.add_item, self.add_item_to_scene)

        connect(self.copilot_widget.add_item_with_transform, self.add_item_to_scene_with_transform)
        connect(self.copilot_widget.request_add_group, self.on_copilot_add_group)

        connect(self.menu_file.aboutToShow, self.prepare_file_menu)
        connect(self.menu_edit.aboutToShow, self.prepare_edit_menu)

        connect(self.add_item_by_drag, self.add_item_drag)
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
            await SceneEditRequestBus().delete_actor(actor)
    
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

    async def add_item_to_scene(self, item_name, parent_actor=None):
        if parent_actor is None:
            parent_path = Path.root_path()
        else:
            parent_path = self.local_scene.get_actor_path(parent_actor)

        name = make_unique_name(item_name, parent_path)
        actor = AssetActor(name=name, spawnable_name=item_name)
        await SceneEditRequestBus().add_actor(actor, parent_path)

    async def add_item_to_scene_with_transform(self, item_name, item_spawnable_name, parent_path=None, transform=None):
        if parent_path is None:
            parent_path = Path.root_path()

        name = make_unique_name(item_name, parent_path)
        actor = AssetActor(name=name, spawnable_name=item_spawnable_name)
        actor.transform = transform
        await SceneEditRequestBus().add_actor(actor, parent_path)

    async def on_copilot_add_group(self, group_path: Path):
        group_actor = GroupActor(name=group_path.name())
        await SceneEditRequestBus().add_actor(group_actor, group_path.parent())

    async def add_item_drag(self, item_name, transform):
        name = make_unique_name(item_name, Path.root_path())
        actor = AssetActor(name=name, spawnable_name=item_name)

        pos = np.array([transform.pos[0], transform.pos[1], transform.pos[2]])
        quat = np.array(
            [transform.quat[0], transform.quat[1], transform.quat[2], transform.quat[3]]
        )
        scale = transform.scale
        actor.transform = Transform(pos, quat, scale)

        await SceneEditRequestBus().add_actor(actor, Path.root_path())

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
