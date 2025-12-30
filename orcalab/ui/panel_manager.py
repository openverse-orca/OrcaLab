from typing import override
import json
import pathlib

from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.ui.panel import Panel
from orcalab.ui.panel_area import PanelArea, PanelAreaVertical, PanelAreaHorizontal
from orcalab.ui.line import make_horizontal_line, make_vertical_line
from orcalab.ui.panel_bus import PanelRequest, PanelRequestBus


class PanelManager(QtWidgets.QWidget, PanelRequest):
    def __init__(self):
        super().__init__()

        # Window partition: Top area, Central area, Bottom area.

        window_top_area_height = 32
        window_bottom_area_height = 32

        window_top_area = QtWidgets.QWidget()
        window_central_area = QtWidgets.QWidget()
        window_bottom_area = QtWidgets.QWidget()

        window_top_area.setFixedHeight(window_top_area_height)
        window_bottom_area.setFixedHeight(window_bottom_area_height)

        window_layout = QtWidgets.QVBoxLayout(self)
        window_layout.setContentsMargins(0, 0, 0, 0)
        window_layout.setSpacing(0)
        window_layout.addWidget(window_top_area)
        window_layout.addWidget(make_horizontal_line())
        window_layout.addWidget(window_central_area, 1)
        window_layout.addWidget(make_horizontal_line())
        # window_layout.addWidget(window_bottom_area)

        # Window top area = Menu bar + Manipulator bar + Tool bar

        menu_bar = QtWidgets.QWidget()
        tool_bar = QtWidgets.QWidget()
        manipulator_bar = QtWidgets.QWidget()

        window_top_area_layout = QtWidgets.QHBoxLayout(window_top_area)
        window_top_area_layout.setContentsMargins(0, 0, 0, 0)
        window_top_area_layout.setSpacing(0)
        window_top_area_layout.addWidget(menu_bar)
        window_top_area_layout.addStretch(1)
        window_top_area_layout.addWidget(manipulator_bar)
        window_top_area_layout.addStretch(1)
        window_top_area_layout.addWidget(tool_bar)

        # Window central area.

        splitter_v = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        splitter_h = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        left_panel_bar_width = 48
        right_panel_bar_width = 48

        left_panel_bar = QtWidgets.QWidget()
        right_panel_bar = QtWidgets.QWidget()

        left_panel_bar.setFixedWidth(left_panel_bar_width)
        right_panel_bar.setFixedWidth(right_panel_bar_width)

        left_panel_area = PanelAreaVertical("left")
        main_content_area = QtWidgets.QWidget()
        right_panel_area = PanelAreaVertical("right")
        bottom_panel_area = PanelAreaHorizontal("bottom")

        main_content_area.setMinimumSize(64, 64)

        window_central_area_layout = QtWidgets.QHBoxLayout(window_central_area)
        window_central_area_layout.setContentsMargins(0, 0, 0, 0)
        window_central_area_layout.setSpacing(0)
        window_central_area_layout.addWidget(left_panel_bar)
        window_central_area_layout.addWidget(make_vertical_line())
        window_central_area_layout.addWidget(splitter_v)
        window_central_area_layout.addWidget(make_vertical_line())
        window_central_area_layout.addWidget(right_panel_bar)

        splitter_v.addWidget(splitter_h)
        splitter_v.addWidget(bottom_panel_area)

        splitter_h.addWidget(left_panel_area)
        splitter_h.addWidget(main_content_area)
        splitter_h.addWidget(right_panel_area)
        splitter_h.setStretchFactor(1, 1)
        splitter_h.setCollapsible(1, False)

        # Left panel bar.

        layout = QtWidgets.QVBoxLayout(left_panel_bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(left_panel_area.panel_button_group)
        layout.addStretch(1)
        layout.addWidget(bottom_panel_area.panel_button_group)

        # Right panel bar.

        layout = QtWidgets.QVBoxLayout(right_panel_bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(right_panel_area.panel_button_group)
        layout.addStretch(1)

        # Store references.

        self._menu_bar_area = menu_bar
        self._tool_bar_area = tool_bar
        self._manipulator_bar_area = manipulator_bar
        self._left_panel_area = left_panel_area
        self._right_panel_area = right_panel_area
        self._bottom_panel_area = bottom_panel_area
        self._main_content_area = main_content_area
        self._splitter_v = splitter_v
        self._splitter_h = splitter_h

    def connect_buses(self):
        PanelRequestBus.connect(self)

    def disconnect_buses(self):
        PanelRequestBus.disconnect(self)

    def iterate_panels(self):
        for panel in self._left_panel_area.panels:
            yield panel, self._left_panel_area
        for panel in self._right_panel_area.panels:
            yield panel, self._right_panel_area
        for panel in self._bottom_panel_area.panels:
            yield panel, self._bottom_panel_area

    def iterate_panel_areas(self):
        yield self._left_panel_area
        yield self._right_panel_area
        yield self._bottom_panel_area

    def add_panel(self, panel: Panel, panel_area_name: str):
        if not isinstance(panel, Panel):
            raise TypeError("panel must be an instance of Panel")

        for existing_panel, panel_area in self.iterate_panels():
            if existing_panel.panel_name == panel.panel_name:
                raise ValueError(f"A panel '{panel.panel_name}' already exists.")

        for panel_area in self.iterate_panel_areas():
            if panel_area_name == panel_area.name:
                panel_area.add_panel(panel)
                return

        raise ValueError(f"No panel area '{panel_area_name}' found.")

    @override
    def open_panel(self, panel_name: str):
        for panel, panel_area in self.iterate_panels():
            if panel.panel_name == panel_name:
                self.open_panel_area(panel_area.name)
                panel_area.open_panel(panel_name)
                return

        raise ValueError(f"No panel with the name '{panel_name}' found.")

    @override
    def close_panel(self, panel_name: str):
        for panel, panel_area in self.iterate_panels():
            if panel.panel_name == panel_name:
                panel_area.close_panel(panel_name)
                return

        raise ValueError(f"No panel with the name '{panel_name}' found.")

    @override
    def open_panel_area(self, name):
        for panel_area in self.iterate_panel_areas():
            if name == panel_area.name:
                self._open_panel_area(panel_area)
                return
        raise ValueError(f"No panel area '{name}' found.")

    @override
    def close_panel_area(self, name):
        for panel_area in self.iterate_panel_areas():
            if name == panel_area.name:
                self._close_panel_area(panel_area)
                return
        raise ValueError(f"No panel area '{name}' found.")

    def _open_panel_area(self, panel_area: PanelArea):
        if panel_area.isVisible():
            return

        panel_area.show()

        panel_area_size = panel_area.panel_area_size

        if panel_area == self._left_panel_area:
            new_sizes = [0, 0, 0]
            new_sizes[0] = panel_area_size
            new_sizes[1] = self._main_content_area.width() - panel_area_size
            new_sizes[2] = self._right_panel_area.width()
            self._splitter_h.setSizes(new_sizes)
        elif panel_area == self._right_panel_area:
            new_sizes = [0, 0, 0]
            new_sizes[0] = self._left_panel_area.width()
            new_sizes[1] = self._main_content_area.width() - panel_area_size
            new_sizes[2] = panel_area_size
            self._splitter_h.setSizes(new_sizes)
        elif panel_area == self._bottom_panel_area:
            new_sizes = [0, 0]
            new_sizes[0] = self._splitter_h.height() - panel_area_size
            new_sizes[1] = panel_area_size
            self._splitter_v.setSizes(new_sizes)

    def _close_panel_area(self, panel_area: PanelArea):
        panel_area.save_size()
        panel_area.hide()

    def restore_default_layout(self):
        self._splitter_h.setSizes([400, 1200, 400])
        self._splitter_v.setSizes([600, 200])

        for panel_area in self.iterate_panel_areas():
            if len(panel_area.panels) > 0:
                panel_area.show()
                panel_area.open_panel(panel_area.panels[0])
            else:
                self.close_panel_area(panel_area.name)

    def save_layout_to_dict(self, layout_data: dict):
        layout_data["left_panel_area"] = {
            "size": self._left_panel_area.get_save_size(),
            "open": self._left_panel_area.isVisible(),
        }
        layout_data["main_content_area"] = {
            "width": self._main_content_area.width(),
            "height": self._main_content_area.height(),
        }
        layout_data["right_panel_area"] = {
            "size": self._right_panel_area.get_save_size(),
            "open": self._right_panel_area.isVisible(),
        }
        layout_data["bottom_panel_area"] = {
            "size": self._bottom_panel_area.get_save_size(),
            "open": self._bottom_panel_area.isVisible(),
        }

        self._left_panel_area.save_layout_to_dict(layout_data["left_panel_area"])
        self._right_panel_area.save_layout_to_dict(layout_data["right_panel_area"])
        self._bottom_panel_area.save_layout_to_dict(layout_data["bottom_panel_area"])

    def load_layout_from_dict(self, layout_data: dict):
        try:
            main_content_height = int(layout_data["main_content_area"]["height"])
            bottom_panel_size = int(layout_data["bottom_panel_area"]["size"])
            bottom_panel_open = bool(layout_data["bottom_panel_area"]["open"])

            new_sizes = [main_content_height, bottom_panel_size]

            if not bottom_panel_open:
                new_sizes[1] = 0
                self._bottom_panel_area.panel_area_size = bottom_panel_size
                self._bottom_panel_area.hide()

            self._splitter_v.setSizes(new_sizes)

            left_panel_size = int(layout_data["left_panel_area"]["size"])
            main_content_width = int(layout_data["main_content_area"]["width"])
            right_panel_size = int(layout_data["right_panel_area"]["size"])
            left_panel_open = bool(layout_data["left_panel_area"]["open"])
            right_panel_open = bool(layout_data["right_panel_area"]["open"])

            new_sizes = [left_panel_size, main_content_width, right_panel_size]
            if not left_panel_open:
                new_sizes[0] = 0
                self._left_panel_area.panel_area_size = left_panel_size
                self._left_panel_area.hide()

            if not right_panel_open:
                new_sizes[2] = 0
                self._right_panel_area.panel_area_size = right_panel_size
                self._right_panel_area.hide()

            self._splitter_h.setSizes(new_sizes)

            self._left_panel_area.load_layout_from_dict(layout_data["left_panel_area"])
            self._right_panel_area.load_layout_from_dict(
                layout_data["right_panel_area"]
            )
            self._bottom_panel_area.load_layout_from_dict(
                layout_data["bottom_panel_area"]
            )

        except Exception as e:
            self.restore_default_layout()
