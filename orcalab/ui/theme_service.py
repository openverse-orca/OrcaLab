from PySide6 import QtCore, QtWidgets, QtGui
from typing import Dict


# ThemeService is a singleton
class ThemeService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)

            # Add any initialization logic here if needed

            cls._instance._init()

        return cls._instance

    def _init(self):
        self._colors: Dict[str, QtGui.QColor] = {}

        self.set_color("bg", "#181818")
        self.set_color("bg_hover", "#323232")
        self.set_color("bg_selection", "#505050")
        self.set_color("text", "#FFFFFF")
        self.set_color("text_disable", "#888888")
        self.set_color("split_line", "#2b2b2b")
        self.set_color("button_bg", "#181818")
        self.set_color("button_bg_hover", "#444444")
        self.set_color("button_bg_pressed", "#555555")
        self.set_color("button_text", "#FFFFFF")
        self.set_color("button_text_hover", "#FFFFFF")
        self.set_color("button_text_pressed", "#FFFFFF")
        self.set_color("panel_icon", "#C2C2C2")

        self.set_color("brand", "#F02C6D")

        self.set_color("property_group_bg", "#676767")
        self.set_color("property_edit_bg", "#8F8E8E")
        self.set_color("property_edit_bg_hover", "#9D9D9D")
        self.set_color("property_edit_bg_editing", "#181818")

        self.set_color("scrollbar_handle_bg", "#676767")
        self.set_color("scrollbar_handle_bg_hover", "#9D9D9D")


    def set_color(self, name: str, color: str):
        self._colors[name] = QtGui.QColor(color)

    def get_color(self, name: str) -> QtGui.QColor:
        return self._colors[name]

    def get_color_hex(self, name: str) -> str:
        return self._colors[name].name()
