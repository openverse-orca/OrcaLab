from typing import Set

from PySide6 import QtCore, QtWidgets


class FilterBar(QtWidgets.QWidget):
    filter_changed = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        self._search_edit = QtWidgets.QLineEdit()
        self._search_edit.setPlaceholderText("搜索属性...")
        self._search_edit.textChanged.connect(self._on_filter_changed)
        layout.addWidget(self._search_edit)

        self._type_combo = QtWidgets.QComboBox()
        self._type_combo.addItem("全部类型", None)
        self._type_combo.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self._type_combo)

    def set_available_types(self, types: list[str]):
        current_data = self._type_combo.currentData()
        self._type_combo.blockSignals(True)
        self._type_combo.clear()
        self._type_combo.addItem("全部类型", None)
        for t in types:
            self._type_combo.addItem(t, t)
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
