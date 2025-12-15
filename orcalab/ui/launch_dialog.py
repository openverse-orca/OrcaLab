from PySide6 import QtCore, QtWidgets, QtGui
from orcalab.config_service import ConfigService


class LaunchDialog(QtWidgets.QDialog):
    """仿真程序启动对话框"""
    
    program_selected = QtCore.Signal(str)  # 选择的程序名称
    no_external_program = QtCore.Signal()  # 无仿真程序信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择仿真程序")
        self.setModal(True)
        self.resize(500, 400)
        
        self.config_service = ConfigService()
        self.selected_program = None
        
        self._setup_ui()
        self._load_programs()
        
        # 设置样式
        self.setStyleSheet("""
            QWidget {
                background-color: #181818;
                color: #ffffff;
            }
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QRadioButton {
                color: #ffffff;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 2px solid #555555;
                background-color: #3c3c3c;
            }
            QRadioButton::indicator:checked {
                border-color: #0078d4;
                background-color: #0078d4;
            }
            QRadioButton::indicator:checked::after {
                width: 8px;
                height: 8px;
                border-radius: 4px;
                background-color: #ffffff;
                margin: 2px;
            }
            QPushButton {
                background-color: #4a4a4a;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 8px 16px;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
                border-color: #666666;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            QPushButton:disabled {
                background-color: #333333;
                color: #666666;
                border-color: #444444;
            }
            QTextEdit {
                background-color: #1e1e1e;
                border: 1px solid #404040;
                border-radius: 4px;
                color: #ffffff;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                padding: 8px;
            }
            QGroupBox {
                border: 1px solid #404040;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
            }
        """)
    
    def _setup_ui(self):
        """设置UI布局"""
        layout = QtWidgets.QVBoxLayout(self)
        
        # 标题
        title_label = QtWidgets.QLabel("选择要启动的仿真程序")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 16px;")
        layout.addWidget(title_label)
        
        # 程序选择区域
        programs_group = QtWidgets.QGroupBox("仿真程序")
        programs_layout = QtWidgets.QVBoxLayout(programs_group)
        
        # 创建单选按钮组
        self.button_group = QtWidgets.QButtonGroup(self)
        self.button_group.setExclusive(True)
        
        # 程序列表容器
        self.programs_scroll = QtWidgets.QScrollArea()
        self.programs_scroll.setWidgetResizable(True)
        self.programs_scroll.setMaximumHeight(200)
        self.programs_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #3c3c3c;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #666666;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #777777;
            }
        """)
        
        self.programs_widget = QtWidgets.QWidget()
        self.programs_layout = QtWidgets.QVBoxLayout(self.programs_widget)
        self.programs_layout.setContentsMargins(0, 0, 0, 0)
        
        self.programs_scroll.setWidget(self.programs_widget)
        programs_layout.addWidget(self.programs_scroll)
        
        layout.addWidget(programs_group)
        
        # 无仿真程序选项
        no_program_group = QtWidgets.QGroupBox("其他选项")
        no_program_layout = QtWidgets.QVBoxLayout(no_program_group)
        
        self.no_program_radio = QtWidgets.QRadioButton("无仿真程序（手动启动）")
        self.no_program_radio.setToolTip("不启动任何仿真程序，用户需要手动启动")
        self.button_group.addButton(self.no_program_radio)
        no_program_layout.addWidget(self.no_program_radio)
        
        layout.addWidget(no_program_group)
        
        # 程序详情显示
        details_group = QtWidgets.QGroupBox("程序详情")
        details_layout = QtWidgets.QVBoxLayout(details_group)
        
        self.details_text = QtWidgets.QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(100)
        details_layout.addWidget(self.details_text)
        
        layout.addWidget(details_group)
        
        # 按钮区域
        button_layout = QtWidgets.QHBoxLayout()
        
        self.launch_button = QtWidgets.QPushButton("启动")
        self.launch_button.setEnabled(False)
        self.launch_button.clicked.connect(self._on_launch_clicked)
        
        self.cancel_button = QtWidgets.QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.launch_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        # 连接信号
        self.button_group.buttonClicked.connect(self._on_program_selected)
    
    def _load_programs(self):
        """从配置文件加载程序列表"""
        programs = self.config_service.external_programs()
        
        if not programs:
            # 如果没有配置程序，显示默认选项
            no_programs_label = QtWidgets.QLabel("未配置仿真程序")
            no_programs_label.setStyleSheet("color: #888888; font-style: italic; padding: 16px;")
            self.programs_layout.addWidget(no_programs_label)
            return
        
        for i, program in enumerate(programs):
            radio = QtWidgets.QRadioButton(program.get("display_name", program.get("name", "Unknown")))
            radio.setProperty("program_name", program.get("name"))
            radio.setProperty("program_config", program)
            
            # 设置工具提示
            tooltip = f"名称: {program.get('name', 'Unknown')}\n"
            tooltip += f"命令: {program.get('command', 'Unknown')}\n"
            tooltip += f"参数: {' '.join(program.get('args', []))}\n"
            tooltip += f"描述: {program.get('description', 'No description')}"
            radio.setToolTip(tooltip)
            
            self.button_group.addButton(radio, i)
            self.programs_layout.addWidget(radio)
        
        # 设置默认选择
        default_program = self.config_service.default_external_program()
        for button in self.button_group.buttons():
            if button.property("program_name") == default_program:
                button.setChecked(True)
                self._on_program_selected(button)
                break
    
    def _on_program_selected(self, button):
        """程序选择改变时的处理"""
        self.selected_program = button.property("program_name")
        self.launch_button.setEnabled(True)
        
        if button == self.no_program_radio:
            self.details_text.setText("将不启动任何仿真程序。\n用户需要手动启动仿真程序并通过其他方式连接到OrcaLab。")
        else:
            program_config = button.property("program_config")
            if program_config:
                details = self._format_program_details(program_config)
                self.details_text.setText(details)
    
    def _format_program_details(self, program_config):
        """格式化程序详情显示"""
        details = []
        details.append(f"程序名称: {program_config.get('name', 'Unknown')}")
        details.append(f"显示名称: {program_config.get('display_name', 'Unknown')}")
        details.append(f"执行命令: {program_config.get('command', 'Unknown')}")
        
        args = program_config.get('args', [])
        if args:
            details.append(f"命令行参数: {' '.join(args)}")
        
        description = program_config.get('description', '')
        if description:
            details.append(f"描述: {description}")
        
        return '\n'.join(details)
    
    def _on_launch_clicked(self):
        """启动按钮点击处理"""
        if self.no_program_radio.isChecked():
            self.no_external_program.emit()
        elif self.selected_program:
            self.program_selected.emit(self.selected_program)
        
        self.accept()
    
    def get_selected_program(self):
        """获取选择的程序名称"""
        return self.selected_program


if __name__ == "__main__":
    import sys
    from orcalab.config_service import ConfigService
    
    # 初始化配置服务
    config_service = ConfigService()
    config_service.init_config("/home/superfhwl/repo/OrcaLab")
    
    app = QtWidgets.QApplication(sys.argv)
    
    dialog = LaunchDialog()
    dialog.show()
    
    sys.exit(app.exec())
