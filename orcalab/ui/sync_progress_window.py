"""
资产同步进度窗口

显示资产包同步状态：
- 需要下载的资产包及进度
- 需要删除的资产包
- 不需要变化的资产包
"""

from PySide6 import QtWidgets, QtCore, QtGui
from typing import Dict, List, Optional
import time

from numpy import int64


class AssetItemWidget(QtWidgets.QWidget):
    """资产包条目组件"""
    
    def __init__(self, asset_name: str, file_name: str, size: int, status: str, parent=None):
        super().__init__(parent)
        self.asset_name = asset_name
        self.file_name = file_name
        self._size = size
        self.status = status  # 'download', 'delete', 'ok', 'downloading'
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # 状态图标
        self.status_label = QtWidgets.QLabel()
        self.status_label.setFixedWidth(30)
        self.update_status_icon()
        layout.addWidget(self.status_label)
        
        # 资产包名称和文件名
        info_layout = QtWidgets.QVBoxLayout()
        self.name_label = QtWidgets.QLabel(self.asset_name)
        self.name_label.setStyleSheet("font-weight: bold;")
        self.file_label = QtWidgets.QLabel(self.file_name)
        self.file_label.setStyleSheet("color: gray; font-size: 10px;")
        info_layout.addWidget(self.name_label)
        info_layout.addWidget(self.file_label)
        layout.addLayout(info_layout)
        
        layout.addStretch()
        
        # 大小
        size_mb = self._size / (1024 * 1024)
        self.size_label = QtWidgets.QLabel(f"{size_mb:.2f} MB")
        self.size_label.setMinimumWidth(80)
        self.size_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        layout.addWidget(self.size_label)
        
        # 进度条（仅下载时显示）
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setMaximumWidth(150)
        self.progress_bar.setVisible(self.status in ['download', 'downloading'])
        layout.addWidget(self.progress_bar)
        
        # 速度和状态文本
        self.status_text = QtWidgets.QLabel()
        self.status_text.setMinimumWidth(120)
        self.status_text.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.update_status_text()
        layout.addWidget(self.status_text)
    
    def update_status_icon(self):
        """更新状态图标"""
        if self.status == 'ok':
            self.status_label.setText("✓")
            self.status_label.setStyleSheet("color: green; font-size: 20px;")
        elif self.status == 'delete':
            self.status_label.setText("✗")
            self.status_label.setStyleSheet("color: red; font-size: 20px;")
        elif self.status in ['download', 'downloading']:
            self.status_label.setText("⬇")
            self.status_label.setStyleSheet("color: blue; font-size: 20px;")
        elif self.status == 'completed':
            self.status_label.setText("✓")
            self.status_label.setStyleSheet("color: green; font-size: 20px;")
        elif self.status == 'failed':
            self.status_label.setText("✗")
            self.status_label.setStyleSheet("color: red; font-size: 20px;")
        elif self.status == 'incompatible':
            self.status_label.setText("⚠️")
    
    def update_status_text(self):
        """更新状态文本"""
        if self.status == 'ok':
            self.status_text.setText("已是最新")
            self.status_text.setStyleSheet("color: green;")
        elif self.status == 'delete':
            self.status_text.setText("待删除")
            self.status_text.setStyleSheet("color: red;")
        elif self.status == 'download':
            self.status_text.setText("待下载")
            self.status_text.setStyleSheet("color: blue;")
        elif self.status == 'downloading':
            self.status_text.setText("下载中...")
            self.status_text.setStyleSheet("color: blue;")
        elif self.status == 'completed':
            self.status_text.setText("下载完成")
            self.status_text.setStyleSheet("color: green;")
        elif self.status == 'failed':
            self.status_text.setText("下载失败")
            self.status_text.setStyleSheet("color: red;")
        elif self.status == 'incompatible':
            self.status_text.setText("不兼容")
            self.status_text.setStyleSheet("color: orange;")
    
    def set_progress(self, progress: int64, speed: float = 0):
        """
        设置下载进度
        
        Args:
            progress: 进度百分比 (0-100)
            speed: 下载速度 (MB/s)
        """
        self.progress_bar.setValue(progress)
        if speed > 0:
            self.status_text.setText(f"{speed:.2f} MB/s")
        else:
            self.status_text.setText("下载中...")
    
    def set_status(self, status: str):
        """更新状态"""
        self.status = status
        self.update_status_icon()
        self.update_status_text()
        self.progress_bar.setVisible(status in ['download', 'downloading'])


class SyncProgressWindow(QtWidgets.QDialog):
    """资产同步进度窗口"""
    
    # 信号（用于线程安全的UI更新）
    sync_completed = QtCore.Signal()
    sync_failed = QtCore.Signal(str)
    
    # 内部信号（线程安全）
    _add_asset_signal = QtCore.Signal(str, str, str, int64, str)  # id, name, file, size, status
    _set_status_signal = QtCore.Signal(str, str)  # asset_id, status
    _set_progress_signal = QtCore.Signal(str, int64, float)  # asset_id, progress, speed
    _set_message_signal = QtCore.Signal(str)  # message
    _complete_signal = QtCore.Signal(bool, str)  # success, message
    _start_signal = QtCore.Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.asset_widgets: Dict[str, AssetItemWidget] = {}
        self.start_time = None
        self.countdown_seconds = 0
        self.countdown_timer = None
        self.setup_ui()
        
        # 连接内部信号（线程安全）
        self._add_asset_signal.connect(self._add_asset_impl)
        self._set_status_signal.connect(self._set_status_impl)
        self._set_progress_signal.connect(self._set_progress_impl)
        self._set_message_signal.connect(self._set_message_impl)
        self._complete_signal.connect(self._complete_impl)
        self._start_signal.connect(self._start_impl)
    
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("资产包同步")
        self.setMinimumSize(700, 500)
        self.setModal(True)
        
        # 主布局
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        
        # 标题
        title_label = QtWidgets.QLabel("正在同步资产包...")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)
        
        # 统计信息
        self.stats_label = QtWidgets.QLabel()
        self.stats_label.setStyleSheet("color: gray;")
        layout.addWidget(self.stats_label)
        
        # 分隔线
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(line)
        
        # 滚动区域
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        
        # 资产列表容器
        self.asset_list_widget = QtWidgets.QWidget()
        self.asset_list_layout = QtWidgets.QVBoxLayout(self.asset_list_widget)
        self.asset_list_layout.setSpacing(2)
        self.asset_list_layout.addStretch()
        
        scroll_area.setWidget(self.asset_list_widget)
        layout.addWidget(scroll_area)
        
        # 底部状态
        bottom_layout = QtWidgets.QHBoxLayout()
        
        self.status_label = QtWidgets.QLabel("准备同步...")
        bottom_layout.addWidget(self.status_label)
        
        bottom_layout.addStretch()
        
        # 退出按钮（初始隐藏，仅在失败时显示）
        self.exit_button = QtWidgets.QPushButton("退出")
        self.exit_button.setVisible(False)
        self.exit_button.clicked.connect(self.on_exit_clicked)
        bottom_layout.addWidget(self.exit_button)
        
        # 离线启动按钮（初始隐藏，仅在失败时显示）
        self.offline_button = QtWidgets.QPushButton("离线启动")
        self.offline_button.setVisible(False)
        self.offline_button.clicked.connect(self.on_offline_clicked)
        bottom_layout.addWidget(self.offline_button)
        
        # 关闭按钮（初始禁用，成功后显示）
        self.close_button = QtWidgets.QPushButton("关闭")
        self.close_button.setEnabled(False)
        self.close_button.clicked.connect(self.on_close_clicked)
        bottom_layout.addWidget(self.close_button)
        
        layout.addLayout(bottom_layout)
        
        # 用户选择结果（用于区分退出还是离线启动）
        self.user_choice = None  # None: 未选择, 'exit': 退出, 'offline': 离线启动, 'close': 正常关闭
    
    def add_asset(self, asset_id: str, asset_name: str, file_name: str, size: int64, status: str):
        """线程安全：添加资产包到列表"""
        self._add_asset_signal.emit(asset_id, asset_name, file_name, size, status)
    
    def _add_asset_impl(self, asset_id: str, asset_name: str, file_name: str, size: int64, status: str):
        """内部实现：添加资产包"""
        widget = AssetItemWidget(asset_name, file_name, size, status)
        self.asset_widgets[asset_id] = widget
        
        # 插入到 stretch 之前
        count = self.asset_list_layout.count()
        self.asset_list_layout.insertWidget(count - 1, widget)
        
        self.update_stats()
    
    def update_stats(self):
        """更新统计信息"""
        total = len(self.asset_widgets)
        download_count = sum(1 for w in self.asset_widgets.values() if w.status in ['download', 'downloading'])
        delete_count = sum(1 for w in self.asset_widgets.values() if w.status == 'delete')
        ok_count = sum(1 for w in self.asset_widgets.values() if w.status == 'ok')
        
        parts = []
        if download_count > 0:
            parts.append(f"<span style='color: blue;'>待下载: {download_count}</span>")
        if delete_count > 0:
            parts.append(f"<span style='color: red;'>待删除: {delete_count}</span>")
        if ok_count > 0:
            parts.append(f"<span style='color: green;'>已最新: {ok_count}</span>")
        
        stats_text = " | ".join(parts) if parts else "无资产包"
        self.stats_label.setText(f"总计: {total} 个资产包 | {stats_text}")
    
    def set_asset_status(self, asset_id: str, status: str):
        """线程安全：设置资产包状态"""
        self._set_status_signal.emit(asset_id, status)
    
    def _set_status_impl(self, asset_id: str, status: str):
        """内部实现：设置资产包状态"""
        if asset_id in self.asset_widgets:
            self.asset_widgets[asset_id].set_status(status)
            self.update_stats()
    
    def set_asset_progress(self, asset_id: str, progress: int64, speed: float = 0):
        """线程安全：设置资产包下载进度"""
        self._set_progress_signal.emit(asset_id, progress, speed)
    
    def _set_progress_impl(self, asset_id: str, progress: int64, speed: float):
        """内部实现：设置资产包下载进度"""
        if asset_id in self.asset_widgets:
            self.asset_widgets[asset_id].set_progress(progress, speed)
    
    def set_status(self, message: str):
        """线程安全：设置底部状态消息"""
        self._set_message_signal.emit(message)
    
    def _set_message_impl(self, message: str):
        """内部实现：设置底部状态消息"""
        self.status_label.setText(message)
    
    def start_sync(self):
        """线程安全：开始同步"""
        self._start_signal.emit()
    
    def _start_impl(self):
        """内部实现：开始同步"""
        self.start_time = time.time()
        self._set_message_impl("正在同步资产包...")
    
    def complete_sync(self, success: bool, message: str = ""):
        """线程安全：完成同步"""
        self._complete_signal.emit(success, message)
    
    def _complete_impl(self, success: bool, message: str):
        """内部实现：完成同步"""
        elapsed = time.time() - self.start_time if self.start_time else 0
        
        if success:
            self._set_message_impl(f"同步完成！用时 {elapsed:.1f} 秒")
            self.sync_completed.emit()
            
            # 成功时显示关闭按钮并启动倒计时
            self.close_button.setVisible(True)
            self.close_button.setEnabled(True)
            self.start_countdown(5)
        else:
            error_msg = f"同步失败：{message}" if message else "同步失败"
            self._set_message_impl(error_msg)
            self.sync_failed.emit(message)
            
            # 失败时隐藏关闭按钮，显示退出和离线启动按钮
            self.close_button.setVisible(False)
            self.exit_button.setVisible(True)
            self.offline_button.setVisible(True)
    
    def start_countdown(self, seconds: int):
        """启动倒计时"""
        self.countdown_seconds = seconds
        self.close_button.setEnabled(True)
        self.update_countdown_button()
        
        # 创建定时器
        self.countdown_timer = QtCore.QTimer(self)
        self.countdown_timer.timeout.connect(self.on_countdown_tick)
        self.countdown_timer.start(1000)  # 每秒触发一次
    
    def update_countdown_button(self):
        """更新倒计时按钮文本"""
        if self.countdown_seconds > 0:
            self.close_button.setText(f"关闭 ({self.countdown_seconds})")
        else:
            self.close_button.setText("关闭")
    
    def on_countdown_tick(self):
        """倒计时滴答"""
        self.countdown_seconds -= 1
        
        if self.countdown_seconds > 0:
            self.update_countdown_button()
        else:
            # 倒计时结束
            if self.countdown_timer:
                self.countdown_timer.stop()
                self.countdown_timer = None
            self.close_button.setText("关闭")
            self.accept()  # 自动关闭
    
    def on_close_clicked(self):
        """关闭按钮点击处理（同步成功后）"""
        # 停止倒计时
        if self.countdown_timer:
            self.countdown_timer.stop()
            self.countdown_timer = None
        # 设置为正常关闭
        self.user_choice = 'close'
        # 立即关闭
        self.accept()
    
    def on_exit_clicked(self):
        """退出按钮点击处理"""
        self.user_choice = 'exit'
        self.reject()  # 使用 reject() 表示用户取消/退出
    
    def on_offline_clicked(self):
        """离线启动按钮点击处理"""
        self.user_choice = 'offline'
        self.accept()  # 使用 accept() 表示继续
    
    def remove_asset(self, asset_id: str):
        """移除资产包（删除后）"""
        if asset_id in self.asset_widgets:
            widget = self.asset_widgets[asset_id]
            self.asset_list_layout.removeWidget(widget)
            widget.deleteLater()
            del self.asset_widgets[asset_id]
            self.update_stats()

