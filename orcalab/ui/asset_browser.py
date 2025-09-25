import asyncio
from typing import List
from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtCore import Qt
import time
from orcalab.actor import BaseActor, GroupActor

class AssetListModel(QtCore.QStringListModel):
    asset_mime = "application/x-orca-asset"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_assets = []
        self._include_filter = ""
        self._exclude_filter = ""

    def mimeTypes(self):
        return [self.asset_mime]

    def mimeData(self, indexes):
        if not indexes:
            return None
        asset_name = indexes[0].data(Qt.DisplayRole)
        mime = QtCore.QMimeData()
        mime.setData(self.asset_mime, asset_name.encode("utf-8"))
        return mime

    def set_assets(self, assets: List[str]):
        """设置所有 assets 并应用当前过滤条件"""
        self._all_assets = [str(asset) for asset in assets]
        self._apply_filters()

    def set_include_filter(self, filter_text: str):
        """设置正向匹配过滤条件"""
        self._include_filter = filter_text
        self._apply_filters()

    def set_exclude_filter(self, filter_text: str):
        """设置剔除匹配过滤条件"""
        self._exclude_filter = filter_text
        self._apply_filters()

    def _apply_filters(self):
        """应用过滤条件并更新模型"""
        filtered_assets = self._all_assets.copy()

        # 应用正向匹配过滤
        if self._include_filter:
            include_lower = self._include_filter.lower()
            filtered_assets = [
                asset for asset in filtered_assets 
                if include_lower in asset.lower()
            ]

        # 应用剔除匹配过滤
        if self._exclude_filter:
            exclude_lower = self._exclude_filter.lower()
            filtered_assets = [
                asset for asset in filtered_assets 
                if exclude_lower not in asset.lower()
            ]

        self.setStringList(filtered_assets)

    def get_total_count(self):
        """获取总 assets 数量"""
        return len(self._all_assets)

    def get_filtered_count(self):
        """获取过滤后的 assets 数量"""
        return len(self.stringList())


class AssetBrowser(QtWidgets.QWidget):

    add_item = QtCore.Signal(str, BaseActor)

    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self):
        """设置 UI 组件"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 正向匹配搜索框
        include_layout = QtWidgets.QHBoxLayout()
        include_label = QtWidgets.QLabel("包含:")
        include_label.setFixedWidth(40)
        include_label.setStyleSheet("color: #ffffff; font-size: 11px;")
        include_layout.addWidget(include_label)
        
        self.include_search_box = QtWidgets.QLineEdit()
        self.include_search_box.setPlaceholderText("输入要包含的文本...")
        self.include_search_box.setStyleSheet("""
            QLineEdit {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
        """)
        include_layout.addWidget(self.include_search_box)
        layout.addLayout(include_layout)

        # 剔除匹配搜索框
        exclude_layout = QtWidgets.QHBoxLayout()
        exclude_label = QtWidgets.QLabel("排除:")
        exclude_label.setFixedWidth(40)
        exclude_label.setStyleSheet("color: #ffffff; font-size: 11px;")
        exclude_layout.addWidget(exclude_label)
        
        self.exclude_search_box = QtWidgets.QLineEdit()
        self.exclude_search_box.setPlaceholderText("输入要排除的文本...")
        self.exclude_search_box.setStyleSheet("""
            QLineEdit {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #dc3545;
            }
        """)
        exclude_layout.addWidget(self.exclude_search_box)
        layout.addLayout(exclude_layout)

        # 资产列表
        self.list_view = QtWidgets.QListView()
        self.list_view.setDragEnabled(True)
        self.list_view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.list_view.setStyleSheet("""
            QListView {
                background-color: #2b2b2b;
                color: #ffffff;
                border: none;
                selection-background-color: #404040;
                alternate-background-color: #333333;
            }
            QListView::item:selected {
                background-color: #404040;
                color: #ffffff;
            }
            QListView::item:hover {
                background-color: #353535;
            }
        """)
        layout.addWidget(self.list_view)

        # 状态标签
        self.status_label = QtWidgets.QLabel("0 assets")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 11px;
                padding: 2px 8px;
                background-color: #2b2b2b;
                border-top: 1px solid #404040;
            }
        """)
        layout.addWidget(self.status_label)

        # 设置模型
        self._model = AssetListModel()
        self.list_view.setModel(self._model)

        # 初始化拖拽相关属性
        self.dragging = False
        self.selected_item_name = None
        self._drag_start_pos = None
        self.actor_outline_hwnd = None

    def _setup_connections(self):
        """设置信号连接"""
        self.include_search_box.textChanged.connect(self._on_include_filter_changed)
        self.exclude_search_box.textChanged.connect(self._on_exclude_filter_changed)
        self.list_view.customContextMenuRequested.connect(self.show_context_menu)
        self._model.rowsInserted.connect(self._update_status)
        self._model.rowsRemoved.connect(self._update_status)
        self._model.modelReset.connect(self._update_status)

    def set_assets(self, assets: List[str]):
        """设置 assets 列表"""
        self._model.set_assets(assets)
        self._update_status()

    def _on_include_filter_changed(self, text: str):
        """正向匹配过滤条件改变"""
        self._model.set_include_filter(text)
        self._update_status()

    def _on_exclude_filter_changed(self, text: str):
        """剔除匹配过滤条件改变"""
        self._model.set_exclude_filter(text)
        self._update_status()

    def _update_status(self):
        """更新状态显示"""
        total_count = self._model.get_total_count()
        filtered_count = self._model.get_filtered_count()
        
        if self.include_search_box.text() or self.exclude_search_box.text():
            self.status_label.setText(f"{filtered_count} / {total_count} assets")
        else:
            self.status_label.setText(f"{total_count} assets")

    def show_context_menu(self, pos):
        """显示右键菜单"""
        index = self.list_view.indexAt(pos)
        if not index.isValid():
            return
        selected_item_name = index.data(QtCore.Qt.DisplayRole)
        context_menu = QtWidgets.QMenu(self)
        add_action = QtGui.QAction(f"Add {selected_item_name}", self)
        add_action.triggered.connect(lambda: self.on_add_item(selected_item_name))
        context_menu.addAction(add_action)
        context_menu.exec(self.list_view.mapToGlobal(pos))

    def on_add_item(self, item_name):
        """添加项目到场景"""
        self.add_item.emit(item_name, None)

    def clear_filters(self):
        """清除所有过滤条件"""
        self.include_search_box.clear()
        self.exclude_search_box.clear()

    def get_filtered_assets(self):
        """获取当前过滤后的 assets 列表"""
        return self._model.stringList()

    def get_all_assets(self):
        """获取所有 assets 列表"""
        return self._model._all_assets