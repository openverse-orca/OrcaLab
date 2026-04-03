# Patch PySide6 first. Before any other PySide6 imports.
from orcalab.patch_pyside6 import patch_pyside6

patch_pyside6()

import pathlib
from typing import List
import asyncio
import sys
import signal
import logging

from orcalab.cli_options import create_argparser, resolve_and_validate_workspace
from orcalab.config_service import ConfigService
from orcalab.project_util import check_project_folder, copy_packages, sync_pak_urls
from orcalab.asset_sync_ui import run_asset_sync_ui
from orcalab.ui.main_window import MainWindow
from orcalab.logging_util import setup_logging, resolve_log_level
from orcalab.default_layout import prepare_default_layout
from orcalab.process_guard import ensure_single_instance
from orcalab.ui.main_window_full_screen import MainWindowFullScreen
import os

# import PySide6.QtAsyncio as QtAsyncio
from PySide6 import QtWidgets
import orcalab.assets.rc_assets

from qasync import QEventLoop
from orcalab.python_project_installer import ensure_python_project_installed
from orcalab.ui.icon_util import app_window_icon

# This is needed to display the app icon on the taskbar on Windows
if os.name == 'nt':
    import ctypes
    myappid = 'opvs.orca.orcalab.version' # Arbitrary string
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

# Global variable to store main window instance for cleanup
_main_window = None

logger = logging.getLogger("orcalab.main")


def _start_force_exit_watchdog(timeout: int = 10) -> None:
    """启动守护线程，若进程在 timeout 秒内未正常退出则强制终止。
    
    使用 os._exit() 绕过 Python 清理流程，防止卡死的后台线程（gRPC/网络IO等）
    导致进程变成无法杀死的僵尸进程。
    """
    import threading
    import time

    def _watchdog():
        time.sleep(timeout)
        logger.warning("进程在 %s 秒内未正常退出，强制终止", timeout)
        os._exit(0)

    t = threading.Thread(target=_watchdog, daemon=True, name="force-exit-watchdog")
    t.start()


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


async def main_async(q_app, fullscreen: bool):
    global _main_window

    app_close_event = asyncio.Event()
    q_app.aboutToQuit.connect(app_close_event.set)
    if fullscreen:
        main_window = MainWindowFullScreen()
    else:
        main_window = MainWindow()
    _main_window = main_window  # Store reference for signal handlers
    await main_window.init()

    await app_close_event.wait()

    # Clean up resources before exiting
    logger.info("Application is closing, cleaning up resources...")
    await main_window.cleanup()


_ADMIN_ONLY_LEVELS = {"previewthumbnail_orcalab"}


def select_scene_and_layout(
    config_service: ConfigService,
    levels: List[dict],
    level: str,
    level_cli: str | None,
    layout_cli: str | None,
):
    layout_mode = "unset"

    from orcalab.token_storage import TokenStorage
    import requests as _requests

    def _check_is_admin() -> bool:
        token = TokenStorage.load_token()
        if not token:
            return False
        base_url = config_service.datalink_base_url()
        headers = {
            "Authorization": f"Bearer {token['access_token']}",
            "username": token["username"],
            "Content-Type": "application/json",
        }
        try:
            resp = _requests.get(f"{base_url}/is_admin/", headers=headers, timeout=10)
            if resp.status_code != 200:
                return False
            return resp.json().get("isAdmin", False)
        except Exception:
            return False

    if not _check_is_admin():
        levels = [l for l in levels if l.get("name") not in _ADMIN_ONLY_LEVELS
                  and l.get("path") not in _ADMIN_ONLY_LEVELS]

    # 1. 选择场景，优先级：命令行 > 场景选择界面

    if type(level_cli) is str and level_cli.strip():
        level_info = None
        for _level in levels:
            if _level["name"] == level_cli:
                level_info = _level
                break

        if level_info is None:
            logger.error("命令行指定的场景 '%s' 不在已发现的场景列表中。", level_cli)
            exit(0)
        else:
            logger.info("命令行指定场景: %s", level_cli)
            config_service.set_current_level(level_info)

    else:
        from orcalab.ui.scene_select_dialog import SceneSelectDialog

        initial_layout_mode = config_service.layout_mode()
        selected, layout_mode, ok = SceneSelectDialog.get_level(
            levels, level, layout_mode=initial_layout_mode
        )
        if ok and selected:
            layout_mode = (
                layout_mode if layout_mode in {"default", "blank"} else "default"
            )
            config_service.set_layout_mode(layout_mode)
            config_service.set_current_level(selected)
            logger.info("用户选择了场景: %s", selected.get("name"))
        else:
            logger.info("用户未选择场景，退出程序")
            exit(0)

    # 2. 选择布局

    def resolve_relative_layout_path(layout_cli: str):
        # 1. 首先在当前工作目录下查找
        p = (pathlib.Path.cwd() / layout_cli).resolve()
        if p.exists():
            return p

        # 2. 如果在当前工作目录下找不到，再尝试在workspace目录下查找
        p = (pathlib.Path(config_service.workspace()) / layout_cli).resolve()
        if p.exists():
            return p

        return None

    def prepare_layout():
        default_layout_file = None
        if layout_mode == "default":
            current_level = config_service.current_level_info()
            default_layout_file = prepare_default_layout(current_level)  # type: ignore
            if default_layout_file:
                logger.info("已生成默认布局: %s", default_layout_file)
            else:
                logger.warning("生成默认布局失败，将使用空白布局。")
        config_service.set_default_layout_file(default_layout_file)

    if type(layout_cli) is str and layout_cli.strip():
        if layout_cli == "default" or layout_cli == "blank":
            if layout_mode == "unset":
                layout_mode = layout_cli
                config_service.set_layout_mode(layout_mode)
                logger.info("命令行指定布局模式: %s", layout_cli)

            prepare_layout()
        else:
            p = pathlib.Path(layout_cli)
            if p.is_absolute():
                if p.exists():
                    config_service.set_default_layout_file(str(p))
                    logger.info("命令行指定布局文件: %s", p)
                else:
                    logger.error("命令行指定的布局文件 '%s' 不存在，无法加载。", p)
            else:
                p = resolve_relative_layout_path(layout_cli)
                if p is not None:
                    config_service.set_default_layout_file(str(p))
                    logger.info("命令行指定布局文件: %s", p)
                else:
                    logger.error(
                        "命令行指定的布局文件 '%s' 不存在，无法加载。", layout_cli
                    )
    else:
        if layout_mode == "unset":
            layout_mode = "default"
        prepare_layout()


def main():
    """Main entry point for the orcalab application"""
    parser = create_argparser()
    args, unknown = parser.parse_known_args()

    console_level = logging.INFO
    if getattr(args, "log_level", logging.INFO):
        try:
            console_level = resolve_log_level(args.log_level)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            sys.exit(2)

    logger = setup_logging(console_level=console_level)

    logger.info("进程 PID: %d", os.getpid())

    workspace = resolve_and_validate_workspace(
        args.workspace, init_config=args.init_config
    )
    logger.info("工作目录: %s", workspace)

    config_service = ConfigService()
    # 配置文件在项目根目录，需要向上查找
    current_dir = pathlib.Path(__file__).parent.resolve()
    project_root = current_dir.parent  # 从 orcalab/ 目录回到项目根目录
    config_service.init_config(project_root, workspace)

    check_project_folder()

    # register_protocol()

    # Register signal handlers for graceful shutdown
    register_signal_handlers()

    q_app = QtWidgets.QApplication(sys.argv)
    q_app.setWindowIcon(app_window_icon())

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

    # 确保不会同时运行多个 OrcaLab 实例
    ensure_single_instance()

    # 同步订阅的资产包（带UI）
    run_asset_sync_ui(config_service)

    from orcalab.level_discovery import discover_levels_from_cache

    discovered_levels = discover_levels_from_cache()
    if discovered_levels:
        config_service.merge_levels(discovered_levels)

    levels = config_service.levels()
    current = config_service.level()

    level_cli = getattr(args, "scene", None)
    layout_cli = getattr(args, "layout", None)

    select_scene_and_layout(
        config_service=config_service,
        levels=levels,
        level=current,
        level_cli=level_cli,
        layout_cli=layout_cli,
    )

    event_loop = QEventLoop(q_app)
    asyncio.set_event_loop(event_loop)

    try:
        fullscreen = args.full_screen
        event_loop.run_until_complete(main_async(q_app, fullscreen))
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt, cleaning up...")
    except Exception as e:
        logger.exception("Application error: %s", e)
    finally:
        event_loop.close()

    _start_force_exit_watchdog(timeout=10)

    # magic!
    # AttributeError: 'NoneType' object has no attribute 'POLLER'
    # https://github.com/google-gemini/deprecated-generative-ai-python/issues/207#issuecomment-2601058191
    exit(0)


if __name__ == "__main__":
    main()
