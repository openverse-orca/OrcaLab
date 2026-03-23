import asyncio

from PySide6 import QtCore, QtGui, QtWidgets

from orcalab.config_service import ConfigService
from orcalab.remote_scene import RemoteScene
from orcalab.ui.checkbox import CheckBox
from orcalab.ui.text_label import TextLabel
from orcalab.ui.theme_service import ThemeService

# 设置行内部水平边距；统计区与底部按钮使用相同值，与标题/正文左缘对齐
_SETTING_BLOCK_H_MARGIN = 12

_MOVE_SENS_RANGE = (0.1, 5.0)
_ROT_SENS_RANGE = (0.1, 15.0)


def _sensitivity_line_edit(lo: float, hi: float, value: float) -> QtWidgets.QLineEdit:
    """带边框的数值框，仅能通过键盘手动输入（无步进/滚轮改值）。"""
    edit = QtWidgets.QLineEdit()
    edit.setObjectName("OrcaSettingsNumericField")
    edit.setValidator(QtGui.QDoubleValidator(lo, hi, 1, edit))
    edit.setText(f"{value:.1f}")
    edit.setFixedWidth(96)
    return edit


def _read_sensitivity_line(
    edit: QtWidgets.QLineEdit, fallback: float, lo: float, hi: float
) -> float:
    t = edit.text().strip().replace(",", ".")
    if not t:
        v = fallback
    else:
        try:
            v = float(t)
        except ValueError:
            v = fallback
    return round(max(lo, min(hi, v)), 1)


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
    *,
    style_description: bool = True,
) -> QtWidgets.QWidget:
    block = _SettingHoverBlock(hover_background)
    layout = QtWidgets.QVBoxLayout(block)
    layout.setContentsMargins(_SETTING_BLOCK_H_MARGIN, 5, _SETTING_BLOCK_H_MARGIN, 5)
    layout.setSpacing(4)

    title_label = TextLabel(title)
    title_label.setStyleSheet("font-size: 13px; font-weight: 600;")

    desc_label = TextLabel(description)
    if style_description:
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

        # —— 相机灵敏度：每项三行垂直（标题 / 说明 / 输入）—
        self.move_value_edit = _sensitivity_line_edit(
            *_MOVE_SENS_RANGE, config.camera_move_sensitivity()
        )
        root_layout.addWidget(
            _vscode_style_setting_row(
                "相机移动灵敏度",
                "控制相机平移时的移动速度",
                self.move_value_edit,
                self._setting_row_hover_bg,
            )
        )

        self.rotation_value_edit = _sensitivity_line_edit(
            *_ROT_SENS_RANGE, config.camera_rotation_sensitivity()
        )
        root_layout.addWidget(
            _vscode_style_setting_row(
                "相机旋转灵敏度",
                "控制相机旋转时的旋转速度",
                self.rotation_value_edit,
                self._setting_row_hover_bg,
            )
        )

        # —— 统计数据：紧挨相机区块下方，间隔由 root_layout.spacing() 控制 ——
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

        # self.checkbox = CheckBox()
        # self.checkbox.set_checked(config.send_statistics() == "true")
        # root_layout.addWidget(
        #     _vscode_style_setting_row(
        #         "统计数据",
        #         "发送用统计数据可以帮助改进OrcaLab。",
        #         self.checkbox,
        #         self._setting_row_hover_bg,
        #         style_description=False,
        #     )
        # )

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

        self.resize(1024, 720)

    def _apply_theme(self):
        theme = ThemeService()
        bg_color = theme.get_color_hex("bg")
        text_color = theme.get_color_hex("text")
        split_line_color = theme.get_color_hex("split_line")
        button_bg = theme.get_color_hex("button_bg")
        button_bg_hover = theme.get_color_hex("button_bg_hover")
        button_bg_pressed = theme.get_color_hex("button_bg_pressed")
        field_focus_border = theme.get_color_hex("button_bg_selected")

        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {bg_color};
                color: {text_color};
            }}
            QLineEdit#OrcaSettingsNumericField {{
                border: 1px solid {split_line_color};
                border-radius: 3px;
                padding: 3px 6px;
                background-color: {button_bg};
                color: {text_color};
                font-size: 12px;
            }}
            QLineEdit#OrcaSettingsNumericField:focus {{
                border: 1px solid {field_focus_border};
            }}
            QLineEdit#OrcaSettingsNumericField:disabled {{
                color: {theme.get_color_hex("text_disable")};
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
        move = _read_sensitivity_line(
            self.move_value_edit,
            config.camera_move_sensitivity(),
            *_MOVE_SENS_RANGE,
        )
        rot = _read_sensitivity_line(
            self.rotation_value_edit,
            config.camera_rotation_sensitivity(),
            *_ROT_SENS_RANGE,
        )
        config.set_camera_move_sensitivity(move)
        config.set_camera_rotation_sensitivity(rot)
        config.set_send_statistics("true" if self.checkbox.checked() else "false")
        if self._remote_scene is not None:
            asyncio.create_task(
                self._remote_scene.set_move_rotate_sensitivity(move, rot)
            )
        super().accept()
