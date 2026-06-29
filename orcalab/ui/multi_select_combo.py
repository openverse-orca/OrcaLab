from typing import Dict, List, Set

from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.ui.fonts.font_service import FontService
from orcalab.ui.theme_service import ThemeService


class MultiSelectCombo(QtWidgets.QWidget):
    """单选下拉框：第一项为"全部显示"，后续为各个组件类型，点击单选。"""

    selection_changed = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)

        self._items: List[str] = []
        self._item_data: Dict[str, str] = {}
        self._selected: str | None = None

        self._btn = QtWidgets.QPushButton("全部显示")
        self._btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(self._show_popup)
        FontService().bind_widget_font(self._btn, "property_edit")

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._btn)

    def set_items(self, items: List[tuple[str, str]]):
        """items: [(内部名, 显示名), ...]"""
        self._items = [item[0] for item in items]
        self._item_data.clear()
        for key, display in items:
            self._item_data[key] = display
        self._selected = None
        self._update_button_text()

    def selected_items(self) -> Set[str] | None:
        if self._selected is None:
            return None
        return {self._selected}

    def _update_button_text(self):
        if self._selected is None:
            self._btn.setText("全部显示")
        else:
            self._btn.setText(self._item_data.get(self._selected, self._selected))

    def _show_popup(self):
        menu = QtWidgets.QMenu(self._btn)

        theme = ThemeService()
        bg = theme.get_color_hex("surface")
        border = theme.get_color_hex("border")

        menu.setStyleSheet(
            f"QMenu {{ background: {bg}; border: 1px solid {border}; padding: 4px; }}"
        )

        action_all = QtGui.QAction("全部显示", menu)
        action_all.setCheckable(True)
        action_all.setChecked(self._selected is None)
        action_all.triggered.connect(lambda: self._select_item(None))
        menu.addAction(action_all)

        if self._items:
            menu.addSeparator()

        for key in self._items:
            display = self._item_data.get(key, key)
            action = QtGui.QAction(display, menu)
            action.setCheckable(True)
            action.setChecked(key == self._selected)
            action.setData(key)
            action.triggered.connect(lambda _checked, k=key: self._select_item(k))
            menu.addAction(action)

        pos = self._btn.mapToGlobal(QtCore.QPoint(0, self._btn.height()))
        menu.exec(pos)

    def _select_item(self, key: str | None):
        if self._selected == key:
            return
        self._selected = key
        self._update_button_text()
        self.selection_changed.emit()