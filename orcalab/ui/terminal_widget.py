from PySide6 import QtCore, QtWidgets, QtGui
import subprocess
import threading
import queue
import os
import sys


class TerminalTextEdit(QtWidgets.QTextEdit):
    """支持输入捕获的终端文本编辑器"""
    
    input_submitted = QtCore.Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._input_buffer = ""
        # 禁用默认的undo/redo
        self.setUndoRedoEnabled(False)
        
    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        
        # 屏蔽 Ctrl+Z (undo) 和 Ctrl+Y/Ctrl+Shift+Z (redo)
        if modifiers & QtCore.Qt.KeyboardModifier.ControlModifier:
            if key in (QtCore.Qt.Key.Key_Z, QtCore.Qt.Key.Key_Y):
                return
        
        # Enter键：发送当前输入缓冲区
        if key in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            text_to_send = self._input_buffer + "\n"
            self._input_buffer = ""
            # 显示换行
            cursor = self.textCursor()
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
            cursor.insertText("\n")
            self.setTextCursor(cursor)
            # 发送输入
            self.input_submitted.emit(text_to_send)
            return
        
        # Ctrl+C：发送中断信号
        if key == QtCore.Qt.Key.Key_C and event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
            self.input_submitted.emit("\x03")  # ETX字符
            return
        
        # Ctrl+D：发送EOF
        if key == QtCore.Qt.Key.Key_D and event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
            self.input_submitted.emit("\x04")  # EOT字符
            return
        
        # 退格键：删除输入缓冲区最后一个字符
        if key == QtCore.Qt.Key.Key_Backspace:
            if self._input_buffer:
                self._input_buffer = self._input_buffer[:-1]
                # 删除显示的字符
                cursor = self.textCursor()
                cursor.deletePreviousChar()
                self.setTextCursor(cursor)
            return
        
        # 普通字符输入
        text = event.text()
        if text and text.isprintable():
            self._input_buffer += text
            # 显示输入的字符
            cursor = self.textCursor()
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
            cursor.insertText(text)
            self.setTextCursor(cursor)
            # 滚动到底部
            scrollbar = self.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            return
        
        # 其他键使用默认处理（如方向键滚动等）
        super().keyPressEvent(event)
    
    def clear_input_buffer(self):
        """清空输入缓冲区"""
        self._input_buffer = ""


class TerminalWidget(QtWidgets.QWidget):
    """终端输出显示组件，支持输入"""
    
    # 进程被中断信号（Ctrl+C）
    process_interrupted = QtCore.Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.process = None
        self._pty_master_fd = None
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
        
        # 输出区域（支持输入）
        self.output_text = TerminalTextEdit()
        self.output_text.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.WidgetWidth)
        self.output_text.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.output_text.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.output_text.input_submitted.connect(self._send_input)
        
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
            
            # 启动进程（包含stdin以支持输入）
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
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
    
    def _send_input(self, text):
        """向进程发送输入"""
        if not self.is_running or not self.process:
            return
        
        try:
            # 处理Ctrl+C中断信号
            if text == "\x03":
                import signal
                if sys.platform == "win32":
                    self.process.send_signal(signal.CTRL_C_EVENT)
                else:
                    self.process.send_signal(signal.SIGINT)
                self._append_output_safe("^C\n")
                # 发出中断信号，通知外部执行停止流程
                self.process_interrupted.emit()
                return
            
            # 优先使用PTY主端发送
            if self._pty_master_fd is not None:
                os.write(self._pty_master_fd, text.encode('utf-8'))
            elif self.process.stdin:
                self.process.stdin.write(text)
                self.process.stdin.flush()
        except (BrokenPipeError, OSError):
            self._append_output_safe(f"\n[输入失败: 进程已关闭]\n")
    
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
    
    def set_external_process(self, process: subprocess.Popen):
        """设置外部进程引用（用于外部启动的进程，使用PIPE）"""
        self.process = process
        self._pty_master_fd = None
        self.is_running = True
        self.status_label.setText(f"运行中 (PID: {process.pid})")
        self.status_label.setStyleSheet("color: #3fb950; font-size: 11px;")
        self.output_text.clear_input_buffer()
    
    def set_pty_process(self, process: subprocess.Popen, master_fd: int):
        """设置使用PTY的外部进程引用"""
        self.process = process
        self._pty_master_fd = master_fd
        self.is_running = True
        self.status_label.setText(f"运行中 (PID: {process.pid})")
        self.status_label.setStyleSheet("color: #3fb950; font-size: 11px;")
        self.output_text.clear_input_buffer()
    
    def clear_external_process(self):
        """清除外部进程引用"""
        self.process = None
        self._pty_master_fd = None
        self.is_running = False
        self.status_label.setText("已停止")
        self.status_label.setStyleSheet("color: #7d8590; font-size: 11px;")
        self.output_text.clear_input_buffer()
    
    def clear_pty_process(self):
        """清除PTY进程引用"""
        self.clear_external_process()
    
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
    
    # 测试启动一个需要输入的进程
    terminal.start_process("python", ["-c", "name=input('请输入你的名字: '); print(f'你好, {name}!')"])
    
    sys.exit(app.exec())
