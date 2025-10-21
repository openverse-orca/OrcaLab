"""
认证等待窗口

显示认证进度，等待用户在浏览器中完成登录
"""

from PySide6 import QtWidgets, QtCore, QtGui
import threading
from typing import Optional, Callable


class AuthWindow(QtWidgets.QDialog):
    """认证等待窗口"""
    
    # 定义信号
    update_status_signal = QtCore.Signal(str)
    auth_complete_signal = QtCore.Signal(bool, str)  # (success, message)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DataLink 认证")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)
        
        self.auth_success = False
        self.auth_message = ""
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """设置 UI"""
        layout = QtWidgets.QVBoxLayout()
        
        # 标题
        title_label = QtWidgets.QLabel("DataLink 用户认证")
        title_font = QtGui.QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        layout.addSpacing(20)
        
        # 状态文本
        self.status_label = QtWidgets.QLabel("初始化中...")
        self.status_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
        layout.addSpacing(10)
        
        # 进度条
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 0)  # 不确定进度
        layout.addWidget(self.progress_bar)
        
        layout.addSpacing(20)
        
        # 说明文本
        help_text = QtWidgets.QLabel(
            "请在浏览器中完成登录。\n"
            "如果浏览器没有自动打开，请检查浏览器设置。"
        )
        help_text.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: gray;")
        layout.addWidget(help_text)
        
        layout.addStretch()
        
        # 取消按钮
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_button = QtWidgets.QPushButton("取消")
        self.cancel_button.setMinimumWidth(100)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def _connect_signals(self):
        """连接信号"""
        self.update_status_signal.connect(self._on_status_update)
        self.auth_complete_signal.connect(self._on_auth_complete)
    
    def _on_status_update(self, message: str):
        """更新状态文本"""
        self.status_label.setText(message)
    
    def _on_auth_complete(self, success: bool, message: str):
        """认证完成"""
        self.auth_success = success
        self.auth_message = message
        
        if success:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.status_label.setText(f"✓ {message}")
            self.status_label.setStyleSheet("color: green;")
            
            # 延迟关闭窗口
            QtCore.QTimer.singleShot(1000, self.accept)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.status_label.setText(f"✗ {message}")
            self.status_label.setStyleSheet("color: red;")
            self.cancel_button.setText("关闭")
    
    def update_status(self, message: str):
        """
        更新状态（线程安全）
        
        Args:
            message: 状态消息
        """
        self.update_status_signal.emit(message)
    
    def complete_auth(self, success: bool, message: str = ""):
        """
        标记认证完成（线程安全）
        
        Args:
            success: 认证是否成功
            message: 结果消息
        """
        self.auth_complete_signal.emit(success, message)
    
    def run_auth(self, auth_func: Callable[[], Optional[dict]]) -> Optional[dict]:
        """
        在后台线程运行认证流程
        
        Args:
            auth_func: 认证函数，返回包含 username, access_token, refresh_token 的字典
        
        Returns:
            认证结果字典，失败返回 None
        """
        result_container = [None]
        
        def auth_thread():
            try:
                credentials = auth_func()
                result_container[0] = credentials
                
                if credentials:
                    self.complete_auth(True, f"认证成功: {credentials['username']}")
                else:
                    self.complete_auth(False, "认证失败或超时")
                    
            except Exception as e:
                self.complete_auth(False, f"认证出错: {str(e)}")
        
        # 启动认证线程
        thread = threading.Thread(target=auth_thread, daemon=True)
        thread.start()
        
        # 显示窗口（阻塞）
        result = self.exec()
        
        # 等待线程完成
        thread.join(timeout=2.0)
        
        # 如果用户点击了取消
        if result == QtWidgets.QDialog.DialogCode.Rejected:
            return None
        
        return result_container[0]


def show_auth_dialog(auth_func: Callable[[], Optional[dict]], parent=None) -> Optional[dict]:
    """
    显示认证对话框的便捷函数
    
    Args:
        auth_func: 认证函数
        parent: 父窗口
    
    Returns:
        认证结果字典，失败返回 None
    """
    dialog = AuthWindow(parent)
    return dialog.run_auth(auth_func)

