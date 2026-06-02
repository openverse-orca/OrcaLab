from typing import List, Tuple

from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.texture_asset_cache import TextureAssetCache
from orcalab.ui.fonts.font_service import FontService
from orcalab.ui.theme_service import ThemeService


def _extract_texture_display_name(path: str) -> str:
    filename = path.replace("\\", "/").split("/")[-1]
    if filename.endswith(".streamingimage"):
        filename = filename[:-len(".streamingimage")]
    for ext in (".png", ".jpg", ".jpeg", ".tga", ".dds", ".bmp", ".tif", ".tiff", ".exr", ".hdr"):
        if filename.lower().endswith(ext):
            filename = filename[:-len(ext)]
            break
    return filename


class TextureSelectDialog(QtWidgets.QDialog):
    texture_selected = QtCore.Signal(str)

    def __init__(
        self,
        cache: TextureAssetCache,
        parent: QtWidgets.QWidget | None = None,
    ):
        super().__init__(parent)
        self._cache = cache
        self._selected_uuid: str | None = None
        self._all_items: List[Tuple[str, str]] = []

        self.setWindowTitle("选择纹理")
        self.setMinimumSize(500, 400)
        self.resize(600, 500)
        self.setModal(True)

        self._build_ui()
        self._load_items()

    def _build_ui(self):
        theme = ThemeService()
        fs = FontService()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._search_edit = QtWidgets.QLineEdit()
        self._search_edit.setPlaceholderText("搜索纹理...")
        self._search_edit.textChanged.connect(self._on_search_changed)
        fs.bind_widget_font(self._search_edit, "property_edit")
        layout.addWidget(self._search_edit)

        self._list_widget = QtWidgets.QListWidget()
        self._list_widget.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self._list_widget.currentItemChanged.connect(self._on_selection_changed)
        fs.bind_widget_font(self._list_widget, "property_edit")
        layout.addWidget(self._list_widget)

        self._status_label = QtWidgets.QLabel()
        fs.bind_widget_font(self._status_label, "property_edit")
        layout.addWidget(self._status_label)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(8)

        self._clear_button = QtWidgets.QPushButton("清除")
        self._clear_button.clicked.connect(self._on_clear)
        fs.bind_widget_font(self._clear_button, "property_edit")
        button_layout.addWidget(self._clear_button)

        button_layout.addStretch()

        self._cancel_button = QtWidgets.QPushButton("取消")
        self._cancel_button.clicked.connect(self.reject)
        fs.bind_widget_font(self._cancel_button, "property_edit")
        button_layout.addWidget(self._cancel_button)

        self._ok_button = QtWidgets.QPushButton("确定")
        self._ok_button.clicked.connect(self._on_accept)
        self._ok_button.setEnabled(False)
        fs.bind_widget_font(self._ok_button, "property_edit")
        button_layout.addWidget(self._ok_button)

        layout.addLayout(button_layout)

        bg_color = theme.get_color_hex("property_group_bg")
        text_color = theme.get_color_hex("text")
        brand_color = theme.get_color_hex("brand")

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
            }}
            QListWidget {{
                background-color: {bg_color};
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                color: {text_color};
            }}
            QListWidget::item {{
                padding: 6px 8px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            }}
            QListWidget::item:selected {{
                background-color: {brand_color};
                color: white;
            }}
            QLineEdit {{
                background-color: {bg_color};
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 6px 8px;
                color: {text_color};
            }}
            QPushButton {{
                background-color: {bg_color};
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 4px;
                padding: 6px 16px;
                color: {text_color};
            }}
            QPushButton:hover {{
                border-color: {brand_color};
            }}
            QPushButton:disabled {{
                color: rgba(255, 255, 255, 0.3);
            }}
        """)

    def _load_items(self):
        self._all_items = self._cache.get_all_items()
        self._populate_list(self._all_items)

    def _populate_list(self, items: List[Tuple[str, str]]):
        self._list_widget.clear()
        for uuid_str, path in items:
            display = _extract_texture_display_name(path)
            item = QtWidgets.QListWidgetItem(display)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, uuid_str)
            item.setToolTip(path)
            self._list_widget.addItem(item)

        self._update_status(len(items))

    def _update_status(self, count: int):
        total = len(self._cache._uuid_to_path)
        if count == total:
            self._status_label.setText(f"共 {total} 个纹理")
        else:
            self._status_label.setText(f"显示 {count} / {total} 个纹理")

    def _on_search_changed(self, text: str):
        if not text:
            self._populate_list(self._all_items)
        else:
            results = self._cache.search(text)
            self._populate_list(results)

    def _on_selection_changed(self, current: QtWidgets.QListWidgetItem, previous: QtWidgets.QListWidgetItem):
        if current is not None:
            self._selected_uuid = current.data(QtCore.Qt.ItemDataRole.UserRole)
            self._ok_button.setEnabled(True)
        else:
            self._selected_uuid = None
            self._ok_button.setEnabled(False)

    def _on_clear(self):
        self._selected_uuid = ""
        self._list_widget.clearSelection()
        self._ok_button.setEnabled(True)
        self.accept()

    def _on_accept(self):
        self.accept()

    def selected_uuid(self) -> str | None:
        return self._selected_uuid