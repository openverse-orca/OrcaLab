from typing import override

from PySide6 import QtCore, QtWidgets, QtGui
from orcalab.state_sync_bus import (
    ManipulatorType,
    CameraMovementType,
    MeasureType,
    PivotPointType,
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
    recursive_display_changed = QtCore.Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._layout = QtWidgets.QHBoxLayout()
        self._layout.setContentsMargins(8, 0, 8, 0)
        self._layout.setSpacing(8)
        self.setLayout(self._layout)

        self._debug_draw = False
        self._grab = False
        self._recursive = False

        button_size = QtCore.QSize(32, 32)
        icon_size = 24

        theme = ThemeService()

        icon_color = theme.get_color("tool_icon")
        
        self.icon_color = theme.get_color("tool_icon")
        self.bg_color = theme.get_color("button_bg")
        self.bg_color_selected = theme.get_color("button_bg_selected")

        self.move_button = Button(icon=make_icon(":/icons/move.svg", icon_color))
        self.move_button.setToolTip("移动(快捷键:1)")
        self.move_button.setFixedSize(button_size)
        self.move_button.icon_size = icon_size
        self.move_button.bg_color = self.bg_color_selected

        self.rotate_button = Button(icon=make_icon(":/icons/rotate.svg", icon_color))
        self.rotate_button.setToolTip("旋转(快捷键:2)")
        self.rotate_button.setFixedSize(button_size)
        self.rotate_button.icon_size = icon_size

        self.scale_button = Button(icon=make_icon(":/icons/scale.svg", icon_color))
        self.scale_button.setToolTip("缩放(快捷键:3)")
        self.scale_button.setFixedSize(button_size)
        self.scale_button.icon_size = icon_size

        self.camera_move_button = Button(icon=make_icon(":/icons/camera_translate.svg", icon_color))
        self.camera_move_button.setToolTip("相机移动(快捷键:4)")
        self.camera_move_button.setFixedSize(button_size)
        self.camera_move_button.icon_size = icon_size
        self.camera_move_button.bg_color = self.bg_color

        self.camera_rotate_button = Button(icon=make_icon(":/icons/camera_rotate.svg", icon_color))
        self.camera_rotate_button.setToolTip("相机旋转(快捷键:5)")
        self.camera_rotate_button.setFixedSize(button_size)
        self.camera_rotate_button.icon_size = icon_size

        self.camera_scale_button = Button(icon=make_icon(":/icons/camera_scale.svg", icon_color))
        self.camera_scale_button.setToolTip("相机缩放(快捷键:6)")
        self.camera_scale_button.setFixedSize(button_size)
        self.camera_scale_button.icon_size = icon_size

        self.measure_distance_button = Button(icon=make_icon(":/icons/distance.svg", icon_color))
        self.measure_distance_button.setToolTip("测距离")
        self.measure_distance_button.setFixedSize(button_size)
        self.measure_distance_button.icon_size = icon_size

        self.measure_angle_button = Button(icon=make_icon(":/icons/angle.svg", icon_color))
        self.measure_angle_button.setToolTip("测角度")
        self.measure_angle_button.setFixedSize(button_size)
        self.measure_angle_button.icon_size = icon_size

        self.debug_button = Button(icon=make_icon(":/icons/physics.png", icon_color))
        self.debug_button.setToolTip("显示物理(F4)")
        self.debug_button.setFixedSize(button_size)
        self.debug_button.icon_size = icon_size

        self.pivot_point_button = Button(icon=make_icon(":/icons/median_point.svg", icon_color))
        self.pivot_point_button.setToolTip("枢轴点:中位点")
        self.pivot_point_button.setFixedSize(button_size)
        self.pivot_point_button.icon_size = icon_size
        self.pivot_point_button.bg_color = self.bg_color_selected

        # 创建枢轴点下拉菜单
        self.pivot_point_menu = QtWidgets.QMenu()
        self.pivot_point_menu.setStyleSheet("""
            QMenuBar {
                background-color: #3c3c3c;
                color: #ffffff;
                border-bottom: 1px solid #404040;
            }
            QMenuBar::item {
                background-color: transparent;
            }
            QMenuBar::item:selected {
                background-color: #4a4a4a;
            }
            QMenuBar::item:pressed {
                background-color: #2a2a2a;
            }
            QMenu {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #404040;
                border-radius: 3px;
            }
            QMenu::item {
                padding: 6px 20px 6px 0px;
            }
            QMenu::item:selected {
                background-color: #4a4a4a;
            }
            QMenu::item:disabled {
                color: #aaaaaa; /* Light gray text */
                background-color: transparent;
            }
             QMenu::item:checked {
                background-color: #2a2a2a;
                color: #ffffff;
            }
            QMenu::item:checked:selected {
                background-color: #555555;
            }
            QMenu::indicator {
                width: 14px;
                height: 14px;

                margin-left: 8px;
                margin-right: 6px;
            }    
        """)
        self.pivot_individual_origin_action = self.pivot_point_menu.addAction("各自中心")
        self.pivot_bounding_box_action = self.pivot_point_menu.addAction("包围盒中心")
        self.pivot_meadian_point_action = self.pivot_point_menu.addAction("中位点")
        self.pivot_active_actor_action = self.pivot_point_menu.addAction("激活的物体")

        for action in [
            self.pivot_individual_origin_action,
            self.pivot_bounding_box_action,
            self.pivot_meadian_point_action,
            self.pivot_active_actor_action,
        ]:
            action.setCheckable(True)
        self.pivot_meadian_point_action.setChecked(True)
        connect(self.pivot_point_button.mouse_pressed, self.show_pivot_menu)

        self.runtime_grab_button = Button(icon=make_icon(":/icons/grab.png", icon_color))
        self.runtime_grab_button.setEnabled(False)
        self.runtime_grab_button.setToolTip("仿真时可用")
        self.runtime_grab_button.setFixedSize(button_size)
        self.runtime_grab_button.icon_size = icon_size

        self.recursive_button = Button(icon=make_icon(":/icons/recursive.svg", icon_color))
        self.recursive_button.setToolTip("递归显示")
        self.recursive_button.setFixedSize(button_size)
        self.recursive_button.icon_size = icon_size

        self.sep_1 = make_vertical_line(2)
        self.sep_2 = make_vertical_line(2)
        self.sep_3 = make_vertical_line(2)
        self.sep_4 = make_vertical_line(2)
        self.sep_5 = make_vertical_line(2)

        self._layout.addWidget(self.move_button)
        self._layout.addWidget(self.rotate_button)
        self._layout.addWidget(self.scale_button)
        self._layout.addWidget(self.sep_1)
        self._layout.addWidget(self.camera_move_button)
        self._layout.addWidget(self.camera_rotate_button)
        self._layout.addWidget(self.camera_scale_button)
        self._layout.addWidget(self.sep_2)
        self._layout.addWidget(self.measure_distance_button)
        self._layout.addWidget(self.measure_angle_button)
        self._layout.addWidget(self.sep_3)
        self._layout.addWidget(self.pivot_point_button)
        self._layout.addWidget(self.sep_4)
        self._layout.addWidget(self.debug_button)
        self._layout.addWidget(self.sep_5)
        self._layout.addWidget(self.runtime_grab_button)
        self._layout.addWidget(self.recursive_button)

        connect(self.move_button.mouse_pressed, self.set_translation)
        connect(self.rotate_button.mouse_pressed, self.set_rotation)
        connect(self.scale_button.mouse_pressed, self.set_scale)
        connect(self.camera_move_button.mouse_pressed, self.set_camera_translation)
        connect(self.camera_rotate_button.mouse_pressed, self.set_camera_rotation)
        connect(self.camera_scale_button.mouse_pressed, self.set_camera_scale)
        connect(self.measure_distance_button.mouse_pressed, self.set_measure_distance)
        connect(self.measure_angle_button.mouse_pressed, self.set_measure_angle)
        connect(self.debug_button.mouse_pressed, self.set_debug_draw)
        connect(self.runtime_grab_button.mouse_pressed, self.set_runtime_grab)
        connect(self.recursive_button.mouse_pressed, self.set_recursive_display)
        connect(self.pivot_individual_origin_action.triggered, self.set_pivot_individual_center)
        connect(self.pivot_bounding_box_action.triggered, self.set_pivot_bounding_box)
        connect(self.pivot_meadian_point_action.triggered, self.set_pivot_median_point)
        connect(self.pivot_active_actor_action.triggered, self.set_pivot_active_actor)

    def connect_bus(self):
        StateSyncNotificationBus.connect(self)

    def disconnect_bus(self):
        StateSyncNotificationBus.disconnect(self)

    def start_sim(self):
        self.scale_button.setEnabled(False)
        self.scale_button.setToolTip("仿真时无法缩放物体")
        self.measure_distance_button.setEnabled(False)
        self.measure_distance_button.setToolTip("仿真时不可用")
        self.measure_angle_button.setEnabled(False)
        self.measure_angle_button.setToolTip("仿真时不可用")
        self.runtime_grab_button.setEnabled(True)
        self.runtime_grab_button.setToolTip("抓取(F3)")

    def end_sim(self):
        self.scale_button.setEnabled(True)
        self.scale_button.setToolTip("缩放(快捷键:3)")
        self.measure_distance_button.setEnabled(True)
        self.measure_distance_button.setToolTip("测距离")
        self.measure_angle_button.setEnabled(True)
        self.measure_angle_button.setToolTip("测角度")
        self.runtime_grab_button.setEnabled(False)
        self.runtime_grab_button.setToolTip("仿真时可用")

    async def set_translation(self):
        bus = StateSyncRequestBus()
        await bus.set_manipulator_type(ManipulatorType.Translate)
        await bus.set_camera_movement_type(CameraMovementType.CameraNone)
        await bus.set_measure_type(MeasureType.MeasureNone)

    async def set_rotation(self):
        bus = StateSyncRequestBus()
        await bus.set_manipulator_type(ManipulatorType.Rotate)
        await bus.set_camera_movement_type(CameraMovementType.CameraNone)
        await bus.set_measure_type(MeasureType.MeasureNone)

    async def set_scale(self):
        bus = StateSyncRequestBus()
        await bus.set_manipulator_type(ManipulatorType.Scale)
        await bus.set_camera_movement_type(CameraMovementType.CameraNone)
        await bus.set_measure_type(MeasureType.MeasureNone)

    async def set_camera_translation(self):
        bus = StateSyncRequestBus()
        await bus.set_camera_movement_type(CameraMovementType.CameraTranslate)
        await bus.set_manipulator_type(ManipulatorType.ManipulatorNone)
        await bus.set_measure_type(MeasureType.MeasureNone)

    async def set_camera_rotation(self):
        bus = StateSyncRequestBus()
        await bus.set_camera_movement_type(CameraMovementType.CameraRotate)
        await bus.set_manipulator_type(ManipulatorType.ManipulatorNone)
        await bus.set_measure_type(MeasureType.MeasureNone)

    async def set_camera_scale(self):
        bus = StateSyncRequestBus()
        await bus.set_camera_movement_type(CameraMovementType.CameraScale)
        await bus.set_manipulator_type(ManipulatorType.ManipulatorNone)
        await bus.set_measure_type(MeasureType.MeasureNone)

    async def set_measure_distance(self):
        bus = StateSyncRequestBus()
        await bus.set_measure_type(MeasureType.Distance)
        await bus.set_manipulator_type(ManipulatorType.ManipulatorNone)
        await bus.set_camera_movement_type(CameraMovementType.CameraNone)

    async def set_measure_angle(self):
        bus = StateSyncRequestBus()
        await bus.set_measure_type(MeasureType.Angle)
        await bus.set_manipulator_type(ManipulatorType.ManipulatorNone)
        await bus.set_camera_movement_type(CameraMovementType.CameraNone)

    def show_pivot_menu(self):
        self.pivot_point_menu.exec(self.pivot_point_button.mapToGlobal(QtCore.QPoint(0, self.pivot_point_button.height())))

    async def set_pivot_individual_center(self):
        bus = StateSyncRequestBus()
        await bus.set_pivot_point_type(PivotPointType.IndividualCenter)

    async def set_pivot_bounding_box(self):
        bus = StateSyncRequestBus()
        await bus.set_pivot_point_type(PivotPointType.BoundingBoxCenter)

    async def set_pivot_median_point(self):
        bus = StateSyncRequestBus()
        await bus.set_pivot_point_type(PivotPointType.MedianPoint)

    async def set_pivot_active_actor(self):
        bus = StateSyncRequestBus()
        await bus.set_pivot_point_type(PivotPointType.ActiveActor)

    @override
    def on_manipulator_type_changed(self, type: ManipulatorType):
        self.move_button.bg_color = self.bg_color
        self.rotate_button.bg_color = self.bg_color
        self.scale_button.bg_color = self.bg_color

        if type == ManipulatorType.Translate:
            self.move_button.bg_color = self.bg_color_selected
        elif type == ManipulatorType.Rotate:
            self.rotate_button.bg_color = self.bg_color_selected
        elif type == ManipulatorType.Scale:
            self.scale_button.bg_color = self.bg_color_selected

        self.move_button.update()
        self.rotate_button.update()
        self.scale_button.update()

    @override
    def on_camera_movement_type_changed(self, type: CameraMovementType):
        self.camera_move_button.bg_color = self.bg_color
        self.camera_rotate_button.bg_color = self.bg_color
        self.camera_scale_button.bg_color = self.bg_color

        if type == CameraMovementType.CameraTranslate:
            self.camera_move_button.bg_color = self.bg_color_selected
        elif type == CameraMovementType.CameraRotate:
            self.camera_rotate_button.bg_color = self.bg_color_selected
        elif type == CameraMovementType.CameraScale:
            self.camera_scale_button.bg_color = self.bg_color_selected

        self.camera_move_button.update()
        self.camera_rotate_button.update()
        self.camera_scale_button.update()

    @override
    def on_measure_type_changed(self,  type: MeasureType):
        self.measure_distance_button.bg_color = self.bg_color
        self.measure_angle_button.bg_color = self.bg_color

        if type == MeasureType.Distance:
            self.measure_distance_button.bg_color = self.bg_color_selected
        elif type == MeasureType.Angle:
            self.measure_angle_button.bg_color = self.bg_color_selected

        self.measure_distance_button.update()
        self.measure_angle_button.update()

    async def set_debug_draw(self):
        bus = StateSyncRequestBus()
        await bus.set_debug_draw(not self._debug_draw)

    @override
    def on_pivot_point_type_changed(self, type: PivotPointType):
        for action in [
            self.pivot_individual_origin_action,
            self.pivot_bounding_box_action,
            self.pivot_meadian_point_action,
            self.pivot_active_actor_action,
        ]:
            action.setChecked(False)
        if type == PivotPointType.IndividualCenter:
            self.pivot_point_button.setIcon(make_icon(":/icons/individual_center.svg", self.icon_color))
            self.pivot_point_button.setToolTip("枢轴点:各自中心")
            self.pivot_individual_origin_action.setChecked(True)
        elif type == PivotPointType.BoundingBoxCenter:
            self.pivot_point_button.setIcon(make_icon(":/icons/boundingbox_center.svg", self.icon_color))
            self.pivot_point_button.setToolTip("枢轴点:包围盒中心")
            self.pivot_bounding_box_action.setChecked(True)
        elif type == PivotPointType.MedianPoint:
            self.pivot_point_button.setIcon(make_icon(":/icons/median_point.svg", self.icon_color))
            self.pivot_point_button.setToolTip("枢轴点:中位点")
            self.pivot_meadian_point_action.setChecked(True)
        elif type == PivotPointType.ActiveActor:
            self.pivot_point_button.setIcon(make_icon(":/icons/active_actor.svg", self.icon_color))
            self.pivot_point_button.setToolTip("枢轴点:激活的物体")
            self.pivot_active_actor_action.setChecked(True)
        self.pivot_point_button.update()

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

    async def set_recursive_display(self):
        self._recursive = not self._recursive
        if self._recursive:
            self.recursive_button.bg_color = self.bg_color_selected
        else:
            self.recursive_button.bg_color = self.bg_color
        self.recursive_button.update()
        self.recursive_display_changed.emit(self._recursive)

    @override
    def on_runtime_grab_changed(self, enabled: bool):
        self._grab = enabled
        if self._grab:
            self.runtime_grab_button.bg_color = self.bg_color_selected
        else:
            self.runtime_grab_button.bg_color = self.bg_color

        self.runtime_grab_button.update()
