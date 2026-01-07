import asyncio
import os
import subprocess
import sys
import logging
from PySide6 import QtCore, QtWidgets, QtGui


from orcalab.application_bus import ApplicationRequestBus
from orcalab.application_util import get_local_scene, get_remote_scene
from orcalab.simulation.simulation_bus import (
    SimulationNotificationBus,
    SimulationRequest,
    SimulationRequestBus,
    SimulationState,
)
from orcalab.ui.launch_dialog import LaunchDialog
from orcalab.ui.terminal_widget import TerminalWidget
from orcalab.config_service import ConfigService
from qasync import asyncWrap

logger = logging.getLogger(__name__)


class SimulationService(SimulationRequest):
    def __init__(self):
        self._sim_process_check_lock = asyncio.Lock()
        self.sim_process_running = False
        self.sim_process: subprocess.Popen | None = None
        self._sim_state = SimulationState.Stopped

    def connect_bus(self):
        SimulationRequestBus.connect(self)

    def disconnect_bus(self):
        SimulationRequestBus.disconnect(self)

    @property
    def terminal(self) -> TerminalWidget:
        terminal = getattr(self, "_terminal", None)
        if isinstance(terminal, TerminalWidget):
            return terminal

        output = []
        ApplicationRequestBus().get_widget("terminal", output)
        if output and isinstance(output[0], TerminalWidget):
            self._terminal = output[0]
            return self._terminal

        raise RuntimeError("Failed to get TerminalWidget")

    @property
    def local_scene(self):
        return get_local_scene()

    @property
    def remote_scene(self):
        return get_remote_scene()

    def show_launch_dialog(self):
        """显示启动对话框（同步版本）"""
        if self.sim_process_running:
            return

        dialog = LaunchDialog()

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

        await self._set_simulation_state(SimulationState.Launching)

        self.config_service = ConfigService()
        program_config = self.config_service.get_external_program_config(program_name)

        if not program_config:
            logger.error("未找到程序配置: %s", program_name)
            await self._set_simulation_state(SimulationState.Failed)
            await self._set_simulation_state(SimulationState.Stopped)
            return

        await self.remote_scene.publish_scene()
        await asyncio.sleep(0.5)
        await self.remote_scene.save_body_transform()
        await self.remote_scene.change_sim_state(True)
        await asyncio.sleep(0.5)

        # 启动外部程序 - 改为在主线程直接启动
        command = program_config.get("command", "python")
        args = []
        for arg in program_config.get("args", []):
            args.append(arg)

        success = await self._start_external_process(command, args)

        if success:
            self.sim_process_running = True

            asyncio.create_task(self._sim_process_check_loop())
            await self.remote_scene.set_sync_from_mujoco_to_scene(True)
            await self._set_simulation_state(SimulationState.Running)

            logger.info("外部程序 %s 启动成功", program_name)
        else:
            logger.error("外部程序 %s 启动失败", program_name)
            self.terminal._append_output(
                f"外部程序 {program_name} 启动失败，请检查命令配置或日志输出。\n"
            )
            try:
                await self.remote_scene.change_sim_state(False)
            except Exception as e:
                logger.exception("回滚模拟状态时发生错误: %s", e)
            finally:
                self.sim_process_running = False
            
            await self._set_simulation_state(SimulationState.Failed)
            await self._set_simulation_state(SimulationState.Stopped)

    async def _on_no_external_program_async(self):
        """无外部程序处理（异步版本）"""

        await self._set_simulation_state(SimulationState.Launching)


        await self.remote_scene.publish_scene()
        await asyncio.sleep(0.5)
        await self.remote_scene.save_body_transform()
        await self.remote_scene.change_sim_state(True)
        await asyncio.sleep(0.5)

        # 启动一个虚拟的等待进程，保持终端活跃状态
        # 使用 sleep 命令创建一个长期运行的进程，这样 _sim_process_check_loop 就不会立即退出
        success = await self._start_external_process(
            sys.executable, ["-c", "import time; time.sleep(99999999)"]
        )

        if success:
            # 设置运行状态
            self.sim_process_running = True
            await self._set_simulation_state(SimulationState.Running)
            asyncio.create_task(self._sim_process_check_loop())
            await self.remote_scene.set_sync_from_mujoco_to_scene(True)

            # 在终端显示提示信息

            self.terminal._append_output("已切换到运行模式，等待外部程序连接...\n")
            self.terminal._append_output("模拟地址: localhost:50051\n")
            self.terminal._append_output("请手动启动外部程序并连接到上述地址\n")
            self.terminal._append_output(
                "注意：当前运行的是虚拟等待进程，可以手动停止\n"
            )
            logger.info("无外部程序模式已启动")
        else:
            logger.error("无外部程序模式启动失败")

    async def _start_external_process(
        self, command: str, args: list
    ):
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
                env=os.environ.copy(),
            )

            # 在terminal_widget中显示启动信息

            self.terminal._append_output(f"启动进程: {' '.join(cmd)}\n")
            self.terminal._append_output(f"工作目录: {os.getcwd()}\n")
            self.terminal._append_output("-" * 50 + "\n")
            logger.info("启动外部程序: %s", " ".join(cmd))

            # 启动输出读取线程
            self._start_output_redirect_thread()

            return True

        except Exception as e:
            logger.exception("启动外部程序失败: %s", e)
            self.terminal._append_output(f"启动进程失败: {str(e)}\n")
            return False

    def _append_line_to_terminal(self, line: str):
        # 使用信号槽机制确保在主线程中更新UI
        QtCore.QMetaObject.invokeMethod(
            self.terminal,
            "_append_output_safe",
            QtCore.Qt.ConnectionType.QueuedConnection,
            QtCore.Q_ARG(str, line),
        )

    def _start_output_redirect_thread(self):
        """启动输出重定向线程"""
        import threading

        def read_output():
            """在后台线程中读取进程输出并重定向到terminal_widget"""
            try:
                while self.sim_process and self.sim_process.poll() is None:
                    assert self.sim_process.stdout is not None
                    line = self.sim_process.stdout.readline()
                    if line:
                        # 使用信号槽机制确保在主线程中更新UI
                        self._append_line_to_terminal(line)
                    else:
                        break

                # 读取剩余输出
                if self.sim_process:
                    assert self.sim_process.stdout is not None
                    remaining_output = self.sim_process.stdout.read()
                    if remaining_output:
                        self._append_line_to_terminal(remaining_output)

                    # 检查进程退出码
                    return_code = self.sim_process.poll()
                    if return_code is not None:
                        self._append_line_to_terminal(
                            f"\n进程退出，返回码: {return_code}\n"
                        )

            except Exception as e:
                self._append_line_to_terminal(f"读取输出时出错: {str(e)}\n")

        # 启动输出读取线程
        self.output_thread = threading.Thread(target=read_output, daemon=True)
        self.output_thread.start()

    async def start_simulation(self) -> None:
        await asyncWrap(self.show_launch_dialog)

    async def stop_simulation(self) -> None:
        await self.stop_sim()

    async def stop_sim(self):
        if not self.sim_process_running:
            return

        async with self._sim_process_check_lock:
            
            await self.remote_scene.set_sync_from_mujoco_to_scene(False)
            self.sim_process_running = False

            # 停止主线程启动的sim_process
            if self.sim_process is not None:
                self.terminal._append_output("\n" + "-" * 50 + "\n")
                self.terminal._append_output("正在停止进程...\n")

                self.sim_process.terminate()
                try:
                    self.sim_process.wait(timeout=5)
                    self.terminal._append_output("进程已正常终止\n")
                except subprocess.TimeoutExpired:
                    self.sim_process.kill()
                    self.sim_process.wait()
                    self.terminal._append_output("进程已强制终止\n")

                self.sim_process = None

            await asyncio.sleep(0.5)
            await self.remote_scene.restore_body_transform()
            await self.remote_scene.publish_scene()
            await self.remote_scene.change_sim_state(self.sim_process_running)

            await self._set_simulation_state(SimulationState.Stopped)

    async def _sim_process_check_loop(self):
        async with self._sim_process_check_lock:
            if not self.sim_process_running:
                return

            # 检查主线程启动的sim_process
            if self.sim_process is not None:
                code = self.sim_process.poll()
                if code is not None:
                    logger.info("外部进程已退出，返回码 %s", code)
                    self.sim_process_running = False
                    await self.remote_scene.set_sync_from_mujoco_to_scene(False)
                    await self.remote_scene.change_sim_state(self.sim_process_running)
                    await self._set_simulation_state(SimulationState.Failed)
                    await self._set_simulation_state(SimulationState.Stopped)
                    return

        frequency = 0.5  # Hz
        await asyncio.sleep(1 / frequency)
        asyncio.create_task(self._sim_process_check_loop())

    async def _set_simulation_state(self, new_state: SimulationState):
        old_state = self._sim_state

        valid_transitions = {
            SimulationState.Stopped: [
                SimulationState.Launching,
            ],
            SimulationState.Launching: [
                SimulationState.Running,
                SimulationState.Failed,
            ],
            SimulationState.Running: [
                SimulationState.Stopped,
                SimulationState.Failed,
            ],
            SimulationState.Failed: [
                SimulationState.Stopped,
            ],
        }

        valid_states = valid_transitions.get(old_state, [])
        if new_state not in valid_states:
            raise ValueError(
                f"Invalid state transition from {old_state} to {new_state}"
            )

        self._sim_state = new_state
        bus = SimulationNotificationBus()
        await bus.on_simulation_state_changed(old_state, new_state)
