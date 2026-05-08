import asyncio
from collections.abc import Callable

from PySide6 import QtCore, QtGui, QtWidgets

from orcalab.config_service import ConfigService
from orcalab.remote_scene import RemoteScene
from orcalab.ui.checkbox import CheckBox
from orcalab.ui.text_label import TextLabel
from orcalab.ui.theme_service import ThemeService
from orcalab.ui.viewport import Viewport

# 设置行内部水平边距；统计区与底部按钮使用相同值，与标题/正文左缘对齐
_SETTING_BLOCK_H_MARGIN = 12

_MOVE_SENS_RANGE = (0.1, 10.0)
_ROT_SENS_RANGE = (0.1, 10.0)

_FPS_OPTIONS = [0, 30, 60, 90, 120, 144, 160, 240]

_AUTO_FPS_LABEL = "自动"


def _filtered_fps_options() -> list:
    screen_fps = Viewport._detect_screen_refresh_rate()
    result = [0]
    for fps in _FPS_OPTIONS:
        if fps > 0 and fps <= screen_fps:
            result.append(fps)
    if len(result) == 1:
        result.append(screen_fps)
    return result


class _SettingsNumericLineEdit(QtWidgets.QLineEdit):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._commit_normalize: Callable[[], None] | None = None

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() in (
            QtCore.Qt.Key.Key_Return,
            QtCore.Qt.Key.Key_Enter,
        ):
            if self._commit_normalize is not None:
                self._commit_normalize()
            self.clearFocus()
            event.accept()
            return
        super().keyPressEvent(event)


def _sensitivity_line_edit(lo: float, hi: float, value: float) -> _SettingsNumericLineEdit:
    edit = _SettingsNumericLineEdit()
    edit.setObjectName("OrcaSettingsNumericField")

    v = QtGui.QDoubleValidator(-1e9, 1e9, 10, edit)
    v.setNotation(QtGui.QDoubleValidator.Notation.StandardNotation)
    edit.setValidator(v)
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


def _normalize_sensitivity_line_edit(
    edit: QtWidgets.QLineEdit, fallback: float, lo: float, hi: float
) -> None:
    clamped = _read_sensitivity_line(edit, fallback, lo, hi)
    new_text = f"{clamped:.1f}"
    if edit.text() != new_text:
        edit.setText(new_text)


class _SettingHoverBlock(QtWidgets.QWidget):
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
        _norm_move = lambda: _normalize_sensitivity_line_edit(
            self.move_value_edit,
            ConfigService().camera_move_sensitivity(),
            *_MOVE_SENS_RANGE,
        )
        self.move_value_edit._commit_normalize = _norm_move
        self.move_value_edit.editingFinished.connect(_norm_move)
        root_layout.addWidget(
            _vscode_style_setting_row(
                "相机移动灵敏度",
                "控制相机平移时的移动速度 (范围: 0.1-10)",
                self.move_value_edit,
                self._setting_row_hover_bg,
            )
        )

        self.rotation_value_edit = _sensitivity_line_edit(
            *_ROT_SENS_RANGE, config.camera_rotation_sensitivity()
        )
        _norm_rot = lambda: _normalize_sensitivity_line_edit(
            self.rotation_value_edit,
            ConfigService().camera_rotation_sensitivity(),
            *_ROT_SENS_RANGE,
        )
        self.rotation_value_edit._commit_normalize = _norm_rot
        self.rotation_value_edit.editingFinished.connect(_norm_rot)
        root_layout.addWidget(
            _vscode_style_setting_row(
                "相机旋转灵敏度",
                "控制相机旋转时的旋转速度 (范围: 0.1-10)",
                self.rotation_value_edit,
                self._setting_row_hover_bg,
            )
        )

        self.fps_combo = QtWidgets.QComboBox()
        self.fps_combo.setObjectName("OrcaSettingsFpsCombo")
        for fps in _filtered_fps_options():
            label = f"{_AUTO_FPS_LABEL} ({Viewport._detect_screen_refresh_rate()} FPS)" if fps == 0 else f"{fps} FPS"
            self.fps_combo.addItem(label, fps)
        current_fps = config.lock_fps_value()
        idx = self.fps_combo.findData(current_fps)
        if idx >= 0:
            self.fps_combo.setCurrentIndex(idx)
        else:
            default_idx = self.fps_combo.findData(0)
            if default_idx >= 0:
                self.fps_combo.setCurrentIndex(default_idx)
        root_layout.addWidget(
            _vscode_style_setting_row(
                "帧率限制",
                "限制视口渲染帧率以降低 GPU 负载",
                self.fps_combo,
                self._setting_row_hover_bg,
            )
        )

        self.vsync_checkbox = CheckBox()
        self.vsync_checkbox.set_checked(config.vsync_enabled())
        root_layout.addWidget(
            _vscode_style_setting_row(
                "垂直同步 (VSync)",
                "开启 VSync 可防止画面撕裂，并在混合 GPU 笔记本上避免卡死；关闭可提高帧率，但可能在部分机型上导致卡死，需重启生效",
                self.vsync_checkbox,
                self._setting_row_hover_bg,
            )
        )

        # —— 统计数据：紧挨相机区块下方，间隔由 root_layout.spacing() 控制 ——
        stats_desc = TextLabel("发送用户环境统计数据可以帮助改进OrcaLab。")
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
        #         "发送用户环境统计数据可以帮助改进OrcaLab。",
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
            QComboBox#OrcaSettingsFpsCombo {{
                border: 1px solid {split_line_color};
                border-radius: 3px;
                padding: 3px 6px;
                background-color: {button_bg};
                color: {text_color};
                font-size: 12px;
                min-width: 96px;
            }}
            QComboBox#OrcaSettingsFpsCombo:hover {{
                border: 1px solid #505050;
            }}
            QComboBox#OrcaSettingsFpsCombo::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox#OrcaSettingsFpsCombo QAbstractItemView {{
                border: 1px solid {split_line_color};
                background-color: {button_bg};
                color: {text_color};
                selection-background-color: {button_bg_hover};
                selection-color: {text_color};
                font-size: 12px;
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

        fps_value = self.fps_combo.currentData()
        config.set_lock_fps(fps_value)

        config.set_vsync(self.vsync_checkbox.checked())

        if self._remote_scene is not None:
            asyncio.create_task(
                self._remote_scene.set_move_rotate_sensitivity(move, rot)
            )

        viewport = self.parent().findChild(Viewport) if self.parent() else None
        if viewport is not None:
            viewport.set_target_fps(fps_value)

        super().accept()
