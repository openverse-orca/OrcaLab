import logging
import os
import sys
import psutil
from typing import List
from filelock import FileLock, Timeout
import json

from orcalab.config_service import ConfigService
from PySide6 import QtWidgets
from PySide6.QtCore import QTimer


logger = logging.getLogger(__name__)
_global_file_lock = None

def looks_like_orcalab_process(name: str, exe: str, cmdline: str) -> bool:
    """Return True if process metadata suggests it is an OrcaLab instance."""
    if "orcalab" in name or "orcalab" in exe:
        return True

    if "orcalab" not in cmdline:
        return False

    python_markers = ("python", "python3", "pypy")
    module_markers = ("-m orcalab", "orcalab/main", "orcalab/__main__", "orcalab.py")

    is_python = any(marker in cmdline for marker in python_markers)
    is_orcalab = any(marker in cmdline for marker in module_markers)
    
    if is_python and is_orcalab:
        return True

    return False


def is_ghost_process(proc: psutil.Process) -> bool:
    """判断进程是否为无法正常交互的僵尸/残留进程。
    
    exe 有路径但 cmdline 不可访问，说明进程已处于异常状态，无法干扰新实例。
    """
    try:
        proc.exe()
    except psutil.NoSuchProcess:
        return True
    except (psutil.AccessDenied, OSError):
        pass

    try:
        cmdline = proc.cmdline()
    except psutil.NoSuchProcess:
        return True
    except (psutil.AccessDenied, OSError):
        # cmdline 不可读取，进程已无法正常运行
        return True

    return not cmdline


def find_other_orcalab_processes() -> List[psutil.Process]:
    """查找当前之外仍在运行的 OrcaLab 进程"""
    current_pid = os.getpid()
    parent_pid = psutil.Process(current_pid).ppid()
    processes: List[psutil.Process] = []

    for proc in psutil.process_iter(["pid", "name", "cmdline", "exe"]):
        try:
            if proc.pid == current_pid:
                continue
            if proc.pid == parent_pid:
                continue

            if sys.platform == "win32":
                if proc.exe().endswith("Scripts\\orcalab.exe"):
                    continue
            else:
                if proc.exe().endswith("bin/orcalab"):
                    continue

            info = proc.info
            name = (info.get("name") or "").lower()
            exe = (info.get("exe") or "").lower()
            cmdline = " ".join(str(part).lower() for part in info.get("cmdline") or [])

            if not looks_like_orcalab_process(name, exe, cmdline):
                continue

            if is_ghost_process(proc):
                try:
                    proc.kill()
                    logger.info("已清理僵尸进程 PID=%s", proc.pid)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("清理僵尸进程 PID=%s 失败，忽略: %s", proc.pid, exc)
                continue

            processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return processes


def ensure_single_instance():
    """确保不会在同一台机器上启动多个 OrcaLab 实例"""
    existing = find_other_orcalab_processes()
    if not existing:
        return

    details_lines = []
    for proc in existing:
        try:
            cmdline = " ".join(proc.cmdline())
        except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied):
            cmdline = "<unavailable>"
        details_lines.append(f"PID: {proc.pid} | CMD: {cmdline}")

    details_text = "\n".join(details_lines)
    logger.warning("检测到已有 OrcaLab 进程: %s, this pid %s", details_text, os.getpid())

    msg_box = QtWidgets.QMessageBox()
    msg_box.setWindowTitle("检测到正在运行的 OrcaLab 进程")
    msg_box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
    msg_box.setText("当前系统上已存在正在运行的 OrcaLab 实例。")
    msg_box.setInformativeText(
        "OrcaLab 不支持在同一台电脑同时运行多个实例。\n\n"
        "选择\"终止并继续\"将尝试结束所有已发现的 OrcaLab 进程后再继续启动。\n"
        "选择\"退出\"将直接退出当前启动。\n\n"
        "若 5 秒内未操作，将自动终止已有进程并继续启动。"
    )
    msg_box.setDetailedText(details_text or "未获取到进程信息")

    kill_button = msg_box.addButton("终止并继续", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
    exit_button = msg_box.addButton("退出", QtWidgets.QMessageBox.ButtonRole.RejectRole)
    msg_box.setDefaultButton(kill_button)

    countdown_seconds = 5
    kill_button.setText(f"终止并继续（{countdown_seconds}s）")

    def _tick():
        nonlocal countdown_seconds
        countdown_seconds -= 1
        if countdown_seconds <= 0:
            msg_box.accept()
            return
        kill_button.setText(f"终止并继续（{countdown_seconds}s）")

    timer = QTimer()
    timer.timeout.connect(_tick)
    timer.start(1000)
    msg_box.exec()
    timer.stop()

    if msg_box.clickedButton() == exit_button:
        logger.info("用户选择退出，以避免多个 OrcaLab 实例同时运行")
        raise SystemExit(0)

    failed = []
    for proc in existing:
        try:
            logger.info("尝试终止 OrcaLab 进程 PID=%s", proc.pid)
            proc.terminate()
            proc.wait(timeout=5)
        except psutil.NoSuchProcess:
            logger.info("进程 PID=%s 已结束", proc.pid)
            continue
        except psutil.TimeoutExpired:
            logger.warning("进程 PID=%s terminate 超时，尝试强制 kill", proc.pid)
        except psutil.AccessDenied as exc:
            logger.warning("进程 PID=%s terminate 权限不足，尝试强制 kill: %s", proc.pid, exc)
        except Exception as exc:  # noqa: BLE001
            logger.exception("终止进程 PID=%s 时出现异常: %s", proc.pid, exc)
            failed.append(proc.pid)
            continue

        try:
            proc.kill()
            proc.wait(timeout=5)
        except psutil.NoSuchProcess:
            logger.info("进程 PID=%s 已结束", proc.pid)
        except Exception as exc:  # noqa: BLE001
            if is_ghost_process(proc):
                logger.warning("进程 PID=%s 无法终止但已是僵尸进程，忽略: %s", proc.pid, exc)
            else:
                logger.warning("强制 kill 进程 PID=%s 失败: %s", proc.pid, exc)
                failed.append(proc.pid)

    if failed:
        error_box = QtWidgets.QMessageBox()
        error_box.setWindowTitle("无法终止所有 OrcaLab 进程")
        error_box.setIcon(QtWidgets.QMessageBox.Icon.Critical)
        error_box.setText("部分 OrcaLab 进程无法自动终止。")
        error_box.setInformativeText(
            "请手动结束以下进程后重新启动 OrcaLab:\n"
            + ", ".join(str(pid) for pid in failed)
        )
        error_box.exec()
        logger.error("仍有进程未终止，放弃启动: %s", failed)
        raise SystemExit(1)

    logger.info("所有现有 OrcaLab 进程已终止，继续启动")

def format_instance_info(data: dict) -> str:
    def v(key):
        val = data.get(key, "")
        return val if val else "(empty)"
    
    cmdline = data.get("cmdline", [])
    if isinstance(cmdline, list):
        cmdline = " ".join(cmdline)
        
    return "\n".join([
    f"PID: {v('pid')}",
    f"CWD: {v('cwd')}",
    f"CmdLine: {cmdline}",
])

def ensure_single_instance_by_file_lock(config_service: ConfigService):
    global _global_file_lock

    from orcalab.project_util import get_orca_studio_folder, project_id
    lock_path = os.path.join(get_orca_studio_folder(), "orcalab.lock")
    info_path = os.path.join(get_orca_studio_folder(), "orcalab.info")

    try:
        _global_file_lock = FileLock(lock_path, timeout=0)
        _global_file_lock.acquire()
    except Timeout:
        print("已有实例在运行")
        try:
            with open(info_path, "r") as f:
                data = json.load(f)
        except Exception:
            pass
        
        # show_message(format_instance_info(data))
        msg_box = QtWidgets.QMessageBox()
        msg_box.setMinimumSize(800, 600)
        msg_box.setWindowTitle("检测到正在运行的 OrcaLab 进程")
        msg_box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        msg_box.setText("当前系统上已存在正在运行的 OrcaLab 实例。")
        msg_box.setInformativeText(
            "OrcaLab 不支持在同一台电脑同时运行多个实例。\n\n"
            "请根据详细信息关闭已有实例后再继续启动。\n"
        )
        msg_box.setDetailedText(format_instance_info(data))

        exit_button = msg_box.addButton("退出", QtWidgets.QMessageBox.ButtonRole.RejectRole)
        msg_box.setDefaultButton(exit_button)
        msg_box.show()
        msg_box.resize(1500, 500)
        msg_box.exec()
        if msg_box.clickedButton() == exit_button:
            logger.info("用户选择退出，以避免多个 OrcaLab 实例同时运行")
            raise SystemExit(0)
        
        sys.exit(0)
    
    info = {
        "pid": os.getpid(),
        "cwd": os.getcwd(),
        "cmdline": sys.argv,
    }

    with open(info_path, "w") as f:
        json.dump(info, f)

    print("启动成功，PID =", os.getpid())

