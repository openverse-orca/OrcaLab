from typing import List, Set

from PySide6 import QtCore, QtWidgets

from orcalab.ui.fonts.font_service import FontService
from orcalab.ui.multi_select_combo import MultiSelectCombo


class FilterBar(QtWidgets.QWidget):
    filter_changed = QtCore.Signal()

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

    def set_available_types(self, type_items: List[tuple[str, str]]):
        self._type_combo.set_items(type_items)

    def get_search_text(self) -> str:
        return self._search_edit.text().strip()

    def get_selected_component_types(self) -> Set[str] | None:
        return self._type_combo.selected_items()

    def _on_filter_changed(self):
        self.filter_changed.emit()