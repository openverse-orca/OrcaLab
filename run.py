# Patch PySide6 first.
from orcalab.patch_pyside6 import patch_pyside6

patch_pyside6()


import asyncio
import sys
import signal
import atexit

from orcalab.config_service import ConfigService
from orcalab.project_util import check_project_folder, copy_packages, clear_cache_packages, sync_pak_urls
from orcalab.asset_sync_ui import run_asset_sync_ui
from orcalab.url_service.url_util import register_protocol
from orcalab.ui.main_window import MainWindow

import os

# import PySide6.QtAsyncio as QtAsyncio
from PySide6 import QtWidgets

from qasync import QEventLoop

# Global variable to store main window instance for cleanup
_main_window = None


def signal_handler(signum, frame):
    """Handle system signals to ensure cleanup"""
    print(f"Received signal {signum}, cleaning up...")
    if _main_window is not None:
        try:
            # Try to run cleanup in the event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(_main_window.cleanup())
        except Exception as e:
            print(f"Error during signal cleanup: {e}")
    sys.exit(0)


def register_signal_handlers():
    """Register signal handlers for graceful shutdown"""
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination signal
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, signal_handler)  # Hangup signal


async def main(q_app):
    global _main_window

    app_close_event = asyncio.Event()
    q_app.aboutToQuit.connect(app_close_event.set)
    main_window = MainWindow()
    _main_window = main_window  # Store reference for signal handlers
    await main_window.init()

    await app_close_event.wait()

    # Clean up resources before exiting
    print("Application is closing, cleaning up resources...")
    await main_window.cleanup()


if __name__ == "__main__":
    check_project_folder()

    register_protocol()

    # Register signal handlers for graceful shutdown
    register_signal_handlers()

    config_service = ConfigService()
    config_service.init_config(os.path.dirname(__file__))

    # 准备资产包
    print("正在准备资产包...")
    
    # 1. 处理手工指定的pak包（复制到缓存目录）
    if config_service.paks():
        copy_packages(config_service.paks())
    
    # 2. 处理pak_urls（下载到缓存目录，与手工pak和订阅列表并行）
    pak_urls = config_service.pak_urls()
    if pak_urls:
        print("正在同步pak_urls列表...")
        sync_pak_urls(pak_urls)
    
    # 3. 清除逻辑在同步订阅列表后执行（在 asset_sync_service 中处理）
    # 这样可以结合订阅列表、手工pak列表和pak_urls列表，只删除不在三者中的包

    # 创建 Qt 应用（需要在创建窗口之前）
    q_app = QtWidgets.QApplication(sys.argv)

    # 同步订阅的资产包（带UI）
    run_asset_sync_ui(config_service)

    event_loop = QEventLoop(q_app)
    asyncio.set_event_loop(event_loop)

    try:
        event_loop.run_until_complete(main(q_app))
    except KeyboardInterrupt:
        print("Received KeyboardInterrupt, cleaning up...")
    except Exception as e:
        print(f"Application error: {e}")
    finally:
        event_loop.close()

    # magic!
    # AttributeError: 'NoneType' object has no attribute 'POLLER'
    # https://github.com/google-gemini/deprecated-generative-ai-python/issues/207#issuecomment-2601058191
    exit(0)
