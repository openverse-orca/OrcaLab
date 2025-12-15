"""
资产同步 UI 管理模块

负责资产同步的UI展示和交互逻辑
"""

import threading
from typing import Optional
import logging
from PySide6 import QtWidgets
from numpy import int64

from orcalab.asset_sync_service import sync_assets, AssetSyncCallbacks
from orcalab.ui.sync_progress_window import SyncProgressWindow
from orcalab.auth_service import AuthService
from orcalab.token_storage import TokenStorage
from orcalab.ui.auth_window import show_auth_dialog

logger = logging.getLogger(__name__)


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
    
    def on_download_progress(self, asset_id: str, progress: int64, speed: float):
        self.window.set_asset_progress(asset_id, progress, speed)
    
    def on_download_complete(self, asset_id: str, success: bool, error: str = ""):
        if success:
            self.window.set_asset_status(asset_id, 'completed')
        else:
            self.window.set_asset_status(asset_id, 'failed')
    
    def on_delete(self, file_name: str):
        pass
    
    def on_metadata_sync(self, status: str, count: int = 0, total: int = 0):
        if status == 'start':
            self.window.set_status(f"正在同步元数据... (0/{total})")
        elif status == 'progress':
            self.window.set_status(f"正在同步元数据... ({count}/{total})")
        elif status == 'complete':
            self.window.set_status(f"元数据同步完成 ({count}/{total})")
    
    def on_complete(self, success: bool, message: str = ""):
        self.window.complete_sync(success, message)


def ask_offline_or_exit(title: str, message: str) -> bool:
    """
    询问用户是否以离线模式继续启动或退出程序
    
    Args:
        title: 对话框标题
        message: 提示消息
    
    Returns:
        True - 用户选择离线启动
        False - 用户选择退出（会直接调用 sys.exit）
    """
    from PySide6 import QtWidgets
    msg_box = QtWidgets.QMessageBox()
    msg_box.setWindowTitle(title)
    msg_box.setText(message)
    msg_box.setInformativeText("是否以离线模式继续启动？\n\n点击「是」使用现有资产包继续启动\n点击「否」退出程序")
    msg_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
    msg_box.setDefaultButton(QtWidgets.QMessageBox.StandardButton.Yes)
    
    reply = msg_box.exec()
    if reply == QtWidgets.QMessageBox.StandardButton.Yes:
        logger.info("✓ 以离线模式继续启动（使用现有资产包）")
        return True
    else:
        logger.info("用户选择退出程序")
        import sys
        sys.exit(0)


def authenticate_user(config_service, window=None) -> bool:
    """
    用户认证流程
    
    Args:
        config_service: 配置服务实例
        window: AuthWindow 实例（可选）
    
    Returns:
        认证是否成功
    """
    base_url = config_service.datalink_base_url()
    auth_server_url = config_service.datalink_auth_server_url()
    timeout = config_service.datalink_timeout()
    redirect_url = config_service.web_server_url()
    
    # 创建认证服务
    auth_service = AuthService(base_url, auth_server_url=auth_server_url, timeout=timeout)
    
    def auth_func():
        """认证函数，带进度回调"""
        return auth_service.authenticate(window=window, redirect_url=redirect_url)
    
    # 如果没有传入 window，则显示认证对话框
    if window is None:
        credentials = show_auth_dialog(auth_func)
    else:
        credentials = auth_func()
    
    if credentials:
        # 保存 token 到本地
        TokenStorage.save_token(
            username=credentials['username'],
            access_token=credentials['access_token'],
            refresh_token=credentials.get('refresh_token')
        )
        logger.info("✓ 认证成功: %s", credentials['username'])
        return True
    else:
        logger.warning("✗ 认证失败或已取消")
        return False


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
        logger.info("跳过资产同步（已禁用）")
        return True
    
    # 检查认证信息（优先从本地存储读取）
    username = config_service.datalink_username()
    token = config_service.datalink_token()
    
    # 如果没有认证信息，显示登录窗口
    if not username or not token:
        logger.info("需要进行 DataLink 认证...")
        if not authenticate_user(config_service):
            # 认证失败，询问用户是否离线启动
            ask_offline_or_exit("认证失败", "DataLink 认证失败或已取消。")
            return True  # 用户选择离线启动
        
        # 认证成功，重新获取 username 和 token
        username = config_service.datalink_username()
        token = config_service.datalink_token()
    
    # 在同步前验证 token 是否有效
    logger.info("验证访问令牌...")
    base_url = config_service.datalink_base_url()
    auth_server_url = config_service.datalink_auth_server_url()
    timeout = config_service.datalink_timeout()
    auth_service = AuthService(base_url, auth_server_url=auth_server_url, timeout=timeout)
    
    if not auth_service.verify_token(username, token):
        logger.warning("⚠️  Token 已过期或无效，需要重新认证")
        TokenStorage.clear_token()
        
        # 直接打开认证窗口，不询问用户
        logger.info("正在打开认证窗口...")
        if not authenticate_user(config_service):
            # 认证失败，询问用户是否离线启动
            ask_offline_or_exit("重新认证失败", "DataLink 重新认证失败。")
            return True  # 用户选择离线启动
        
        logger.info("✓ 重新认证成功")
        # 更新 username 和 token
        username = config_service.datalink_username()
        token = config_service.datalink_token()
    
    # 创建同步进度窗口
    sync_window = SyncProgressWindow()
    
    # 创建回调
    callbacks = SyncCallbacksImpl(sync_window)
    
    # 在后台线程执行同步
    sync_result = [True]  # 使用列表来存储结果，因为需要在闭包中修改
    token_expired = [False]
    
    def run_sync():
        result = sync_assets(config_service, callbacks=callbacks, verbose=False)
        if result == 'TOKEN_EXPIRED':
            token_expired[0] = True
            sync_result[0] = False
        else:
            sync_result[0] = result
    
    sync_thread = threading.Thread(target=run_sync, daemon=True)
    sync_thread.start()
    
    # 显示同步窗口（模态）
    dialog_result = sync_window.exec()
    
    # 等待同步完成
    sync_thread.join()
    
    # 检查用户选择
    if sync_window.user_choice == 'exit':
        logger.info("用户选择退出程序")
        import sys
        sys.exit(0)
    elif sync_window.user_choice == 'offline':
        logger.info("✓ 用户选择离线启动（使用现有资产包）")
        return True
    
    # 如果同步过程中检测到 token 过期（理论上不应该发生，因为已经提前验证过）
    if token_expired[0]:
        logger.warning("⚠️  同步过程中 Token 意外过期，现有资产包已保留")
        logger.info("✓ 以离线模式继续启动（使用现有资产包）")
    elif not sync_result[0]:
        logger.warning("⚠️  资产同步失败，但程序将继续启动（使用现有资产包）")
    else:
        logger.info("✓ 资产同步完成")
    
    return True  # 总是返回 True，允许程序继续启动

