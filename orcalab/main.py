# Patch PySide6 first. Before any other PySide6 imports.
import pathlib
from orcalab.cli_options import create_argparser
from orcalab.patch_pyside6 import patch_pyside6

patch_pyside6()

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
from orcalab.default_layout import prepare_default_layout
from orcalab.process_guard import ensure_single_instance

import os

# import PySide6.QtAsyncio as QtAsyncio
from PySide6 import QtWidgets

from qasync import QEventLoop
from orcalab.python_project_installer import ensure_python_project_installed

# Global variable to store main window instance for cleanup
_main_window = None

logger = logging.getLogger(__name__)

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
    parser = create_argparser()
    args, unknown = parser.parse_known_args()

    console_level = logging.INFO
    if getattr(args, "log_level", None):
        try:
            console_level = resolve_log_level(args.log_level)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            sys.exit(2)

    setup_logging(console_level=console_level)

    workspace = pathlib.Path(args.workspace).resolve()
    logger.info("工作目录: %s", workspace)

    config_service = ConfigService()
    # 配置文件在项目根目录，需要向上查找
    current_dir = pathlib.Path(__file__).parent.resolve()
    project_root = current_dir.parent  # 从 orcalab/ 目录回到项目根目录
    config_service.init_config(project_root, workspace)

    check_project_folder()

    register_protocol()

    # Register signal handlers for graceful shutdown
    register_signal_handlers()

    q_app = QtWidgets.QApplication(sys.argv)

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

    # 场景选择
    from orcalab.ui.scene_select_dialog import SceneSelectDialog

    levels = config_service.levels() if hasattr(config_service, "levels") else []
    current = config_service.level() if hasattr(config_service, "level") else None
    if levels:
        initial_layout_mode = config_service.layout_mode()
        selected, layout_mode, ok = SceneSelectDialog.get_level(
            levels, current, layout_mode=initial_layout_mode
        )
        if ok and selected:
            layout_mode = (
                layout_mode if layout_mode in {"default", "blank"} else "default"
            )
            config_service.set_layout_mode(layout_mode)

            default_layout_file = None
            if layout_mode == "default":
                default_layout_file = prepare_default_layout(selected)
                if default_layout_file:
                    logger.info("已生成默认布局: %s", default_layout_file)
                else:
                    logger.warning("生成默认布局失败，将使用空白布局。")
            config_service.set_default_layout_file(default_layout_file)

            config_service.set_current_level(selected)
            logger.info("用户选择了场景: %s", selected.get("name"))
        else:
            logger.info("用户未选择场景，退出程序")
            exit(0)

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
