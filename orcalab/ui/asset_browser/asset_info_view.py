from PySide6 import QtCore, QtWidgets

from orcalab.ui.asset_browser.asset_info import AssetInfo
from orcalab.metadata_service_bus import AssetMetadata


class AssetInfoView(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        scroll_area = QtWidgets.QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(12)

        name_group = self._create_info_group("名称", self._create_name_widget())
        path_group = self._create_info_group("路径", self._create_path_widget())
        metadata_group = self._create_metadata_group()

        content_layout.addWidget(name_group)
        content_layout.addWidget(path_group)
        content_layout.addWidget(metadata_group)
        content_layout.addStretch(1)

        scroll_area.setWidget(content_widget)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll_area)

    def _create_info_group(self, title: str, widget: QtWidgets.QWidget) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox(title)
        group.setStyleSheet("""
            QGroupBox {
                font-size: 12px;
                font-weight: bold;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
        """)
        layout = QtWidgets.QVBoxLayout(group)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.addWidget(widget)
        return group

    def _create_name_widget(self) -> QtWidgets.QLabel:
        self._name_label = QtWidgets.QLabel()
        self._name_label.setWordWrap(True)
        self._name_label.setStyleSheet("""
            QLabel {
                color: #e0e0e0;
                font-size: 11px;
                padding: 4px;
                background-color: #2a2a2a;
                border-radius: 3px;
            }
        """)
        return self._name_label

    def _create_path_widget(self) -> QtWidgets.QLabel:
        self._path_label = QtWidgets.QLabel()
        self._path_label.setWordWrap(True)
        self._path_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self._path_label.setStyleSheet("""
            QLabel {
                color: #a0c8ff;
                font-size: 11px;
                padding: 4px;
                background-color: #2a2a2a;
                border-radius: 3px;
                font-family: 'Consolas', 'Monaco', monospace;
            }
        """)
        return self._path_label

    def _create_metadata_group(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("元数据")
        group.setStyleSheet("""
            QGroupBox {
                font-size: 12px;
                font-weight: bold;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
        """)
        
        layout = QtWidgets.QVBoxLayout(group)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(8)

        self._metadata_text = QtWidgets.QPlainTextEdit()
        self._metadata_text.setReadOnly(True)
        self._metadata_text.setStyleSheet("""
            QPlainTextEdit {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #444444;
                border-radius: 3px;
                padding: 6px;
                font-size: 11px;
                font-family: 'Consolas', 'Monaco', monospace;
                selection-background-color: #0078d4;
            }
        """)
        self._metadata_text.setMaximumHeight(200)

        copy_button = QtWidgets.QPushButton("复制")
        copy_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                border: none;
                border-radius: 3px;
                padding: 6px 16px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        copy_button.clicked.connect(self._copy_metadata)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(copy_button)

        layout.addWidget(self._metadata_text)
        layout.addLayout(button_layout)

        return group

    def _copy_metadata(self):
        text = self._metadata_text.toPlainText()
        if text:
            clipboard = QtWidgets.QApplication.clipboard()
            clipboard.setText(text)

    def set_asset_info(self, asset_info: AssetInfo | None):
        if asset_info is not None:
            self._name_label.setText(asset_info.name)
            self._path_label.setText(asset_info.path)
            self.set_metadata_info(asset_info.metadata)
        else:
            self._name_label.setText("")
            self._path_label.setText("")
            self._metadata_text.setPlainText("")

    def set_metadata_info(self, metadata_info: AssetMetadata | None):
        if metadata_info is not None:
            metadata_str = (
                f"ID: {metadata_info.get('id', 'N/A')}\n"
                f"Parent Package ID: {metadata_info.get('parentPackageId', 'N/A')}\n"
                f"Category: {metadata_info.get('category', 'N/A')}\n"
                f"Type: {metadata_info.get('type', 'N/A')}\n"
                f"Author: {metadata_info.get('author', 'N/A')}"
            )
            self._metadata_text.setPlainText(metadata_str)
        else:
            self._metadata_text.setPlainText("无可用元数据")