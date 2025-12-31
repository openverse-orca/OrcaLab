from typing import List
from PySide6 import QtCore, QtWidgets
from orcalab.ui.asset_browser.asset_info import AssetInfo


class AssetTreeView(QtWidgets.QTreeWidget):
    category_selected = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setHeaderLabel("资产分类")
        self.setMinimumWidth(200)
        self.setMaximumWidth(300)
        
        self._assets: List[AssetInfo] = []
        # self._setup_style()
        
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
        
        category_map = {}
        root_item = QtWidgets.QTreeWidgetItem(self, ["/"])
        root_item.setData(0, QtCore.Qt.UserRole, "/")
        category_map["/"] = root_item
        other_item = QtWidgets.QTreeWidgetItem(root_item, ["other"])
        other_item.setData(0, QtCore.Qt.UserRole, "/other")
        category_map["/other"] = other_item

        for asset in self._assets:
            if asset.metadata is not None:
                self._build_branch(asset.metadata['categoryPath'], category_map)
        
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
        category = item.data(0, QtCore.Qt.UserRole)
        self.category_selected.emit(category)

