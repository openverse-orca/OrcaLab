import asyncio
from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.actor import AssetActor
from orcalab.actor_property import (
    ActorProperty,
    ActorPropertyGroup,
    ActorPropertyKey,
)
from orcalab.path import Path
from orcalab.scene_edit_bus import (
    SceneEditRequestBus,
)
from orcalab.ui.styled_widget import StyledWidget
from orcalab.ui.theme_service import ThemeService


class PropertyEditContext:
    def __init__(
        self,
        actor: AssetActor,
        actor_path: Path,
        group: ActorPropertyGroup,
        prop: ActorProperty,
    ):
        self.actor = actor
        self.actor_path = actor_path
        self.group = group
        self.prop = prop

        self.key = ActorPropertyKey(
            self.actor_path,
            self.group.prefix,
            prop.name(),
            prop.value_type(),
        )


def get_property_edit_style_sheet() -> str:
    theme = ThemeService()
    bg_color = theme.get_color_hex("property_edit_bg")
    bg_hover_color = theme.get_color_hex("property_edit_bg_hover")
    bg_focus_color = theme.get_color_hex("property_edit_bg_editing")
    brand_color = theme.get_color_hex("brand")

    base_style = f"""
        QLineEdit {{
            background-color: {bg_color};
            border-radius: 2px;
            border-bottom: 1px solid {bg_color};
            padding: 4px 8px;
        }}
        QLineEdit:hover {{
            background-color: {bg_hover_color};
        }}
        QLineEdit:focus {{
            background-color: {bg_focus_color};
            border-bottom: 1px solid {brand_color};
        }}
        BaseNumberEdit[dragging="true"] {{
            background-color: {bg_focus_color};
            border-radius: 2px;
            border-bottom: 1px solid {bg_focus_color};
            padding: 4px 8px;
        }}
        """
    return base_style


class BasePropertyEdit[T](StyledWidget):
    def __init__(self, parent: QtWidgets.QWidget | None, context: PropertyEditContext):
        super().__init__(parent)

        self.context = context
        self.in_dragging = False
        self.base_style = get_property_edit_style_sheet()

    async def _do_set_value_async(self, value: T, undo: bool):
        await SceneEditRequestBus().set_property(
            self.context.key,
            value=value,
            undo=undo,
            source="ui",
        )

    def _do_set_value(self, value: T, undo: bool):
        asyncio.create_task(self._do_set_value_async(value, undo))

    def _on_start_drag(self):
        SceneEditRequestBus().start_change_property(self.context.key)
        self.in_dragging = True

    def _on_end_drag(self):
        async def warpper():
            # We must await here to ensure the property change is commited.
            await self._do_set_value_async(self.context.prop.value(), undo=True)
            SceneEditRequestBus().end_change_property(self.context.key)
            self.in_dragging = False

        asyncio.create_task(warpper())

    def set_value(self, value: T):
        pass

    def _create_label(self, label_width: int) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(self.context.prop.name())
        label.setFixedWidth(label_width)
        label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        return label
