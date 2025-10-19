"""
资产同步 UI 管理模块

负责资产同步的UI展示和交互逻辑
"""

import threading
from typing import Optional
from PySide6 import QtWidgets

from orcalab.asset_sync_service import sync_assets, AssetSyncCallbacks
from orcalab.ui.sync_progress_window import SyncProgressWindow


class SyncCallbacksImpl(AssetSyncCallbacks):
    """同步回调实现"""
    
    def __init__(self, window: SyncProgressWindow):
        self.window = window
    
    def on_start(self):
        self.window.start_sync()
    
    def on_query_complete(self, packages):
        pass
    
    def on_asset_status(self, asset_id: str, asset_name: str, file_name: str, size: int, status: str):
        self.window.add_asset(asset_id, asset_name, file_name, size, status)
    
    def on_download_start(self, asset_id: str, asset_name: str):
        self.window.set_asset_status(asset_id, 'downloading')
        self.window.set_status(f"正在下载: {asset_name}")
    
    def on_download_progress(self, asset_id: str, progress: int, speed: float):
        self.window.set_asset_progress(asset_id, progress, speed)
    
    def on_download_complete(self, asset_id: str, success: bool, error: str = ""):
        if success:
            self.window.set_asset_status(asset_id, 'completed')
        else:
            self.window.set_asset_status(asset_id, 'failed')
    
    def on_delete(self, file_name: str):
        pass
    
    def on_complete(self, success: bool, message: str = ""):
        self.window.complete_sync(success, message)


def run_asset_sync_ui(config_service) -> bool:
    """
    运行资产同步（带UI）
    
    Args:
        config_service: 配置服务实例
    
    Returns:
        同步是否成功
    """
    # 检查是否启用同步
    if not config_service.datalink_enable_sync():
        print("跳过资产同步（已禁用）")
        return True
    
    # 检查认证信息
    if not config_service.datalink_username() or not config_service.datalink_token():
        print("跳过资产同步（未配置认证信息）")
        return True
    
    # 创建同步进度窗口
    sync_window = SyncProgressWindow()
    
    # 创建回调
    callbacks = SyncCallbacksImpl(sync_window)
    
    # 在后台线程执行同步
    sync_result = [True]  # 使用列表来存储结果，因为需要在闭包中修改
    
    def run_sync():
        result = sync_assets(config_service, callbacks=callbacks, verbose=False)
        sync_result[0] = result
    
    sync_thread = threading.Thread(target=run_sync, daemon=True)
    sync_thread.start()
    
    # 显示同步窗口（模态）
    sync_window.exec()
    
    # 等待同步完成
    sync_thread.join()
    
    if not sync_result[0]:
        print("⚠️  资产同步失败，但程序将继续启动")
    
    return sync_result[0]

