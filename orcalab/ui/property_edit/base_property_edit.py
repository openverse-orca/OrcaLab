import asyncio
from dataclasses import dataclass
from typing import TypeVar, Generic
from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.actor import BaseActor
from orcalab.actor_property import (
    ActorProperty,
    ActorPropertyGroup,
    ActorPropertyKey,
)
from orcalab.path import Path
from orcalab.scene_edit_bus import SceneEditRequestBus
from orcalab.ui.styled_widget import StyledWidget
from orcalab.ui.theme_service import ThemeService
from orcalab.ui.fonts.font_service import FontService

_T = TypeVar("_T")


@dataclass
class PropertyEditContext:
    actor: BaseActor
    actor_path: Path
    group: ActorPropertyGroup
    prop: ActorProperty
    key: ActorPropertyKey


def get_property_edit_style_sheet() -> str:
    theme = ThemeService()
    property_group_bg_color = theme.get_color_hex("property_group_bg")
    bg_color = theme.get_color_hex("property_edit_bg")
    bg_hover_color = theme.get_color_hex("property_edit_bg_hover")
    bg_focus_color = theme.get_color_hex("property_edit_bg_editing")
    brand_color = theme.get_color_hex("brand")

    base_style = f"""
        QLineEdit[readOnly="false"] {{
            background-color: {bg_color};
            border-radius: 2px;
            border-bottom: 1px solid {bg_color};
            padding: 2px 8px;
        }}
        QLineEdit[readOnly="true"] {{
            background-color: {property_group_bg_color};
            border-radius: 2px;
            border: 1px solid {bg_color};
            padding: 2px 8px;
        }}
        QLineEdit[readOnly="false"]:hover {{
            background-color: {bg_hover_color};
        }}
        QLineEdit[readOnly="false"]:focus {{
            background-color: {bg_focus_color};
            border-bottom: 1px solid {brand_color};
        }}
        BaseNumberEdit[dragging="true"] {{
            background-color: {bg_focus_color};
            border-radius: 2px;
            border-bottom: 1px solid {bg_focus_color};
            padding: 2px 8px;
        }}
        """
    return base_style


class BasePropertyEdit(Generic[_T], StyledWidget):
    def __init__(self, parent: QtWidgets.QWidget | None, context: PropertyEditContext):
        super().__init__(parent)

        self.context = context
        self.base_style = get_property_edit_style_sheet()

    async def _do_set_value_async(self, value: _T, undo: bool):
        await SceneEditRequestBus().set_property(
            self.context.key,
            value=value,
            undo=undo,
            source="ui",
        )

    def _do_set_value(self, value: _T, undo: bool):
        asyncio.create_task(self._do_set_value_async(value, undo))

    def _on_start_drag(self):
        SceneEditRequestBus().start_change_property(self.context.key)
        self.in_dragging = True

    def _on_end_drag(self):
        async def warpper():
            await self._do_set_value_async(self.context.prop.value(), undo=True)
            SceneEditRequestBus().end_change_property(self.context.key)
            self.in_dragging = False

        asyncio.create_task(warpper())

    def set_value(self, value: _T):
        pass

    def _create_label(self, label_width: int, display_text: str | None = None) -> QtWidgets.QLabel:
        if display_text is not None:
            text = display_text
        else:
            text = self.context.prop.display_name()
            if not text:
                text = self.context.prop.name()
        label = QtWidgets.QLabel(text)
        if label_width > 0:
            label.setMinimumWidth(label_width)
            label.setMaximumWidth(label_width * 2)
        else:
            label.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Preferred,
                QtWidgets.QSizePolicy.Policy.Preferred,
            )
        label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        FontService().bind_widget_font(label, "property_edit")
        return label

    def set_value(self, value: _T):
        raise NotImplementedError()

    def set_base_value(self, value: _T):
        self.context.prop.set_base_value(value)
        # TODO: update UI

    def set_read_only(self, read_only: bool):
        """Set UI read only"""
        raise NotImplementedError()
