import asyncio
from typing import override

from PySide6 import QtCore, QtGui, QtWidgets

from orcalab.config_service import ConfigService
from orcalab.pyside_util import connect
from orcalab.remote_scene import RemoteScene
from orcalab.ui.checkbox import CheckBox
from orcalab.ui.edit.float_edit import FloatEdit
from orcalab.ui.property_edit.base_property_edit import get_property_edit_style_sheet
from orcalab.ui.text_label import TextLabel
from orcalab.ui.theme_service import ThemeService

# 设置行内部水平边距；统计区与底部按钮使用相同值，与标题/正文左缘对齐
_SETTING_BLOCK_H_MARGIN = 12


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


class _SettingHoverBlock(QtWidgets.QWidget):
    """整块设置区域悬停时背景变浅（子控件上悬停也生效）。"""

    def __init__(self, hover_bg_hex: str, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._hover_bg = hover_bg_hex
        self._hover = False
        self.setObjectName("OrcaSettingRow")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self._sync_style()

    def enterEvent(self, event: QtGui.QEnterEvent) -> None:
        super().enterEvent(event)
        self._set_hover(True)

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        super().leaveEvent(event)
        QtCore.QTimer.singleShot(0, self._sync_hover_after_leave)

    def _sync_hover_after_leave(self) -> None:
        local = self.mapFromGlobal(QtGui.QCursor.pos())
        self._set_hover(self.rect().contains(local))

    def _set_hover(self, on: bool) -> None:
        if on == self._hover:
            return
        self._hover = on
        self._sync_style()

    def _sync_style(self) -> None:
        bg = self._hover_bg if self._hover else "transparent"
        self.setStyleSheet(
            f"QWidget#OrcaSettingRow {{ background-color: {bg}; border-radius: 6px; }}"
        )


def _vscode_style_setting_row(
    title: str,
    description: str,
    control: QtWidgets.QWidget,
    hover_background: str,
) -> QtWidgets.QWidget:
    block = _SettingHoverBlock(hover_background)
    layout = QtWidgets.QVBoxLayout(block)
    layout.setContentsMargins(_SETTING_BLOCK_H_MARGIN, 5, _SETTING_BLOCK_H_MARGIN, 5)
    layout.setSpacing(4)

    title_label = TextLabel(title)
    title_label.setStyleSheet("font-size: 13px; font-weight: 600;")

    desc_label = TextLabel(description)
    desc_label.setStyleSheet("color: #888888; font-size: 12px;")

    control_row = QtWidgets.QHBoxLayout()
    control_row.setContentsMargins(0, 8, 0, 0)
    control_row.setSpacing(0)
    control_row.addWidget(control, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
    control_row.addStretch()

    layout.addWidget(title_label)
    layout.addWidget(desc_label)
    layout.addLayout(control_row)

    return block


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, remote_scene: RemoteScene | None = None):
        super().__init__(parent)
        self._remote_scene = remote_scene
        self.setWindowTitle("设置")
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)

        theme = ThemeService()
        self._setting_row_hover_bg = theme.get_color_hex("bg_hover")

        self._apply_theme()

        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setSpacing(20)
        root_layout.setContentsMargins(24, 24, 24, 20)

        config = ConfigService()
        prop_style = get_property_edit_style_sheet()

        # —— 统计数据（水平内边距与下方设置行一致）——
        stats_desc = TextLabel("发送用统计数据可以帮助改进OrcaLab。")
        stats_checkbox = CheckBox()
        stats_row = QtWidgets.QHBoxLayout()
        stats_row.setContentsMargins(
            _SETTING_BLOCK_H_MARGIN, 0, _SETTING_BLOCK_H_MARGIN, 0
        )
        stats_row.addWidget(stats_checkbox, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        stats_row.addWidget(stats_desc, 1, QtCore.Qt.AlignmentFlag.AlignVCenter)
        stats_row.addStretch()

        self.checkbox = stats_checkbox
        send_statistics = config.send_statistics()
        self.checkbox.set_checked(send_statistics == "true")

        root_layout.addLayout(stats_row)

        # —— 相机灵敏度：每项三行垂直（标题 / 说明 / 输入）——
        camera_section = QtWidgets.QWidget()
        camera_layout = QtWidgets.QVBoxLayout(camera_section)
        camera_layout.setSpacing(22)

        self.move_value_edit = _RangedFloatEdit(0.1, 5.0, 0.1)
        self.move_value_edit.set_value(config.camera_move_sensitivity())
        self.move_value_edit.setStyleSheet(prop_style)
        self.move_value_edit.setFixedWidth(160)

        camera_layout.addWidget(
            _vscode_style_setting_row(
                "相机移动灵敏度",
                "控制相机平移时的移动速度",
                self.move_value_edit,
                self._setting_row_hover_bg,
            )
        )

        self.rotation_value_edit = _RangedFloatEdit(0.1, 15.0, 0.1)
        self.rotation_value_edit.set_value(config.camera_rotation_sensitivity())
        self.rotation_value_edit.setStyleSheet(prop_style)
        self.rotation_value_edit.setFixedWidth(160)

        camera_layout.addWidget(
            _vscode_style_setting_row(
                "相机旋转灵敏度",
                "控制相机旋转时的旋转速度",
                self.rotation_value_edit,
                self._setting_row_hover_bg,
            )
        )

        root_layout.addWidget(camera_section)
        root_layout.addStretch()

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setContentsMargins(
            _SETTING_BLOCK_H_MARGIN, 0, _SETTING_BLOCK_H_MARGIN, 0
        )
        button_layout.addStretch()

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        cancel_btn = buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        if ok_btn is not None:
            ok_btn.setText("确定")
        if cancel_btn is not None:
            cancel_btn.setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        button_layout.addWidget(buttons)

        root_layout.addLayout(button_layout)

        self.resize(520, 420)

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
        config.set_send_statistics("true" if self.checkbox.checked() else "false")
        if self._remote_scene is not None:
            asyncio.create_task(
                self._remote_scene.set_move_rotate_sensitivity(move, rot)
            )
        super().accept()
