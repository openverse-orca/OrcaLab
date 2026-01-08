import logging
import os
import sys
import psutil
from typing import List

from PySide6 import QtWidgets


logger = logging.getLogger(__name__)


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
        "选择“终止并继续”将尝试结束所有已发现的 OrcaLab 进程后再继续启动。\n"
        "选择“退出”将直接退出当前启动。"
    )
    msg_box.setDetailedText(details_text or "未获取到进程信息")

    kill_button = msg_box.addButton("终止并继续", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
    exit_button = msg_box.addButton("退出", QtWidgets.QMessageBox.ButtonRole.RejectRole)
    msg_box.setDefaultButton(kill_button)
    msg_box.exec()

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
        except (psutil.TimeoutExpired, psutil.AccessDenied) as exc:
            logger.warning("终止进程 PID=%s 失败: %s", proc.pid, exc)
            failed.append(proc.pid)
        except Exception as exc:  # noqa: BLE001
            logger.exception("终止进程 PID=%s 时出现异常: %s", proc.pid, exc)
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

