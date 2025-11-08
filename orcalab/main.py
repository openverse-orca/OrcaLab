import argparse
import asyncio
import sys
import signal
import logging

from orcalab.config_service import ConfigService
from orcalab.project_util import check_project_folder, copy_packages, sync_pak_urls
from orcalab.asset_sync_ui import run_asset_sync_ui
from orcalab.url_service.url_util import register_protocol
from orcalab.ui.main_window import MainWindow
from orcalab.logging_util import setup_logging, resolve_log_level

import os

# import PySide6.QtAsyncio as QtAsyncio
from PySide6 import QtWidgets

from qasync import QEventLoop
from orcalab.python_project_installer import ensure_python_project_installed

import psutil

# Global variable to store main window instance for cleanup
_main_window = None

logger = logging.getLogger(__name__)


def parse_cli_args():
    parser = argparse.ArgumentParser(
        prog="orcalab",
        description=(
            "OrcaLab 启动器\n\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-l",
        "--log-level",
        dest="log_level",
        metavar="LEVEL",
        help="控制台日志等级（支持 DEBUG/INFO/WARNING/ERROR/CRITICAL），默认输出 WARNING 及以上，日志文件会记录 INFO 及以上的全部日志。",
    )

    args, remaining = parser.parse_known_args()
    sys.argv = [sys.argv[0]] + remaining
    return args


def signal_handler(signum, frame):
    """Handle system signals to ensure cleanup"""
    logger.info("Received signal %s, cleaning up...", signum)
    if _main_window is not None:
        try:
            # Try to run cleanup in the event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(_main_window.cleanup())
        except Exception as e:
            logger.exception("Error during signal cleanup: %s", e)
    sys.exit(0)


def register_signal_handlers():
    """Register signal handlers for graceful shutdown"""
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination signal
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, signal_handler)  # Hangup signal


def _looks_like_orcalab_process(name: str, exe: str, cmdline: str) -> bool:
    """Return True if process metadata suggests it is an OrcaLab instance."""
    if "orcalab" in name or "orcalab" in exe:
        return True

    if "orcalab" not in cmdline:
        return False

    # Only treat as OrcaLab if it's a Python process or directly invokes the orcalab module
    python_markers = ("python", "python3", "pypy")
    module_markers = ("-m orcalab", "orcalab/main", "orcalab/__main__", "orcalab.py")

    if any(marker in cmdline for marker in python_markers):
        return True

    if any(marker in cmdline for marker in module_markers):
        return True

    return False


def _find_other_orcalab_processes() -> list[psutil.Process]:
    """查找当前之外仍在运行的 OrcaLab 进程"""
    current_pid = os.getpid()
    processes: list[psutil.Process] = []

    for proc in psutil.process_iter(["pid", "name", "cmdline", "exe"]):
        try:
            if proc.pid == current_pid:
                continue

            info = proc.info
            name = (info.get("name") or "").lower()
            exe = (info.get("exe") or "").lower()
            cmdline = " ".join(str(part).lower() for part in info.get("cmdline") or [])

            # Skip helper processes that reference OrcaLab only in arguments
            if not _looks_like_orcalab_process(name, exe, cmdline):
                continue

            processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return processes


def _ensure_single_instance():
    """确保不会在同一台机器上启动多个 OrcaLab 实例"""
    existing = _find_other_orcalab_processes()
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
    logger.warning("检测到已有 OrcaLab 进程: %s", details_text)

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
        sys.exit(0)

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
        sys.exit(1)

    logger.info("所有现有 OrcaLab 进程已终止，继续启动")


async def main_async(q_app):
    global _main_window

    app_close_event = asyncio.Event()
    q_app.aboutToQuit.connect(app_close_event.set)
    main_window = MainWindow()
    _main_window = main_window  # Store reference for signal handlers
    await main_window.init()

    await app_close_event.wait()

    # Clean up resources before exiting
    logger.info("Application is closing, cleaning up resources...")
    await main_window.cleanup()


def main():
    """Main entry point for the orcalab application"""
    args = parse_cli_args()

    console_level = None
    if getattr(args, "log_level", None):
        try:
            console_level = resolve_log_level(args.log_level)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            sys.exit(2)

    setup_logging(console_level=console_level)

    check_project_folder()

    register_protocol()

    # Register signal handlers for graceful shutdown
    register_signal_handlers()

    config_service = ConfigService()
    # 配置文件在项目根目录，需要向上查找
    current_dir = os.path.dirname(__file__)
    project_root = os.path.dirname(current_dir)  # 从 orcalab/ 目录回到项目根目录
    config_service.init_config(project_root)

    # Ensure the external Python project (orcalab-pyside) is present and installed
    try:
        ensure_python_project_installed(config_service)
    except Exception as e:
        logger.exception("安装 orcalab-pyside 失败: %s", e)
        # Continue startup but warn; some features may not work without it

    # 处理pak包
    logger.info("正在准备资产包...")
    if config_service.init_paks():
        paks = config_service.paks()
        if paks:
            # 如果paks有内容，则复制本地文件
            logger.info("使用本地pak文件...")
            copy_packages(paks)
    
    # 处理pak_urls（独立于paks和订阅列表，下载到orcalab子目录）
    pak_urls = config_service.pak_urls()
    if pak_urls:
        logger.info("正在同步pak_urls列表...")
        sync_pak_urls(pak_urls)
    
    # 创建 Qt 应用（需要在创建窗口之前）
    q_app = QtWidgets.QApplication(sys.argv)

    # 确保不会同时运行多个 OrcaLab 实例
    _ensure_single_instance()
    
    # 同步订阅的资产包（带UI）
    run_asset_sync_ui(config_service)

    from orcalab.level_discovery import discover_levels_from_cache

    discovered_levels = discover_levels_from_cache()
    if discovered_levels:
        config_service.merge_levels(discovered_levels)

    # 场景选择
    from orcalab.ui.scene_select_dialog import SceneSelectDialog
    levels = config_service.levels() if hasattr(config_service, 'levels') else []
    current = config_service.level() if hasattr(config_service, 'level') else None
    if levels:
        selected, ok = SceneSelectDialog.get_level(levels, current)
        if ok and selected:
            config_service.set_current_level(selected)
            logger.info("用户选择了场景: %s", selected.get("name"))
        else:
            logger.info("用户未选择场景，使用默认值")

    event_loop = QEventLoop(q_app)
    asyncio.set_event_loop(event_loop)

    try:
        event_loop.run_until_complete(main_async(q_app))
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt, cleaning up...")
    except Exception as e:
        logger.exception("Application error: %s", e)
    finally:
        event_loop.close()

    # magic!
    # AttributeError: 'NoneType' object has no attribute 'POLLER'
    # https://github.com/google-gemini/deprecated-generative-ai-python/issues/207#issuecomment-2601058191
    exit(0)


if __name__ == "__main__":
    main()
