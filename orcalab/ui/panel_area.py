import pathlib
from typing import List, override
from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.ui.panel import Panel

from orcalab.ui.icon_util import make_text_icon
from orcalab.ui.button import Button

from orcalab.ui.panel_bus import PanelRequestBus
from orcalab.ui.theme_service import ThemeService


class PanelButton(Button):

    def __init__(self):
        super().__init__()

        self.panel: Panel = None
        self.panel_area: "PanelArea" = None
        self.icon_size = 24
        self.border_radius = 0
        self.padding_left = 0
        self.padding_right = 0
        self.padding_top = 12
        self.padding_bottom = 12

        self.mark_color = ThemeService().get_color("brand")

    def mouseReleaseEvent(self, event):
        self.panel_area.toggle_panel(self.panel)
        super().mouseReleaseEvent(event)

    def make_icon(self):
        if self.panel.panel_icon is not None:
            self._icon = self.panel.panel_icon
            return

        name = self.panel.panel_name
        if len(name) > 2:
            short_name = name[:2]
        else:
            short_name = name

        color = ThemeService().get_color("panel_icon")
        self._icon = make_text_icon(short_name, self.font(), color)

    def paintEvent(self, event: QtGui.QPaintEvent):
        super().paintEvent(event)

        if self.panel_area.opened_panel == self.panel:
            self._draw_mark()

    def _draw_mark(self):
        mark_size = 2

        mark_rect = QtCore.QRect(0, 0, mark_size, self.height())
        if self.panel_area.name == "right":
            mark_rect.moveRight(self.width() - 1)

        painter = QtGui.QPainter(self)
        painter.fillRect(mark_rect, self.mark_color)
        painter.end()


class PanelButtonGroup(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.root_layout = QtWidgets.QVBoxLayout()
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)
        self.setLayout(self.root_layout)

        self.panel_buttons: List[PanelButton] = []

    def set_panels(self, panels: List[Panel], panel_area: "PanelArea"):
        n = len(panels)
        while self.root_layout.count() != n:
            if self.root_layout.count() < n:
                button = PanelButton()
                self.panel_buttons.append(button)
                self.root_layout.addWidget(button)
            else:
                self.panel_buttons.pop()
                item = self.root_layout.takeAt(0)
                widget = item.widget()
                widget.setParent(None)

        panels.sort()
        for i, panel in enumerate(panels):
            self.panel_buttons[i].panel = panel
            self.panel_buttons[i].panel_area = panel_area
            self.panel_buttons[i].make_icon()
            self.panel_buttons[i].updateGeometry()
            self.panel_buttons[i].update()


class PanelArea(QtWidgets.QWidget):
    request_hide = QtCore.Signal()

    def __init__(self, name: str, root_layout: QtWidgets.QBoxLayout):
        super().__init__()

        if not isinstance(name, str):
            raise TypeError("name must be a string")

        if not name:
            raise ValueError("name cannot be an empty string")

        self.name = name
        self.panels: List[Panel] = []
        self.panel_button_group = PanelButtonGroup()
        self.opened_panel: Panel | None = None
        self.root_layout = root_layout
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        self.panel_area_size = 0
        self.setMinimumSize(200, 100)

        self.setLayout(root_layout)

    def add_panel(self, panel: Panel):
        if not isinstance(panel, Panel):
            raise TypeError("panel must be an instance of Panel")

        for existing_panel in self.panels:
            if existing_panel.panel_name == panel.panel_name:
                raise ValueError(
                    f"A panel with the name '{panel.panel_name}' already exists."
                )

        self.panels.append(panel)
        self.panel_button_group.set_panels(self.panels, self)
        self.root_layout.addWidget(panel)

        panel.hide()

    def has_panel(self, panel_name: str) -> bool:
        for panel in self.panels:
            if panel.panel_name == panel_name:
                return True
        return False

    def open_panel(self, panel: str | Panel):
        if self.opened_panel == panel:
            return

        if self.opened_panel is not None:
            self._close_panel(self.opened_panel)

        panel = self._get_panel(panel)

        panel.show()
        self.opened_panel = panel

    def _get_panel(self, panel: str | Panel) -> Panel:
        if isinstance(panel, Panel):
            return panel

        name = str(panel)
        for p in self.panels:
            if p.panel_name == name:
                return p

        raise ValueError(f"No panel with the name '{name}' found.")

    def _close_panel(self, panel: Panel):
        panel.hide()
        self.panel_button_group.update()

    def close_panel(self, panel: str | Panel):
        panel = self._get_panel(panel)

        if self.opened_panel == panel:
            self._close_panel(panel)
            self.opened_panel = None

        PanelRequestBus().close_panel_area(self.name)

    def toggle_panel(self, panel: str | Panel):
        panel = self._get_panel(panel)
        if self.opened_panel == panel:
            PanelRequestBus().close_panel(panel.panel_name)
        else:
            PanelRequestBus().open_panel(panel.panel_name)

    def save_size(self):
        raise NotImplementedError("Subclasses must implement save_size method")

    def get_save_size(self):
        raise NotImplementedError("Subclasses must implement get_save_size method")

    def save_layout_to_dict(self, data: dict):
        if self.opened_panel is not None:
            data["opened_panel"] = self.opened_panel.panel_name

    def load_layout_from_dict(self, data: dict):
        opened_panel_name = data.get("opened_panel", None)
        if opened_panel_name is not None:
            self.open_panel(opened_panel_name)


class PanelAreaVertical(PanelArea):
    def __init__(self, name: str):
        super().__init__(name, QtWidgets.QVBoxLayout())

    def save_size(self):
        self.panel_area_size = self.width()

    def get_save_size(self):
        if self.isVisible():
            return self.width()
        return self.panel_area_size


class PanelAreaHorizontal(PanelArea):
    def __init__(self, name: str):
        super().__init__(name, QtWidgets.QHBoxLayout())

    def save_size(self):
        self.panel_area_size = self.height()

    def get_save_size(self):
        if self.isVisible():
            return self.height()
        return self.panel_area_size
