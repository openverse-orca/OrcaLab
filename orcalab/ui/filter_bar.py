from typing import Set

from PySide6 import QtCore, QtWidgets

from orcalab.ui.fonts.font_service import FontService


class FilterBar(QtWidgets.QWidget):
    filter_changed = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        fs = FontService()

        self._search_edit = QtWidgets.QLineEdit()
        self._search_edit.setPlaceholderText("搜索属性...")
        self._search_edit.textChanged.connect(self._on_filter_changed)
        fs.bind_widget_font(self._search_edit, 'property_edit')
        layout.addWidget(self._search_edit)

        self._type_combo = QtWidgets.QComboBox()
        self._type_combo.addItem("全部类型", None)
        self._type_combo.currentIndexChanged.connect(self._on_filter_changed)
        fs.bind_widget_font(self._type_combo, 'property_edit')
        layout.addWidget(self._type_combo)

    @staticmethod
    def _strip_component_suffix(name: str) -> str:
        suffix = "Component"
        if len(name) > len(suffix) and name.endswith(suffix):
            return name[:-len(suffix)]
        return name

    def set_available_types(self, types: list[str]):
        current_data = self._type_combo.currentData()
        self._type_combo.blockSignals(True)
        self._type_combo.clear()
        self._type_combo.addItem("全部类型", None)
        for t in types:
            display_text = self._strip_component_suffix(t)
            self._type_combo.addItem(display_text, t)
        for i in range(self._type_combo.count()):
            if self._type_combo.itemData(i) == current_data:
                self._type_combo.setCurrentIndex(i)
                break
        self._type_combo.blockSignals(False)

    def get_search_text(self) -> str:
        return self._search_edit.text().strip()

    def get_selected_component_types(self) -> Set[str] | None:
        data = self._type_combo.currentData()
        if data is None:
            return None
        return {data}

    def _on_filter_changed(self):
        self.filter_changed.emit()
