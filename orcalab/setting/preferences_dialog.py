import asyncio
from typing import override

from PySide6 import QtCore, QtGui, QtWidgets

from orcalab.config_service import ConfigService
from orcalab.remote_scene import RemoteScene
from orcalab.ui.edit.float_edit import FloatEdit
from orcalab.ui.property_edit.base_property_edit import get_property_edit_style_sheet
from orcalab.ui.text_label import TextLabel
from orcalab.ui.theme_service import ThemeService


class _RangedFloatEdit(FloatEdit):
    """与属性面板 FloatEdit 一致交互，并限制在 [min_value, max_value]，数值保留一位小数。"""

    def __init__(
        self,
        min_value: float,
        max_value: float,
        step: float,
        parent: QtWidgets.QWidget | None = None,
    ):
        super().__init__(parent, step)
        self._min_value = min_value
        self._max_value = max_value
        self.setValidator(
            QtGui.QDoubleValidator(self._min_value, self._max_value, 1, self)
        )

    @override
    def _value_to_text(self, value: float) -> str:
        return f"{value:.1f}"

    @override
    def _set_value_only(self, value: float) -> bool:
        rounded = round(float(value), 1)
        clamped = max(self._min_value, min(self._max_value, rounded))
        return super()._set_value_only(clamped)


class PreferencesDialog(QtWidgets.QDialog):
    """偏好设置对话框：相机移动速度、旋转速度等"""

    def __init__(self, parent=None, remote_scene: RemoteScene | None = None):
        super().__init__(parent)
        self._remote_scene = remote_scene
        self.setWindowTitle("偏好设置")
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)

        self._apply_theme()

        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setSpacing(20)
        root_layout.setContentsMargins(24, 24, 24, 20)

        config = ConfigService()
        prop_style = get_property_edit_style_sheet()

        camera_group = QtWidgets.QGroupBox("相机控制")
        camera_layout = QtWidgets.QVBoxLayout(camera_group)
        camera_layout.setSpacing(16)
        camera_layout.setContentsMargins(16, 20, 16, 16)

        # 相机移动灵敏度
        move_container = QtWidgets.QWidget()
        move_layout = QtWidgets.QVBoxLayout(move_container)
        move_layout.setContentsMargins(0, 0, 0, 0)
        move_layout.setSpacing(6)

        move_label = TextLabel("移动灵敏度")
        move_label.setStyleSheet("font-weight: 500;")
        move_desc = TextLabel("控制相机平移时的移动速度")
        move_desc.setStyleSheet("color: #888888; font-size: 11px;")

        move_layout.addWidget(move_label)
        move_layout.addWidget(move_desc)

        move_control = QtWidgets.QHBoxLayout()
        move_control.setSpacing(12)

        self.move_value_edit = _RangedFloatEdit(0.2, 5.0, 0.1)
        self.move_value_edit.set_value(config.camera_move_sensitivity())
        self.move_value_edit.setStyleSheet(prop_style)
        self.move_value_edit.setMinimumWidth(140)

        move_control.addWidget(move_container, 1)
        move_control.addWidget(self.move_value_edit, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        move_control.addStretch()

        camera_layout.addLayout(move_control)

        separator1 = QtWidgets.QFrame()
        separator1.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator1.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        camera_layout.addWidget(separator1)

        # 相机旋转灵敏度
        rot_container = QtWidgets.QWidget()
        rot_layout = QtWidgets.QVBoxLayout(rot_container)
        rot_layout.setContentsMargins(0, 0, 0, 0)
        rot_layout.setSpacing(6)

        rot_label = TextLabel("旋转灵敏度")
        rot_label.setStyleSheet("font-weight: 500;")
        rot_desc = TextLabel("控制相机旋转时的旋转速度")
        rot_desc.setStyleSheet("color: #888888; font-size: 11px;")

        rot_layout.addWidget(rot_label)
        rot_layout.addWidget(rot_desc)

        rot_control = QtWidgets.QHBoxLayout()
        rot_control.setSpacing(12)

        self.rotation_value_edit = _RangedFloatEdit(0.2, 15.0, 0.1)
        self.rotation_value_edit.set_value(config.camera_rotation_sensitivity())
        self.rotation_value_edit.setStyleSheet(prop_style)
        self.rotation_value_edit.setMinimumWidth(140)

        rot_control.addWidget(rot_container, 1)
        rot_control.addWidget(self.rotation_value_edit, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        rot_control.addStretch()

        camera_layout.addLayout(rot_control)

        root_layout.addWidget(camera_group)
        root_layout.addStretch()

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        button_layout.addWidget(buttons)

        root_layout.addLayout(button_layout)

        self.resize(480, 280)

    def _apply_theme(self):
        theme = ThemeService()
        bg_color = theme.get_color_hex("bg")
        text_color = theme.get_color_hex("text")
        split_line_color = theme.get_color_hex("split_line")
        button_bg = theme.get_color_hex("button_bg")
        button_bg_hover = theme.get_color_hex("button_bg_hover")
        button_bg_pressed = theme.get_color_hex("button_bg_pressed")

        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {bg_color};
                color: {text_color};
            }}
            QGroupBox {{
                border: 1px solid {split_line_color};
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 12px;
                font-size: 13px;
                font-weight: 600;
                color: {text_color};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px 0 6px;
            }}
            QPushButton {{
                background-color: {button_bg};
                border: 1px solid {split_line_color};
                border-radius: 4px;
                padding: 8px 20px;
                color: {text_color};
                font-size: 13px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {button_bg_hover};
                border-color: #505050;
            }}
            QPushButton:pressed {{
                background-color: {button_bg_pressed};
            }}
            QFrame[frameShape="5"] {{
                color: {split_line_color};
                max-height: 1px;
            }}
        """
        )

    def accept(self):
        config = ConfigService()
        move = self.move_value_edit.value()
        rot = self.rotation_value_edit.value()
        config.set_camera_move_sensitivity(move)
        config.set_camera_rotation_sensitivity(rot)
        if self._remote_scene is not None:
            asyncio.create_task(
                self._remote_scene.set_move_rotate_sensitivity(move, rot)
            )
        super().accept()