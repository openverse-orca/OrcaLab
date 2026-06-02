import asyncio
import logging
from typing import Any

from PySide6 import QtCore, QtWidgets

from orcalab.actor import BaseActor
from orcalab.actor_property import (
    ActorProperty,
    ActorPropertyGroup,
    ActorPropertyKey,
    ActorPropertyType,
)
from orcalab.application_util import get_local_scene
from orcalab.path import Path
from orcalab.physical_material import (
    CUSTOM_MATERIAL_NAME,
    PhysicalMaterialManager,
    PhysicalMaterialParams,
    compute_effective_params,
)
from orcalab.scene_edit_bus import SceneEditRequestBus
from orcalab.ui.fonts.font_service import FontService
from orcalab.ui.styled_widget import StyledWidget
from orcalab.ui.theme_service import ThemeService

logger = logging.getLogger(__name__)

MJGEOM_COMPONENT_TYPE_ID = "{39E400EC-2015-416D-8483-3C64041787A5}"

CONTROLLED_PROP_NAMES = {
    "density",
    "friction.x", "friction.y", "friction.z",
    "solref.x", "solref.y",
    "solimp.x", "solimp.y", "solimp.z",
    "condim",
}


def _is_geom_component(group: ActorPropertyGroup) -> bool:
    if group.component_type_id == MJGEOM_COMPONENT_TYPE_ID:
        return True
    return False


class PhysicalMaterialEdit(StyledWidget):

    def __init__(
        self,
        parent: QtWidgets.QWidget,
        actor: BaseActor,
        actor_path: Path,
        group: ActorPropertyGroup,
        label_width: int,
    ):
        super().__init__(parent)

        self._actor = actor
        self._actor_path = actor_path
        self._group = group
        self._label_width = label_width

        self._material_name: str = CUSTOM_MATERIAL_NAME
        self._solidity: float = 1.0
        self._roughness: float = 1.0
        self._hardness: float = 1.0

        self._controlled_props: dict[str, ActorProperty] = {}
        self._controlled_keys: dict[str, ActorPropertyKey] = {}
        self._property_edits: list = []
        self._block_events = False
        self._applying = False

        self._build_controlled_map()
        self._build_ui()
        self._init_from_current_props()

    def set_property_edits(self, property_edits: list):
        self._property_edits = property_edits

    def _build_controlled_map(self):
        for prop in self._group.properties:
            name = prop.name()
            if name in CONTROLLED_PROP_NAMES:
                self._controlled_props[name] = prop
                self._controlled_keys[name] = ActorPropertyKey(
                    self._actor_path,
                    self._group.prefix,
                    name,
                    prop.value_type(),
                    entity_id=self._group.entity_id,
                    component_type=self._group.component_type_id,
                )

    def _build_ui(self):
        theme = ThemeService()
        fs = FontService()

        bg_color = theme.get_color_hex("property_group_bg")
        border_color = theme.get_color_hex("split_line")
        label_color = theme.get_color_hex("text")
        value_color = theme.get_color_hex("text")
        brand_color = theme.get_color_hex("brand")
        slider_bg = theme.get_color_hex("property_edit_bg")
        slider_track = theme.get_color_hex("border")

        self.setStyleSheet(f"""
            PhysicalMaterialEdit {{
                background-color: {bg_color};
                border-radius: 4px;
                border: 1px solid {border_color};
                padding: 4px;
            }}
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        manager = PhysicalMaterialManager.instance()
        material_names = [CUSTOM_MATERIAL_NAME] + manager.material_names()

        combo_row = QtWidgets.QWidget()
        combo_layout = QtWidgets.QHBoxLayout(combo_row)
        combo_layout.setContentsMargins(0, 0, 0, 0)
        combo_layout.setSpacing(4)

        combo_label = QtWidgets.QLabel("物理材质")
        combo_label.setMinimumWidth(self._label_width)
        combo_label.setMaximumWidth(self._label_width * 2)
        combo_label.setStyleSheet(f"color: {label_color};")
        fs.bind_widget_font(combo_label, "property_edit")
        combo_layout.addWidget(combo_label)

        self._combo = QtWidgets.QComboBox()
        self._combo.addItems(material_names)
        self._combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {slider_bg};
                border-radius: 2px;
                border: 1px solid {border_color};
                padding: 2px 8px;
                color: {value_color};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {bg_color};
                color: {value_color};
                selection-background-color: {brand_color};
            }}
        """)
        fs.bind_widget_font(self._combo, "property_edit")
        self._combo.currentTextChanged.connect(self._on_material_changed)
        combo_layout.addWidget(self._combo, 1)
        layout.addWidget(combo_row)

        self._solidity_slider = self._create_slider_row(
            layout, "实心比例", 0.0, 1.0, 0.01, self._solidity,
            slider_bg, border_color, label_color, value_color, brand_color,
        )
        self._roughness_slider = self._create_slider_row(
            layout, "表面粗糙度", 0.0, 2.0, 0.01, self._roughness,
            slider_bg, border_color, label_color, value_color, brand_color,
        )
        self._hardness_slider = self._create_slider_row(
            layout, "硬度系数", 0.0, 2.0, 0.01, self._hardness,
            slider_bg, border_color, label_color, value_color, brand_color,
        )

        self._solidity_slider.valueChanged.connect(self._on_solidity_changed)
        self._roughness_slider.valueChanged.connect(self._on_roughness_changed)
        self._hardness_slider.valueChanged.connect(self._on_hardness_changed)

    def _create_slider_row(
        self,
        parent_layout: QtWidgets.QVBoxLayout,
        label_text: str,
        min_val: float,
        max_val: float,
        step: float,
        default: float,
        slider_bg: str,
        border_color: str,
        label_color: str,
        value_color: str,
        brand_color: str,
    ) -> QtWidgets.QSlider:
        fs = FontService()

        row = QtWidgets.QWidget()
        row_layout = QtWidgets.QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)

        label = QtWidgets.QLabel(label_text)
        label.setMinimumWidth(self._label_width)
        label.setMaximumWidth(self._label_width * 2)
        label.setStyleSheet(f"color: {label_color};")
        fs.bind_widget_font(label, "property_edit")
        row_layout.addWidget(label)

        scale = int(1.0 / step)
        slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        slider.setMinimum(int(min_val * scale))
        slider.setMaximum(int(max_val * scale))
        slider.setValue(int(default * scale))
        slider.setProperty("scale", scale)
        slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {border_color};
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {brand_color};
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }}
            QSlider::sub-page:horizontal {{
                background: {brand_color};
                border-radius: 2px;
            }}
        """)
        row_layout.addWidget(slider, 1)

        value_label = QtWidgets.QLabel(f"{default:.2f}")
        value_label.setMinimumWidth(36)
        value_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        value_label.setStyleSheet(f"color: {value_color};")
        fs.bind_widget_font(value_label, "property_edit")
        row_layout.addWidget(value_label)

        slider._value_label = value_label
        slider._scale = scale

        parent_layout.addWidget(row)
        return slider

    def _slider_value(self, slider: QtWidgets.QSlider) -> float:
        return slider.value() / slider._scale

    def _set_slider_value(self, slider: QtWidgets.QSlider, val: float):
        slider.blockSignals(True)
        slider.setValue(int(val * slider._scale))
        slider._value_label.setText(f"{val:.2f}")
        slider.blockSignals(False)

    def _get_prop_value(self, name: str) -> Any:
        prop = self._controlled_props.get(name)
        if prop is not None:
            return prop.value()
        return None

    def _init_from_current_props(self):
        self._material_name = CUSTOM_MATERIAL_NAME

        self._block_events = True
        idx = self._combo.findText(CUSTOM_MATERIAL_NAME)
        if idx >= 0:
            self._combo.setCurrentIndex(idx)

        self._set_slider_value(self._solidity_slider, self._solidity)
        self._set_slider_value(self._roughness_slider, self._roughness)
        self._set_slider_value(self._hardness_slider, self._hardness)
        self._block_events = False

    def _on_material_changed(self, text: str):
        if self._block_events:
            return
        self._material_name = text
        if text != CUSTOM_MATERIAL_NAME:
            self._solidity = 1.0
            self._roughness = 1.0
            self._hardness = 1.0
            self._set_slider_value(self._solidity_slider, 1.0)
            self._set_slider_value(self._roughness_slider, 1.0)
            self._set_slider_value(self._hardness_slider, 1.0)
            self._apply_params()
        else:
            self._solidity = 1.0
            self._roughness = 1.0
            self._hardness = 1.0
            self._set_slider_value(self._solidity_slider, 1.0)
            self._set_slider_value(self._roughness_slider, 1.0)
            self._set_slider_value(self._hardness_slider, 1.0)

    def _on_solidity_changed(self, slider_val: int):
        if self._block_events:
            return
        value = slider_val / self._solidity_slider._scale
        self._solidity_slider._value_label.setText(f"{value:.2f}")
        self._solidity = value
        if self._material_name != CUSTOM_MATERIAL_NAME:
            self._apply_params()

    def _on_roughness_changed(self, slider_val: int):
        if self._block_events:
            return
        value = slider_val / self._roughness_slider._scale
        self._roughness_slider._value_label.setText(f"{value:.2f}")
        self._roughness = value
        if self._material_name != CUSTOM_MATERIAL_NAME:
            self._apply_params()

    def _on_hardness_changed(self, slider_val: int):
        if self._block_events:
            return
        value = slider_val / self._hardness_slider._scale
        self._hardness_slider._value_label.setText(f"{value:.2f}")
        self._hardness = value
        if self._material_name != CUSTOM_MATERIAL_NAME:
            self._apply_params()

    async def _apply_params_async(self):
        params = compute_effective_params(
            self._material_name, self._solidity, self._roughness, self._hardness
        )
        if not params:
            return

        keys = []
        values = []
        for prop_name, value in params.items():
            prop = self._controlled_props.get(prop_name)
            key = self._controlled_keys.get(prop_name)
            if prop is not None and key is not None:
                prop.set_value(value)
                keys.append(key)
                values.append(value)
                self._update_property_edit_ui(prop_name, value)

        if not keys:
            return

        try:
            await SceneEditRequestBus().set_properties(
                keys, values, undo=True, source="ui"
            )
        except Exception as e:
            logger.warning("Failed to batch set properties: %s", e)

    def _update_property_edit_ui(self, prop_name: str, value):
        for edit in self._property_edits:
            if edit.context.prop.name() == prop_name:
                edit.set_value(value)

    def _apply_params(self):
        if self._applying:
            return
        self._applying = True
        try:
            asyncio.create_task(self._apply_params_async())
        finally:
            self._applying = False

    def on_controlled_property_changed(self, property_name: str, value: Any):
        if self._applying:
            return

        base_name = property_name.split(".")[0] if "." in property_name else property_name
        if base_name not in {"density", "friction", "solimp", "solref", "condim"}:
            return

        if self._material_name != CUSTOM_MATERIAL_NAME:
            self._material_name = CUSTOM_MATERIAL_NAME
            self._block_events = True
            idx = self._combo.findText(CUSTOM_MATERIAL_NAME)
            if idx >= 0:
                self._combo.setCurrentIndex(idx)
            self._block_events = False
