from PySide6 import QtCore, QtWidgets

from orcalab.ui.asset_browser.asset_info import AssetInfo
from orcalab.ui.fonts.font_service import FontService


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

        path_group = self._create_info_group("路径", self._create_path_widget())
        content_layout.addWidget(path_group)
        content_layout.addStretch(1)

        scroll_area.setWidget(content_widget)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll_area)

    def _create_info_group(self, title: str, widget: QtWidgets.QWidget) -> QtWidgets.QGroupBox:
        fs = FontService()
        group = QtWidgets.QGroupBox(title)
        fs.bind_widget_stylesheet(
            group,
            lambda: f"""
            QGroupBox {{
                {fs.get_font_css('group_title')}
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }}
        """,
        )
        layout = QtWidgets.QVBoxLayout(group)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.addWidget(widget)
        return group

    def _create_path_widget(self) -> QtWidgets.QLabel:
        fs = FontService()
        self._path_label = QtWidgets.QLabel()
        self._path_label.setWordWrap(True)
        self._path_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        fs.bind_widget_stylesheet(
            self._path_label,
            lambda: f"""
            QLabel {{
                color: #a0c8ff;
                {fs.get_font_css('path_label')}
                padding: 4px;
                background-color: #2a2a2a;
                border-radius: 3px;
            }}
        """,
        )
        return self._path_label

    def set_asset_info(self, asset_info: AssetInfo | None):
        if asset_info is not None:
            self._path_label.setText(asset_info.path)
        else:
            self._path_label.setText("")
