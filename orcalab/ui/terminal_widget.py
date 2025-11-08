from PySide6 import QtCore, QtWidgets, QtGui
import subprocess
import threading
import queue
import os
import sys


class TerminalWidget(QtWidgets.QWidget):
    """终端输出显示组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.process = None
        self.output_queue = queue.Queue()
        self.output_thread = None
        self.is_running = False
        
        self._setup_ui()
        
        # 创建定时器来更新UI
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self._update_output)
        self.update_timer.start(50)  # 每50ms更新一次
        
        # 设置样式
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QTextEdit {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 4px;
                color: #e6edf3;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 12px;
                padding: 8px;
                selection-background-color: #264f78;
            }
            QTextEdit:focus {
                border-color: #58a6ff;
            }
            QPushButton {
                background-color: #21262d;
                border: 1px solid #30363d;
                border-radius: 4px;
                color: #f0f6fc;
                padding: 6px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #30363d;
                border-color: #8b949e;
            }
            QPushButton:pressed {
                background-color: #161b22;
            }
            QPushButton:disabled {
                background-color: #161b22;
                color: #7d8590;
                border-color: #21262d;
            }
        """)
    
    def _setup_ui(self):
        """设置UI布局"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # 工具栏
        toolbar_layout = QtWidgets.QHBoxLayout()
        
        self.clear_button = QtWidgets.QPushButton("清空")
        self.clear_button.clicked.connect(self.clear_output)
        toolbar_layout.addWidget(self.clear_button)
        
        self.copy_button = QtWidgets.QPushButton("复制")
        self.copy_button.clicked.connect(self.copy_output)
        toolbar_layout.addWidget(self.copy_button)
        
        toolbar_layout.addStretch()
        
        # 状态标签
        self.status_label = QtWidgets.QLabel("就绪")
        self.status_label.setStyleSheet("color: #7d8590; font-size: 11px;")
        toolbar_layout.addWidget(self.status_label)
        
        layout.addLayout(toolbar_layout)
        
        # 输出区域
        self.output_text = QtWidgets.QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.WidgetWidth)
        self.output_text.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.output_text.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 设置滚动条样式
        self.output_text.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical {
                background-color: #161b22;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #30363d;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #484f58;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """)
        
        layout.addWidget(self.output_text)
    
    def start_process(self, command, args, working_dir=None):
        """启动外部进程"""
        if self.is_running:
            self.stop_process()
        
        try:
            # 构建完整的命令
            cmd = [command] + args
            
            # 启动进程
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                cwd=working_dir,
                env=os.environ.copy()
            )
            
            self.is_running = True
            self.status_label.setText(f"运行中 (PID: {self.process.pid})")
            self.status_label.setStyleSheet("color: #3fb950; font-size: 11px;")
            
            # 启动输出读取线程
            self.output_thread = threading.Thread(
                target=self._read_output,
                daemon=True
            )
            self.output_thread.start()
            
            # 添加启动信息
            self._append_output(f"启动进程: {' '.join(cmd)}\n")
            self._append_output(f"工作目录: {working_dir or os.getcwd()}\n")
            self._append_output("-" * 50 + "\n")
            
            return True
            
        except Exception as e:
            self._append_output(f"启动进程失败: {str(e)}\n")
            self.status_label.setText("启动失败")
            self.status_label.setStyleSheet("color: #f85149; font-size: 11px;")
            return False
    
    def stop_process(self):
        """停止外部进程"""
        if not self.is_running or not self.process:
            return
        
        try:
            self._append_output("\n" + "-" * 50 + "\n")
            self._append_output("正在停止进程...\n")
            
            # 尝试优雅终止
            self.process.terminate()
            
            # 等待进程结束
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # 强制终止
                self.process.kill()
                self.process.wait()
                self._append_output("进程已强制终止\n")
            else:
                self._append_output("进程已正常终止\n")
            
            self.is_running = False
            self.process = None
            self.status_label.setText("已停止")
            self.status_label.setStyleSheet("color: #7d8590; font-size: 11px;")
            
        except Exception as e:
            self._append_output(f"停止进程时出错: {str(e)}\n")
    
    def _read_output(self):
        """在后台线程中读取进程输出"""
        if not self.process:
            return
        
        try:
            while self.is_running and self.process and self.process.poll() is None:
                line = self.process.stdout.readline()
                if line:
                    self.output_queue.put(line)
                else:
                    break
            
            # 读取剩余输出
            remaining_output = self.process.stdout.read()
            if remaining_output:
                self.output_queue.put(remaining_output)
            
            # 检查进程退出码
            if self.process:
                return_code = self.process.poll()
                if return_code is not None:
                    self.output_queue.put(f"\n进程退出，返回码: {return_code}\n")
                    
        except Exception as e:
            self.output_queue.put(f"读取输出时出错: {str(e)}\n")
    
    def _update_output(self):
        """更新UI显示输出"""
        try:
            while True:
                try:
                    if self.output_queue.empty():
                        break
                    line = self.output_queue.get_nowait()
                    self._append_output(line)
                except queue.Empty:
                    break
        except Exception as e:
            print(f"更新输出时出错: {e}")
    
    def _append_output(self, text):
        """追加输出到文本区域"""
        # 使用信号槽机制确保在主线程中更新UI
        QtCore.QMetaObject.invokeMethod(
            self, "_append_output_safe",
            QtCore.Qt.ConnectionType.QueuedConnection,
            QtCore.Q_ARG(str, text)
        )
    
    @QtCore.Slot(str)
    def _append_output_safe(self, text):
        """安全地追加输出（在主线程中调用）"""
        cursor = self.output_text.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        
        # 自动滚动到底部
        scrollbar = self.output_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def clear_output(self):
        """清空输出"""
        self.output_text.clear()
        self._append_output("输出已清空\n")
    
    def copy_output(self):
        """复制输出到剪贴板"""
        text = self.output_text.toPlainText()
        if text:
            clipboard = QtWidgets.QApplication.clipboard()
            clipboard.setText(text)
            self.status_label.setText("已复制到剪贴板")
            self.status_label.setStyleSheet("color: #58a6ff; font-size: 11px;")
            
            # 2秒后恢复状态
            QtCore.QTimer.singleShot(2000, lambda: self.status_label.setText(
                "运行中 (PID: {})".format(self.process.pid) if self.is_running and self.process else "就绪"
            ))
    
    def is_process_running(self):
        """检查进程是否正在运行"""
        return self.is_running and self.process and self.process.poll() is None
    
    def get_process_pid(self):
        """获取进程PID"""
        if self.process:
            return self.process.pid
        return None
    
    def closeEvent(self, event):
        """关闭事件处理"""
        if self.is_running:
            self.stop_process()
        event.accept()


if __name__ == "__main__":
    import sys
    
    app = QtWidgets.QApplication(sys.argv)
    
    terminal = TerminalWidget()
    terminal.show()
    terminal.resize(600, 400)
    
    # 测试启动一个简单进程
    terminal.start_process("python", ["-c", "import time; [print(f'Line {i}') or time.sleep(1) for i in range(10)]"])
    
    sys.exit(app.exec())
