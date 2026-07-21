from typing import List
from PySide6 import QtCore, QtWidgets
from orcalab.ui.asset_browser.asset_info import AssetInfo
from orcalab.ui.fonts.font_service import FontService


class AssetTreeView(QtWidgets.QTreeWidget):
    category_selected = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setHeaderLabel("资产分类")
        self.setMinimumWidth(200)
        
        self._assets: List[AssetInfo] = []
        self.category_map = {}
        
        fs = FontService()
        header = self.header()
        header.setFont(fs.get_font("tree_header"))
        fs.bind_widget_font(header, "tree_header")

        fs.bind_widget_font(self, "small")

        self.itemClicked.connect(self._on_item_clicked)

    def _setup_style(self):
        self.setStyleSheet("""
            QTreeWidget {
                background-color: #2b2b2b;
                color: #ffffff;
                border: none;
                outline: 0;
            }
            QTreeWidget::item {
                padding: 4px;
            }
            QTreeWidget::item:hover {
                background-color: #3c3c3c;
            }
            QTreeWidget::item:selected {
                background-color: #094771;
            }
        """)

    def set_assets(self, assets: List[AssetInfo]):
        self._assets = assets
        self._rebuild_tree()

    def _rebuild_tree(self):
        self.clear()
        
        self.category_map = {}
        root_item = QtWidgets.QTreeWidgetItem(self, ["/"])
        root_item.setData(0, QtCore.Qt.UserRole, "/")
        self.category_map["/"] = root_item

        paks_item = QtWidgets.QTreeWidgetItem(root_item, ["paks"])
        paks_item.setData(0, QtCore.Qt.UserRole, "/paks")
        self.category_map["/paks"] = paks_item

        other_item = QtWidgets.QTreeWidgetItem(root_item, ["other"])
        other_item.setData(0, QtCore.Qt.UserRole, "/other")
        self.category_map["/other"] = other_item

        for asset in self._assets:
            if asset.metadata is not None:
                category_path = asset.metadata.get('categoryPath', '')
                if isinstance(category_path, str) and category_path:
                    self._build_branch(category_path, self.category_map)

            if asset.pak_id not in self.category_map:
                paks_item = self.category_map.get("/paks")
                if paks_item is not None:
                    pak_item = QtWidgets.QTreeWidgetItem(paks_item, [asset.pak_name])
                    pak_item.setData(0, QtCore.Qt.UserRole, asset.pak_name)
                    self.category_map[asset.pak_id] = pak_item
        
        self.expandAll()

    def _build_branch(self, category: str, category_map: dict):
        if category not in category_map:
            parent_category = category.rsplit('/', 1)[0]
            if parent_category == "":
                parent_item = category_map["/"]
            else:
                parent_item = self._build_branch(parent_category, category_map)
            display_name = category.rsplit('/', 1)[1]
            category_item = QtWidgets.QTreeWidgetItem(parent_item, [display_name])
            category_item.setData(0, QtCore.Qt.UserRole, category)
            category_map[category] = category_item
        return category_map[category]

    
    def _on_item_clicked(self, item: QtWidgets.QTreeWidgetItem, column: int):
        for category, tree_item in self.category_map.items():
            if tree_item == item:
                self.category_selected.emit(category)
                return

