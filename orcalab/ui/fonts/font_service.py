import math
import os
import tomllib
import logging
from typing import Dict, Callable

from PySide6 import QtCore, QtGui, QtWidgets

from orcalab.config_service import ConfigService

logger = logging.getLogger(__name__)

_FONT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "font_config.toml")

_DEFAULT_SCALE_PERCENT = 100
_SCALE_STEP = 10
_SCALE_MIN = 50
_SCALE_MAX = 200


class _FontSignals(QtCore.QObject):
    scale_changed = QtCore.Signal()


class FontConfig:
    __slots__ = ("family", "size", "bold", "italic", "weight", "unit", "base")

    def __init__(
        self,
        family: str = "",
        size: int = 12,
        bold: bool = False,
        italic: bool = False,
        weight: int = 0,
        unit: str = "pt",
        base: str = "",
    ):
        self.family = family
        self.size = size
        self.bold = bold
        self.italic = italic
        self.weight = weight
        self.unit = unit
        self.base = base


class FontService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self._configs: Dict[str, FontConfig] = {}
        self._raw: Dict[str, dict] = {}
        self._scale_percent: int = _DEFAULT_SCALE_PERCENT
        self._signals = _FontSignals()
        self._callbacks: Dict[int, Callable[[], None]] = {}
        self._next_cb_id: int = 0
        self._load_config()
        self._load_scale_factor()

    def _load_config(self):
        if not os.path.exists(_FONT_CONFIG_PATH):
            logger.warning("Font config not found: %s", _FONT_CONFIG_PATH)
            self._set_defaults()
            return

        with open(_FONT_CONFIG_PATH, "rb") as f:
            data = tomllib.load(f)

        fonts = data.get("fonts", {})
        for key, value in fonts.items():
            if not isinstance(value, dict):
                continue
            self._raw[key] = value
            self._configs[key] = FontConfig(
                family=value.get("family", ""),
                size=value.get("size", 11),
                bold=value.get("bold", False),
                italic=value.get("italic", False),
                weight=value.get("weight", 0),
                unit=value.get("unit", "pt"),
                base=value.get("base", ""),
            )

        self._resolve_inheritance()

    def _resolve_inheritance(self):
        resolved = set()

        def resolve(key: str, chain: set | None = None):
            if key in resolved:
                return
            if chain is None:
                chain = set()
            if key in chain:
                logger.error("Circular font inheritance: %s", key)
                return
            chain.add(key)

            cfg = self._configs.get(key)
            if cfg is None or not cfg.base:
                resolved.add(key)
                return

            parent_key = cfg.base
            if parent_key not in self._configs:
                logger.warning("Font '%s' base '%s' not found", key, parent_key)
                resolved.add(key)
                return

            resolve(parent_key, chain)
            parent = self._configs[parent_key]

            raw = self._raw.get(key, {})
            if "family" not in raw:
                cfg.family = parent.family
            if "size" not in raw:
                cfg.size = parent.size
            if "bold" not in raw:
                cfg.bold = parent.bold
            if "italic" not in raw:
                cfg.italic = parent.italic
            if "weight" not in raw:
                cfg.weight = parent.weight
            if "unit" not in raw:
                cfg.unit = parent.unit

            resolved.add(key)

        for key in list(self._configs.keys()):
            resolve(key)

    def _set_defaults(self):
        self._configs["body"] = FontConfig(size=11)
        self._configs["small"] = FontConfig(size=10)
        self._configs["tiny"] = FontConfig(size=9)
        self._configs["title"] = FontConfig(size=14, bold=True)
        self._configs["subtitle"] = FontConfig(size=12, bold=True)
        self._configs["button"] = FontConfig(size=11)

    def _load_scale_factor(self):
        try:
            config = ConfigService()
            self._scale_percent = config.font_scale_percent()
        except Exception:
            self._scale_percent = _DEFAULT_SCALE_PERCENT

    def _save_scale_factor(self):
        try:
            config = ConfigService()
            config.set_font_scale_percent(self._scale_percent)
        except Exception as e:
            logger.error("Failed to save font scale: %s", e)

    @property
    def scale_changed(self):
        return self._signals.scale_changed

    def get_config(self, key: str) -> FontConfig:
        if key in self._configs:
            return self._configs[key]
        logger.warning("Font key '%s' not found, using default", key)
        return FontConfig()

    def _scaled_size(self, base_size: int) -> int:
        return math.floor(base_size * self._scale_percent / 100)

    def _size_to_px(self, cfg: FontConfig) -> int:
        scaled = self._scaled_size(cfg.size)
        if cfg.unit == "pt":
            screen = QtGui.QGuiApplication.primaryScreen()
            dpi = screen.logicalDotsPerInch() if screen else 96.0
            return max(1, math.floor(scaled * dpi / 72.0))
        return scaled

    def indent_unit_px(self, base: int = 20) -> int:
        """计算缩进单位（像素），基于字体缩放系数和屏幕 DPI。"""
        scaled = self._scaled_size(base)
        screen = QtGui.QGuiApplication.primaryScreen()
        dpi = screen.logicalDotsPerInch() if screen else 96.0
        return max(1, math.floor(scaled * dpi / 96.0))

    def get_font(self, key: str) -> QtGui.QFont:
        cfg = self.get_config(key)
        font = QtGui.QFont()
        if cfg.family:
            families = [f.strip() for f in cfg.family.split(",")]
            font.setFamilies(families)
        scaled = self._scaled_size(cfg.size)
        if cfg.unit == "pt":
            font.setPointSize(max(1, scaled))
        else:
            font.setPixelSize(max(1, scaled))
        if cfg.weight > 0:
            font.setWeight(QtGui.QFont.Weight(cfg.weight))
        else:
            font.setBold(cfg.bold)
        font.setItalic(cfg.italic)
        return font

    def apply_font_modifiers(self, key: str, font: QtGui.QFont) -> QtGui.QFont:
        raw = self._raw.get(key, {})
        if "family" in raw:
            families = [f.strip() for f in raw["family"].split(",")]
            font.setFamilies(families)
        if "size" in raw:
            cfg = self.get_config(key)
            scaled = self._scaled_size(cfg.size)
            if cfg.unit == "pt":
                font.setPointSize(max(1, scaled))
            else:
                font.setPixelSize(max(1, scaled))
        if "weight" in raw:
            font.setWeight(raw["weight"])
        elif "bold" in raw:
            font.setBold(raw["bold"])
        if "italic" in raw:
            font.setItalic(raw["italic"])
        return font

    def get_font_size_px(self, key: str) -> str:
        cfg = self.get_config(key)
        scaled = self._scaled_size(cfg.size)
        if cfg.unit == "pt":
            return f"{scaled}pt"
        return f"{scaled}px"

    def get_font_size(self, key: str) -> int:
        cfg = self.get_config(key)
        return self._size_to_px(cfg)

    def get_font_css(self, key: str) -> str:
        cfg = self.get_config(key)
        parts = []
        scaled = self._scaled_size(cfg.size)
        if cfg.unit == "pt":
            parts.append(f"font-size: {scaled}pt")
        else:
            parts.append(f"font-size: {scaled}px")
        if cfg.weight > 0:
            parts.append(f"font-weight: {cfg.weight}")
        elif cfg.bold:
            parts.append("font-weight: bold")
        if cfg.italic:
            parts.append("font-style: italic")
        if cfg.family:
            parts.append(f"font-family: {cfg.family}")
        return "; ".join(parts) + ";"

    def get_scale_percent(self) -> int:
        return self._scale_percent

    def set_scale_percent(self, percent: int):
        percent = round(percent / _SCALE_STEP) * _SCALE_STEP
        percent = max(_SCALE_MIN, min(_SCALE_MAX, percent))
        if percent == self._scale_percent:
            return
        self._scale_percent = percent
        self._save_scale_factor()
        self._signals.scale_changed.emit()
        self._fire_callbacks()

    def increase_scale(self):
        self.set_scale_percent(self._scale_percent + _SCALE_STEP)

    def decrease_scale(self):
        self.set_scale_percent(self._scale_percent - _SCALE_STEP)

    def reset_scale(self):
        self.set_scale_percent(_DEFAULT_SCALE_PERCENT)

    def on_scale_changed(self, callback: Callable[[], None]) -> int:
        cb_id = self._next_cb_id
        self._next_cb_id += 1
        self._callbacks[cb_id] = callback
        return cb_id

    def remove_on_scale_changed(self, cb_id: int) -> None:
        self._callbacks.pop(cb_id, None)

    def bind_widget_font(
        self,
        widget: QtWidgets.QWidget,
        key: str,
        *,
        use_css: bool = False,
        extra_css: str = "",
    ) -> int:
        if use_css:
            def refresh():
                css = self.get_font_css(key)
                if extra_css:
                    widget.setStyleSheet(f"{css} {extra_css}")
                else:
                    widget.setStyleSheet(css)
            refresh()
        else:
            def refresh():
                widget.setFont(self.get_font(key))
            refresh()

        cb_id = self.on_scale_changed(refresh)

        def on_destroyed(_obj=None):
            self.remove_on_scale_changed(cb_id)

        widget.destroyed.connect(on_destroyed)
        return cb_id

    def bind_widget_stylesheet(
        self,
        widget: QtWidgets.QWidget,
        build_css: Callable[[], str],
    ) -> int:
        def refresh():
            widget.setStyleSheet(build_css())
        refresh()

        cb_id = self.on_scale_changed(refresh)

        def on_destroyed(_obj=None):
            self.remove_on_scale_changed(cb_id)

        widget.destroyed.connect(on_destroyed)
        return cb_id

    def _fire_callbacks(self):
        for cb_id in list(self._callbacks.keys()):
            cb = self._callbacks.get(cb_id)
            if cb is not None:
                try:
                    cb()
                except Exception as e:
                    logger.error("Font scale callback error: %s", e)
