from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.ui.icon_util import make_icon
from orcalab.ui.panel_bus import PanelRequestBus
from orcalab.ui.button import Button
from orcalab.ui.line import make_horizontal_line
from orcalab.ui.theme_service import ThemeService


class Panel(QtWidgets.QWidget):
    def __init__(self, panel_name: str, panel_content: QtWidgets.QWidget):
        super().__init__()

        if not isinstance(panel_name, str):
            raise TypeError("panel_name must be a string")

        if not panel_name:
            raise ValueError("panel_name cannot be an empty string")

        self.panel_name = panel_name
        self.panel_icon: QtGui.QIcon | None = None
        self.panel_order = 0
        self.panel_size = 0

        title_area = QtWidgets.QWidget()
        title_area.setFixedHeight(28)

        theme_service = ThemeService()
        panel_icon_color = theme_service.get_color("panel_icon")
        icon = make_icon(":/icons/subtract", panel_icon_color)

        close_btn = Button(icon=icon)
        close_btn.icon_size = 16
        close_btn.mouse_released.connect(self._request_close)
        close_btn.setFixedSize(20, 20)

        self.title_area_layout = QtWidgets.QHBoxLayout(title_area)
        self.title_area_layout.setContentsMargins(5, 0, 5, 0)
        self.title_area_layout.setSpacing(0)
        self.title_area_layout.addWidget(QtWidgets.QLabel(self.panel_name), 0)
        self.title_area_layout.addStretch(1)
        self.title_area_layout.addWidget(close_btn, 0)

        content_area = QtWidgets.QScrollArea()

        layout = QtWidgets.QVBoxLayout(content_area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(panel_content)

        self.root_layout = QtWidgets.QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        self.root_layout.addWidget(title_area, 0)
        self.root_layout.addWidget(make_horizontal_line(), 0)
        self.root_layout.addWidget(content_area, 1)

        theme = ThemeService()

        bg_color = theme.get_color_hex("button_bg")
        text_color = theme.get_color_hex("text")

        self.setObjectName(f"panel_{panel_name.lower().replace(' ', '_')}")

        self.setStyleSheet(
            f"""
            QWidget#{self.objectName()} {{
                background-color: {bg_color};
            }}
        """
        )

        title_area.setStyleSheet(
            f"""
            QLabel {{
                color: {text_color};
            }}
        """
        )

        content_area.setStyleSheet(
            """
            QTreeView, QListView, QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
                border: none;
                selection-background-color: #404040;
                alternate-background-color: #333333;
            }
            QTreeView::item:selected, QListView::item:selected {
                background-color: #404040;
                color: #ffffff;
            }
            QTreeView::item:hover, QListView::item:hover {
                background-color: #353535;
            }
            QHeaderView::section {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #404040;
                padding: 4px;
            }
        """
        )

    def __lt__(self, other):
        return self.panel_order < other.panel_order

    def _request_close(self):
        PanelRequestBus().close_panel(self.panel_name)
