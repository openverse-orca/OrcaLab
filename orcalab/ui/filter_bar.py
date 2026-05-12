from typing import List, Set

from PySide6 import QtCore, QtWidgets

from orcalab.ui.fonts.font_service import FontService
from orcalab.ui.multi_select_combo import MultiSelectCombo
from orcalab.ui.button import Button
from orcalab.ui.icon_util import make_icon
from orcalab.ui.theme_service import ThemeService
import orcalab.assets.rc_assets


class FilterBar(QtWidgets.QWidget):
    filter_changed = QtCore.Signal()
    show_transform_changed = QtCore.Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        fs = FontService()

        self._search_edit = QtWidgets.QLineEdit()
        self._search_edit.setPlaceholderText("搜索实体...")
        self._search_edit.textChanged.connect(self._on_filter_changed)
        fs.bind_widget_font(self._search_edit, 'property_edit')
        layout.addWidget(self._search_edit)

        self._type_combo = MultiSelectCombo()
        self._type_combo.selection_changed.connect(self._on_filter_changed)
        layout.addWidget(self._type_combo)

        theme = ThemeService()
        icon_color = theme.get_color("tool_icon")

        self._show_transform = False
        self._show_transform_button = Button(
            icon=make_icon(":/icons/coordinate_system.svg", icon_color)
        )
        self._show_transform_button.setToolTip("显示变换")
        self._show_transform_button.setFixedSize(28, 28)
        self._show_transform_button.icon_size = 18
        self._show_transform_button.bg_color = theme.get_color("button_bg")
        self._show_transform_button.mouse_pressed.connect(self._toggle_show_transform)
        layout.addWidget(self._show_transform_button)

    def set_available_types(self, type_items: List[tuple[str, str]]):
        self._type_combo.set_items(type_items)

    def get_search_text(self) -> str:
        return self._search_edit.text().strip()

    def get_selected_component_types(self) -> Set[str] | None:
        return self._type_combo.selected_items()

    def is_transform_visible(self) -> bool:
        return self._show_transform

    def _toggle_show_transform(self):
        self._show_transform = not self._show_transform
        if self._show_transform:
            self._show_transform_button.bg_color = ThemeService().get_color("button_bg_selected")
        else:
            self._show_transform_button.bg_color = ThemeService().get_color("button_bg")
        self._show_transform_button.update()
        self.show_transform_changed.emit(self._show_transform)

    def _on_filter_changed(self):
        self.filter_changed.emit()