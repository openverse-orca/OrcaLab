import asyncio
import sys
import signal
import atexit

from orcalab.config_service import ConfigService
from orcalab.project_util import check_project_folder, copy_packages, download_pak_files_sync
from orcalab.asset_sync_ui import run_asset_sync_ui
from orcalab.url_service.url_util import register_protocol
from orcalab.ui.main_window import MainWindow

import os

# import PySide6.QtAsyncio as QtAsyncio
from PySide6 import QtWidgets

from qasync import QEventLoop
from orcalab.python_project_installer import ensure_python_project_installed

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


async def main_async(q_app):
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


def main():
    """Main entry point for the orcalab application"""
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
        print(f"安装 orcalab-pyside 失败: {e}")
        # Continue startup but warn; some features may not work without it

    # 处理pak包
    print("正在准备资产包...")
    if config_service.init_paks():
        paks = config_service.paks()
        if paks:
            # 如果paks有内容，则复制本地文件
            print("使用本地pak文件...")
            copy_packages(paks)
        else:
            # 如果paks为空，则从URL下载
            pak_urls = config_service.pak_urls()
            if pak_urls:
                print("从OSS下载pak文件...")
                downloaded_files = download_pak_files_sync(pak_urls)
                if downloaded_files:
                    print(f"成功下载 {len(downloaded_files)} 个pak文件")
                    # 将下载的文件路径添加到配置中，避免被资产同步删除
                    config_service.config["orcalab"]["paks"] = downloaded_files
                    print("已将下载的pak文件添加到配置中")
                else:
                    print("警告: 没有成功下载任何pak文件")
            else:
                print("警告: 没有配置pak文件路径或下载URL")
    
    # 创建 Qt 应用（需要在创建窗口之前）
    q_app = QtWidgets.QApplication(sys.argv)
    
    # 同步订阅的资产包（带UI）
    run_asset_sync_ui(config_service)

    event_loop = QEventLoop(q_app)
    asyncio.set_event_loop(event_loop)

    try:
        event_loop.run_until_complete(main_async(q_app))
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


if __name__ == "__main__":
    main()
