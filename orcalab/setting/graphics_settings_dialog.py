"""图形设置对话框。

允许用户调整渲染质量相关 CVAR，保存后写入用户级 game.cfg（@user@/game.cfg），
引擎下次启动时加载。所有设置均需重启生效（避免运行时管线重建卡顿）。

质量预设（低/中/高/超高）会自动联动调整抗锯齿、阴影、纹理、后处理等关联设置。
用户单独修改任一关联设置时，质量预设自动切换为"自定义"。
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from orcalab.config_service import ConfigService
from orcalab.i18n import tr
from orcalab.project_util import read_user_game_cfg, write_user_game_cfg
from orcalab.ui.fonts.font_service import FontService
from orcalab.ui.text_label import TextLabel
from orcalab.ui.theme_service import ThemeService
from orcalab.ui.checkbox import CheckBox
from orcalab.ui.viewport import Viewport

_SETTING_BLOCK_H_MARGIN = 12

# 质量预设的自定义标记值
_QUALITY_CUSTOM = -1


# ============================================================
# 质量预设定义：每个等级对应一组关联 CVAR 值
# ============================================================
# 格式: { preset_level: { cvar_name: value, ... } }
# None 表示该等级不设置该 CVAR（使用引擎默认）
_QUALITY_PRESETS = {
    0: {  # 低
        "r_antiAliasing": "",
        "r_multiSampleCount": 1,
        "r_directionalShadowFilteringMethod": 1,  # Pcf
        "r_directionalShadowFilteringSampleCountMode": 0,  # 4 taps
        "r_streamingImageMipBias": 2,  # 低纹理
        "r_enableBloom": 0,
        "r_enableDOF": 0,
        "r_enableFog": 1,
        "r_useEntryWorkListsForCulling": 1,
        "r_numEntriesPerCullingJob": 750,
    },
    1: {  # 中
        "r_antiAliasing": "SMAA",
        "r_multiSampleCount": 1,
        "r_directionalShadowFilteringMethod": 1,  # Pcf
        "r_directionalShadowFilteringSampleCountMode": 1,  # 9 taps
        "r_streamingImageMipBias": 1,  # 中纹理
        "r_enableBloom": 1,
        "r_enableDOF": 0,
        "r_enableFog": 1,
        "r_useEntryWorkListsForCulling": 1,
        "r_numEntriesPerCullingJob": 1500,
    },
    2: {  # 高
        "r_antiAliasing": "SMAA",
        "r_multiSampleCount": 2,
        "r_directionalShadowFilteringMethod": 3,  # EsmPcf
        "r_directionalShadowFilteringSampleCountMode": 1,  # 9 taps
        "r_streamingImageMipBias": 0,  # 高纹理
        "r_enableBloom": 1,
        "r_enableDOF": 1,
        "r_enableFog": 1,
        "r_useEntryWorkListsForCulling": 1,
        "r_numEntriesPerCullingJob": 1500,
    },
    3: {  # 超高
        "r_antiAliasing": "TAA",
        "r_multiSampleCount": 4,
        "r_directionalShadowFilteringMethod": 3,  # EsmPcf
        "r_directionalShadowFilteringSampleCountMode": 2,  # 16 taps
        "r_streamingImageMipBias": 0,  # 高纹理
        "r_enableBloom": 1,
        "r_enableDOF": 1,
        "r_enableFog": 1,
        "r_useEntryWorkListsForCulling": 1,
        "r_numEntriesPerCullingJob": 1500,
    },
}


# ============================================================
# CVAR 选项构造器：在运行时调用（语言已设置），返回 [(value, label), ...]
# ============================================================

def _quality_levels():
    return [
        (0, tr("低")),
        (1, tr("中")),
        (2, tr("高")),
        (3, tr("超高")),
        (_QUALITY_CUSTOM, tr("自定义")),
    ]


def _aa_modes():
    return [
        ("", tr("关闭")),
        ("SMAA", "SMAA"),
        ("TAA", "TAA"),
        ("MSAA", "MSAA"),
    ]


def _msaa_samples():
    return [
        (1, "1×"),
        (2, "2×"),
        (4, "4×"),
        (8, "8×"),
    ]


def _shadow_methods():
    return [
        (-1, tr("默认")),
        (0, tr("无")),
        (1, "Pcf"),
        (2, "Esm"),
        (3, "EsmPcf"),
    ]


def _shadow_sample_modes():
    return [
        (-1, tr("默认")),
        (0, "4 taps"),
        (1, "9 taps"),
        (2, "16 taps"),
    ]


def _texture_quality():
    return [
        (0, tr("高")),
        (1, tr("中")),
        (2, tr("低")),
    ]


def _culling_job_counts():
    return [
        (500, "500"),
        (750, "750"),
        (1500, "1500"),
        (3000, "3000"),
    ]


# FPS 选项（0 = 自动，跟随屏幕刷新率）
_FPS_OPTIONS = [0, 30, 60, 90, 120, 144, 160, 240]
_AUTO_FPS_LABEL = "自动"


def _filtered_fps_options() -> list:
    max_screen_fps = Viewport.detect_max_screen_refresh_rate()
    result = [0]
    for fps in _FPS_OPTIONS:
        if fps > 0 and fps <= max_screen_fps:
            result.append(fps)
    if len(result) == 1:
        result.append(max_screen_fps)
    return result


def _cvar_to_int(value, default: int) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _cvar_to_str(value, default: str) -> str:
    return value if value else default


def _make_combo(options: list, current_value, object_name: str) -> QtWidgets.QComboBox:
    """构建下拉框。options 为 [(value, label), ...]。"""
    combo = QtWidgets.QComboBox()
    combo.setObjectName(object_name)
    for value, label in options:
        combo.addItem(label, value)
    idx = combo.findData(current_value)
    if idx >= 0:
        combo.setCurrentIndex(idx)
    else:
        combo.setCurrentIndex(0)
    return combo


def _setting_row(
    title: str,
    description: str,
    control: QtWidgets.QWidget,
    hover_background: str,
) -> QtWidgets.QWidget:
    """VSCode 风格的设置行：标题 + 说明 + 控件。"""
    block = _SettingHoverBlock(hover_background)
    layout = QtWidgets.QVBoxLayout(block)
    layout.setContentsMargins(_SETTING_BLOCK_H_MARGIN, 5, _SETTING_BLOCK_H_MARGIN, 5)
    layout.setSpacing(4)

    fs = FontService()
    title_label = TextLabel(title)
    fs.bind_widget_stylesheet(title_label, lambda: fs.get_font_css("setting_title"))

    desc_label = TextLabel(description)
    fs.bind_widget_stylesheet(
        desc_label, lambda: f"color: #888888; {fs.get_font_css('body')}"
    )

    control_row = QtWidgets.QHBoxLayout()
    control_row.setContentsMargins(0, 8, 0, 0)
    control_row.setSpacing(0)
    control_row.addWidget(control, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
    control_row.addStretch()

    layout.addWidget(title_label)
    layout.addWidget(desc_label)
    layout.addLayout(control_row)
    return block


class _SettingHoverBlock(QtWidgets.QWidget):
    """带 hover 高亮效果的设置行容器。"""

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


class GraphicsSettingsDialog(QtWidgets.QDialog):
    """图形设置对话框。

    设置项通过用户级 game.cfg 持久化，重启后引擎加载生效。
    所有 CVAR 变更均需重启应用才能稳定生效（避免运行时渲染管线重建）。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("图形设置"))
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)

        theme = ThemeService()
        self._setting_row_hover_bg = theme.get_color_hex("bg_hover")
        self._apply_theme()

        # 标记：是否正在程序化设置控件值（避免触发联动回调）
        self._suppress_cascade = False

        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setSpacing(0)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QtWidgets.QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll_content = QtWidgets.QWidget()
        scroll_content.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        content_layout = QtWidgets.QVBoxLayout(scroll_content)
        content_layout.setSpacing(20)
        content_layout.setContentsMargins(24, 24, 24, 20)

        # 读取已持久化的用户级 game.cfg
        cfg = read_user_game_cfg()

        # —— 质量预设 ——
        # 检测当前配置是否匹配某个预设，否则为自定义
        current_quality = self._detect_quality_preset(cfg)
        self.quality_combo = _make_combo(
            _quality_levels(),
            current_quality,
            "OrcaGraphicsQualityCombo",
        )
        self.quality_combo.currentIndexChanged.connect(self._on_quality_preset_changed)
        content_layout.addWidget(
            _setting_row(
                tr("质量预设"),
                tr("全局图形质量等级，自动调整下方关联设置。单独修改任一设置将切换为自定义"),
                self.quality_combo,
                self._setting_row_hover_bg,
            )
        )

        # —— 抗锯齿模式 ——
        self.aa_combo = _make_combo(
            _aa_modes(),
            _cvar_to_str(cfg.get("r_antiAliasing", ""), ""),
            "OrcaGraphicsAaCombo",
        )
        self.aa_combo.currentIndexChanged.connect(self._on_individual_setting_changed)
        content_layout.addWidget(
            _setting_row(
                tr("抗锯齿模式"),
                tr("MSAA 为多重采样，TAA 为时域抗锯齿，SMAA 为子像素形态学抗锯齿"),
                self.aa_combo,
                self._setting_row_hover_bg,
            )
        )

        # —— MSAA 采样数 ——
        self.msaa_combo = _make_combo(
            _msaa_samples(),
            _cvar_to_int(cfg.get("r_multiSampleCount", ""), 1),
            "OrcaGraphicsMsaaCombo",
        )
        self.msaa_combo.currentIndexChanged.connect(self._on_individual_setting_changed)
        content_layout.addWidget(
            _setting_row(
                tr("MSAA 采样数"),
                tr("仅在抗锯齿模式为 MSAA 时生效。采样数越高画质越好但性能越低"),
                self.msaa_combo,
                self._setting_row_hover_bg,
            )
        )

        # —— 阴影过滤方法 ——
        self.shadow_method_combo = _make_combo(
            _shadow_methods(),
            _cvar_to_int(cfg.get("r_directionalShadowFilteringMethod", ""), -1),
            "OrcaGraphicsShadowMethodCombo",
        )
        self.shadow_method_combo.currentIndexChanged.connect(
            self._on_individual_setting_changed
        )
        content_layout.addWidget(
            _setting_row(
                tr("阴影过滤方法"),
                tr("方向光阴影的过滤算法。EsmPcf 质量最高，Pcf 次之"),
                self.shadow_method_combo,
                self._setting_row_hover_bg,
            )
        )

        # —— 阴影采样数 ——
        self.shadow_sample_combo = _make_combo(
            _shadow_sample_modes(),
            _cvar_to_int(cfg.get("r_directionalShadowFilteringSampleCountMode", ""), -1),
            "OrcaGraphicsShadowSampleCombo",
        )
        self.shadow_sample_combo.currentIndexChanged.connect(
            self._on_individual_setting_changed
        )
        content_layout.addWidget(
            _setting_row(
                tr("阴影采样数"),
                tr("阴影采样点数量。采样越多阴影越柔和但性能越低"),
                self.shadow_sample_combo,
                self._setting_row_hover_bg,
            )
        )

        # —— 纹理质量 ——
        self.texture_combo = _make_combo(
            _texture_quality(),
            _cvar_to_int(cfg.get("r_streamingImageMipBias", ""), 0),
            "OrcaGraphicsTextureCombo",
        )
        self.texture_combo.currentIndexChanged.connect(
            self._on_individual_setting_changed
        )
        content_layout.addWidget(
            _setting_row(
                tr("纹理质量"),
                tr("控制纹理流式加载的 mip 偏移。高质量加载完整纹理，低质量节省显存"),
                self.texture_combo,
                self._setting_row_hover_bg,
            )
        )

        # —— Culling 性能调优：每 Job 条目数 ——
        self.culling_combo = _make_combo(
            _culling_job_counts(),
            _cvar_to_int(cfg.get("r_numEntriesPerCullingJob", ""), 1500),
            "OrcaGraphicsCullingCombo",
        )
        self.culling_combo.currentIndexChanged.connect(
            self._on_individual_setting_changed
        )
        content_layout.addWidget(
            _setting_row(
                tr("Culling 任务粒度"),
                tr("每 Job 处理的 Culling 条目数。值越大派发次数越少，负载越集中"),
                self.culling_combo,
                self._setting_row_hover_bg,
            )
        )

        # —— Bloom 开关 ——
        self.bloom_checkbox = CheckBox()
        bloom_val = cfg.get("r_enableBloom", "")
        self.bloom_checkbox.set_checked(bloom_val != "0")
        self.bloom_checkbox.value_changed.connect(self._on_individual_setting_changed)
        content_layout.addWidget(
            _setting_row(
                tr("Bloom (泛光)"),
                tr("高亮区域的辉光效果"),
                self.bloom_checkbox,
                self._setting_row_hover_bg,
            )
        )

        # —— 景深开关 ——
        self.dof_checkbox = CheckBox()
        dof_val = cfg.get("r_enableDOF", "")
        self.dof_checkbox.set_checked(dof_val != "0")
        self.dof_checkbox.value_changed.connect(self._on_individual_setting_changed)
        content_layout.addWidget(
            _setting_row(
                tr("景深 (DOF)"),
                tr("模拟相机镜头的景深模糊效果"),
                self.dof_checkbox,
                self._setting_row_hover_bg,
            )
        )

        # —— 雾效开关 ——
        self.fog_checkbox = CheckBox()
        fog_val = cfg.get("r_enableFog", "")
        self.fog_checkbox.set_checked(fog_val != "0")
        self.fog_checkbox.value_changed.connect(self._on_individual_setting_changed)
        content_layout.addWidget(
            _setting_row(
                tr("雾效"),
                tr("场景中的体积雾与距离雾"),
                self.fog_checkbox,
                self._setting_row_hover_bg,
            )
        )

        # —— 垂直同步 ——
        self.vsync_checkbox = CheckBox()
        # vsync_interval: 0=关闭, 1=开启（引擎默认）
        vsync_val = cfg.get("vsync_interval", "")
        if vsync_val == "":
            # 未设置时使用 ConfigService 的值（viewport 命令行依赖）
            self.vsync_checkbox.set_checked(ConfigService().vsync_enabled())
        else:
            self.vsync_checkbox.set_checked(vsync_val != "0")
        content_layout.addWidget(
            _setting_row(
                tr("垂直同步 (VSync)"),
                tr("开启可防止画面撕裂，关闭可提高帧率。需重启生效"),
                self.vsync_checkbox,
                self._setting_row_hover_bg,
            )
        )

        # —— 帧率限制 ——
        self.fps_combo = QtWidgets.QComboBox()
        self.fps_combo.setObjectName("OrcaGraphicsFpsCombo")
        screen_fps = Viewport.detect_screen_refresh_rate()
        for fps in _filtered_fps_options():
            label = (
                f"{tr(_AUTO_FPS_LABEL)} ({screen_fps} FPS)"
                if fps == 0
                else f"{fps} FPS"
            )
            self.fps_combo.addItem(label, fps)
        current_fps = ConfigService().lock_fps_value()
        idx = self.fps_combo.findData(current_fps)
        if idx >= 0:
            self.fps_combo.setCurrentIndex(idx)
        else:
            default_idx = self.fps_combo.findData(0)
            if default_idx >= 0:
                self.fps_combo.setCurrentIndex(default_idx)
        content_layout.addWidget(
            _setting_row(
                tr("帧率限制"),
                tr("限制视口渲染帧率以降低 GPU 负载。0 为自动跟随屏幕刷新率"),
                self.fps_combo,
                self._setting_row_hover_bg,
            )
        )

        scroll_area.setWidget(scroll_content)
        root_layout.addWidget(scroll_area)

        # —— 底部按钮 ——
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setContentsMargins(
            _SETTING_BLOCK_H_MARGIN, 8, _SETTING_BLOCK_H_MARGIN, 8
        )
        button_layout.addStretch()

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        cancel_btn = buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        if ok_btn is not None:
            ok_btn.setText(tr("保存"))
        if cancel_btn is not None:
            cancel_btn.setText(tr("取消"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        button_layout.addWidget(buttons)

        root_layout.addLayout(button_layout)

        self.setMinimumSize(480, 400)
        self.resize(560, 720)

    # ============================================================
    # 预设联动逻辑
    # ============================================================

    def _detect_quality_preset(self, cfg: dict) -> int:
        """检测当前 CVAR 配置是否匹配某个预设，返回预设等级或 _QUALITY_CUSTOM。"""
        for level, preset in _QUALITY_PRESETS.items():
            if self._config_matches_preset(cfg, preset):
                return level
        return _QUALITY_CUSTOM

    def _config_matches_preset(self, cfg: dict, preset: dict) -> bool:
        """检查当前配置是否与给定预设完全匹配。

        预设值统一为 int/str，read_user_game_cfg 读回的是 str，
        所以统一转为 str 比较。
        """
        for cvar, expected in preset.items():
            actual = cfg.get(cvar, "")
            # 统一转为 str 比较（预设 int 1 → "1"，读回 str "1"）
            expected_str = expected if isinstance(expected, str) else str(expected)
            if actual != expected_str:
                return False
        return True

    def _on_quality_preset_changed(self) -> None:
        """用户切换质量预设时，自动设置关联 CVAR 控件。"""
        if self._suppress_cascade:
            return
        level = self.quality_combo.currentData()
        if level == _QUALITY_CUSTOM or level is None:
            return

        preset = _QUALITY_PRESETS.get(level)
        if preset is None:
            return

        self._suppress_cascade = True
        try:
            self._apply_preset_to_controls(preset)
        finally:
            self._suppress_cascade = False

    def _apply_preset_to_controls(self, preset: dict) -> None:
        """将预设值应用到各控件。表驱动，避免重复代码。"""
        # 下拉框控件：(combo, cvar_name, default)
        combo_specs = [
            (self.aa_combo, "r_antiAliasing", ""),
            (self.msaa_combo, "r_multiSampleCount", 1),
            (self.shadow_method_combo, "r_directionalShadowFilteringMethod", -1),
            (self.shadow_sample_combo, "r_directionalShadowFilteringSampleCountMode", -1),
            (self.texture_combo, "r_streamingImageMipBias", 0),
            (self.culling_combo, "r_numEntriesPerCullingJob", 1500),
        ]
        for combo, cvar, default in combo_specs:
            idx = combo.findData(preset.get(cvar, default))
            if idx >= 0:
                combo.setCurrentIndex(idx)

        # 复选框控件：(checkbox, cvar_name, default)
        # 预设中布尔类 CVAR 统一用 int (0/1)，这里转 bool
        checkbox_specs = [
            (self.bloom_checkbox, "r_enableBloom", 1),
            (self.dof_checkbox, "r_enableDOF", 0),
            (self.fog_checkbox, "r_enableFog", 1),
        ]
        for checkbox, cvar, default in checkbox_specs:
            checkbox.set_checked(bool(preset.get(cvar, default)))

    def _on_individual_setting_changed(self) -> None:
        """用户单独修改任一关联设置时，质量预设切换为自定义。"""
        if self._suppress_cascade:
            return
        idx = self.quality_combo.findData(_QUALITY_CUSTOM)
        if idx >= 0 and self.quality_combo.currentIndex() != idx:
            self._suppress_cascade = True
            try:
                self.quality_combo.setCurrentIndex(idx)
            finally:
                self._suppress_cascade = False

    # ============================================================
    # 保存
    # ============================================================

    def accept(self) -> None:
        """保存设置到用户级 game.cfg，并提示重启。"""
        settings = {
            "q_graphics": self.quality_combo.currentData(),
            "r_antiAliasing": self.aa_combo.currentData(),
            "r_multiSampleCount": self.msaa_combo.currentData(),
            "r_directionalShadowFilteringMethod": self.shadow_method_combo.currentData(),
            "r_directionalShadowFilteringSampleCountMode": self.shadow_sample_combo.currentData(),
            "r_streamingImageMipBias": self.texture_combo.currentData(),
            "r_numEntriesPerCullingJob": self.culling_combo.currentData(),
            "r_useEntryWorkListsForCulling": 1,
            "r_enableBloom": 1 if self.bloom_checkbox.checked() else 0,
            "r_enableDOF": 1 if self.dof_checkbox.checked() else 0,
            "r_enableFog": 1 if self.fog_checkbox.checked() else 0,
            "vsync_interval": 1 if self.vsync_checkbox.checked() else 0,
            # sys_MaxFPS: 0 表示自动（无限制），与 ConfigService.lock_fps 保持一致
            "sys_MaxFPS": self.fps_combo.currentData() or 0,
        }
        # 空字符串的抗锯齿模式不写入（使用引擎默认）
        if settings["r_antiAliasing"] == "":
            settings["r_antiAliasing"] = None
        # 自定义预设不写入 q_graphics
        if settings["q_graphics"] == _QUALITY_CUSTOM:
            settings["q_graphics"] = None

        write_user_game_cfg(settings)

        # 同步 VSync 和帧率到 ConfigService（供 viewport 启动时构建命令行读取）
        config = ConfigService()
        config.set_vsync(self.vsync_checkbox.checked())
        # fps 统一变量，避免 game.cfg 与 ConfigService 不一致
        fps = self.fps_combo.currentData() or 0
        config.set_lock_fps(fps)

        # 提示用户重启后生效
        QtWidgets.QMessageBox.information(
            self,
            tr("图形设置"),
            tr("图形设置已保存，需要重启应用才能生效。"),
        )

        super().accept()

    # ============================================================
    # 主题样式
    # ============================================================

    def _apply_theme(self) -> None:
        theme = ThemeService()
        self._theme = theme
        fs = FontService()
        fs.bind_widget_stylesheet(self, self._build_stylesheet)

    def _build_stylesheet(self) -> str:
        theme = self._theme
        fs = FontService()
        bg_color = theme.get_color_hex("bg")
        text_color = theme.get_color_hex("text")
        split_line_color = theme.get_color_hex("split_line")
        button_bg = theme.get_color_hex("button_bg")
        button_bg_hover = theme.get_color_hex("button_bg_hover")

        return f"""
            QDialog {{
                background-color: {bg_color};
                color: {text_color};
            }}
            QScrollArea {{
                background-color: {bg_color};
                border: none;
            }}
            QComboBox {{
                background-color: {button_bg};
                color: {text_color};
                border: 1px solid {split_line_color};
                border-radius: 4px;
                padding: 4px 8px;
                min-width: 120px;
                {fs.get_font_css('body')}
            }}
            QComboBox:hover {{
                border: 1px solid #505050;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                border: 1px solid {split_line_color};
                background-color: {button_bg};
                color: {text_color};
                selection-background-color: {button_bg_hover};
                selection-color: {text_color};
                {fs.get_font_css('body')}
            }}
            QPushButton {{
                background-color: {button_bg};
                color: {text_color};
                border: 1px solid {split_line_color};
                border-radius: 4px;
                padding: 6px 16px;
                {fs.get_font_css('body')}
            }}
            QPushButton:hover {{
                background-color: {button_bg_hover};
            }}
        """
