from typing import override

from PySide6 import QtCore, QtWidgets, QtGui
from orcalab.state_sync_bus import (
    ManipulatorType,
    StateSyncRequestBus,
    StateSyncNotification,
    StateSyncNotificationBus,
)
from orcalab.ui.icon_util import make_icon
from orcalab.ui.button import Button
from orcalab.pyside_util import connect
import orcalab.assets.rc_assets
from orcalab.ui.line import make_vertical_line
from orcalab.ui.theme_service import ThemeService


class ManipulatorBar(QtWidgets.QWidget, StateSyncNotification):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._layout = QtWidgets.QHBoxLayout()
        self._layout.setContentsMargins(8, 0, 8, 0)
        self._layout.setSpacing(8)
        self.setLayout(self._layout)

        self._debug_draw = False
        self._grab = False

        button_size = QtCore.QSize(32, 32)
        icon_size = 24

        theme = ThemeService()

        icon_color = theme.get_color("tool_icon")

        self.bg_color = theme.get_color("button_bg")
        self.bg_color_selected = theme.get_color("button_bg_selected")

        self.move_button = Button(icon=make_icon(":/icons/move.svg", icon_color))
        self.move_button.setToolTip("移动(快捷键:1)")
        self.move_button.setFixedSize(button_size)
        self.move_button.icon_size = icon_size

        self.rotate_button = Button(icon=make_icon(":/icons/rotate.svg", icon_color))
        self.rotate_button.setToolTip("旋转(快捷键:2)")
        self.rotate_button.setFixedSize(button_size)
        self.rotate_button.icon_size = icon_size

        self.scale_button = Button(icon=make_icon(":/icons/scale.svg", icon_color))
        self.scale_button.setToolTip("缩放(快捷键:3)")
        self.scale_button.setFixedSize(button_size)
        self.scale_button.icon_size = icon_size

        self.debug_button = Button(icon=make_icon(":/icons/physics.png", icon_color))
        self.debug_button.setToolTip("显示物理(F4)")
        self.debug_button.setFixedSize(button_size)
        self.debug_button.icon_size = icon_size

        self.runtime_grab_button = Button(icon=make_icon(":/icons/grab.png", icon_color))
        self.runtime_grab_button.setToolTip("抓取(F3)")
        self.runtime_grab_button.setFixedSize(button_size)
        self.runtime_grab_button.icon_size = icon_size

        self.sep_1 = make_vertical_line(2)
        self.sep_2 = make_vertical_line(2)

        self._layout.addWidget(self.move_button)
        self._layout.addWidget(self.rotate_button)
        self._layout.addWidget(self.scale_button)
        self._layout.addWidget(self.sep_1)
        self._layout.addWidget(self.debug_button)
        self._layout.addWidget(self.sep_2)
        self._layout.addWidget(self.runtime_grab_button)

        connect(self.move_button.mouse_pressed, self.set_translation)
        connect(self.rotate_button.mouse_pressed, self.set_rotation)
        connect(self.scale_button.mouse_pressed, self.set_scale)
        connect(self.debug_button.mouse_pressed, self.set_debug_draw)
        connect(self.runtime_grab_button.mouse_pressed, self.set_runtime_grab)

    def connect_buses(self):
        StateSyncNotificationBus.connect(self)

    def disconnect_buses(self):
        StateSyncNotificationBus.disconnect(self)

    async def set_translation(self):
        bus = StateSyncRequestBus()
        await bus.set_manipulator_type(ManipulatorType.Translate)

    async def set_rotation(self):
        bus = StateSyncRequestBus()
        await bus.set_manipulator_type(ManipulatorType.Rotate)

    async def set_scale(self):
        bus = StateSyncRequestBus()
        await bus.set_manipulator_type(ManipulatorType.Scale)

    @override
    def on_manipulator_type_changed(self, type: ManipulatorType):
        if type == ManipulatorType.Translate:
            self.move_button.bg_color = self.bg_color_selected
            self.rotate_button.bg_color = self.bg_color
            self.scale_button.bg_color = self.bg_color
        elif type == ManipulatorType.Rotate:
            self.move_button.bg_color = self.bg_color
            self.rotate_button.bg_color = self.bg_color_selected
            self.scale_button.bg_color = self.bg_color
        elif type == ManipulatorType.Scale:
            self.move_button.bg_color = self.bg_color
            self.rotate_button.bg_color = self.bg_color
            self.scale_button.bg_color = self.bg_color_selected

        self.move_button.update()
        self.rotate_button.update()
        self.scale_button.update()

    async def set_debug_draw(self):
        bus = StateSyncRequestBus()
        await bus.set_debug_draw(not self._debug_draw)

    @override
    def on_debug_draw_changed(self, enabled: bool):
        self._debug_draw = enabled
        if self._debug_draw:
            self.debug_button.bg_color = self.bg_color_selected
        else:
            self.debug_button.bg_color = self.bg_color

        self.debug_button.update()

    async def set_runtime_grab(self):
        bus = StateSyncRequestBus()
        await bus.set_runtime_grab(not self._grab)

    @override
    def on_runtime_grab_changed(self, enabled: bool):
        self._grab = enabled
        if self._grab:
            self.runtime_grab_button.bg_color = self.bg_color_selected
        else:
            self.runtime_grab_button.bg_color = self.bg_color

        self.runtime_grab_button.update()
