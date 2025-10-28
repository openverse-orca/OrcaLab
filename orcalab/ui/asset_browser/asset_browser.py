import asyncio
from typing import List, override
from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtCore import Qt
import time
from orcalab.actor import BaseActor, GroupActor

from orcalab.ui.asset_browser.asset_info import AssetInfo
from orcalab.ui.asset_browser.asset_view import AssetView
from orcalab.ui.asset_browser.asset_model import AssetModel
from orcalab.ui.asset_browser.asset_info_view import AssetInfoView


class AssetBrowser(QtWidgets.QWidget):

    add_item = QtCore.Signal(str, BaseActor)

    create_panorama_gif = QtCore.Signal(str)

    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self):

        # 正向匹配搜索框

        include_label = QtWidgets.QLabel("包含:")
        include_label.setFixedWidth(40)
        include_label.setStyleSheet("color: #ffffff; font-size: 11px;")

        self.include_search_box = QtWidgets.QLineEdit()
        self.include_search_box.setPlaceholderText("输入要包含的文本...")
        self.include_search_box.setStyleSheet(
            """
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
        """
        )

        # 剔除匹配搜索框

        exclude_label = QtWidgets.QLabel("排除:")
        exclude_label.setFixedWidth(40)
        exclude_label.setStyleSheet("color: #ffffff; font-size: 11px;")

        self.exclude_search_box = QtWidgets.QLineEdit()
        self.exclude_search_box.setPlaceholderText("输入要排除的文本...")
        self.exclude_search_box.setStyleSheet(
            """
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
        """
        )

        self.create_panorama_gif_button = QtWidgets.QPushButton("创建周视图")
        self.create_panorama_gif_button.setStyleSheet(
            """
            QPushButton {
                background-color: #007acc;
                color: #ffffff;
                border: none;
                border-radius: 3px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
            QPushButton:pressed {
                background-color: #004578;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #999999;
            }
        """
        )

        # 状态标签
        self.status_label = QtWidgets.QLabel("0 assets")
        self.status_label.setStyleSheet(
            """
            QLabel {
                color: #888888;
                font-size: 11px;
                padding: 2px 8px;
                background-color: #2b2b2b;
                border-top: 1px solid #404040;
            }
        """
        )

        self._view = AssetView()
        self._model = AssetModel()
        self._view.set_model(self._model)

        self._info_view = AssetInfoView()
        self._info_view.setFixedWidth(250)

        tool_bar_layout = QtWidgets.QHBoxLayout()
        tool_bar_layout.setContentsMargins(0, 0, 0, 0)
        tool_bar_layout.setSpacing(0)

        tool_bar_layout.addWidget(include_label)
        tool_bar_layout.addWidget(self.include_search_box)
        tool_bar_layout.addSpacing(10)
        tool_bar_layout.addWidget(exclude_label)
        tool_bar_layout.addWidget(self.exclude_search_box)
        tool_bar_layout.addStretch()
        tool_bar_layout.addWidget(self.create_panorama_gif_button)
        tool_bar_layout.addSpacing(5)
        tool_bar_layout.addWidget(self.status_label)

        left_layout = QtWidgets.QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        left_layout.addLayout(tool_bar_layout)
        left_layout.addWidget(self._view, 1)

        root_layout = QtWidgets.QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addLayout(left_layout)
        root_layout.addWidget(self._info_view)

        self._view.selection_changed.connect(self._on_selection_changed)

    def _setup_connections(self):
        """设置信号连接"""
        self.include_search_box.textChanged.connect(self._on_include_filter_changed)
        self.exclude_search_box.textChanged.connect(self._on_exclude_filter_changed)
        # self.create_panorama_gif_button.clicked.connect(
        #     self._on_create_panorama_gif_clicked
        # )

    def set_assets(self, assets: List[str]):
        infos = []

        for asset in assets:
            info = AssetInfo()
            info.name = asset.split("/")[-1]
            info.path = asset
            infos.append(info)

        self._model.set_assets(infos)

    def _on_include_filter_changed(self, text: str):
        self._model.include_filter = text
        self._model.apply_filters()

    def _on_exclude_filter_changed(self, text: str):
        self._model.exclude_filter = text
        self._model.apply_filters()

    def _on_selection_changed(self):
        index = self._view.selected_index()
        if index == -1:
            self._info_view.set_asset_info(None)
        else:
            info = self._model.info_at(index)
            self._info_view.set_asset_info(info)

    # def _update_status(self):
    #     total_count = self._model.get_total_count()
    #     filtered_count = self._model.get_filtered_count()

    #     if self.include_search_box.text() or self.exclude_search_box.text():
    #         self.status_label.setText(f"{filtered_count} / {total_count} assets")
    #     else:
    #         self.status_label.setText(f"{total_count} assets")

    # def show_context_menu(self, pos):
    #     """显示右键菜单"""
    #     index = self.list_view.indexAt(pos)
    #     if not index.isValid():
    #         return
    #     selected_item_name = index.data(QtCore.Qt.DisplayRole)
    #     context_menu = QtWidgets.QMenu(self)
    #     add_action = QtGui.QAction(f"Add {selected_item_name}", self)
    #     add_action.triggered.connect(lambda: self.on_add_item(selected_item_name))
    #     context_menu.addAction(add_action)
    #     context_menu.exec(self.list_view.mapToGlobal(pos))

    # def _on_create_panorama_gif_clicked(self):
    #     """创建周视图"""
    #     if len(self.list_view.selectedIndexes()) == 0:
    #         return
    #     selected_item_name = self.list_view.selectedIndexes()[0].data(
    #         QtCore.Qt.DisplayRole
    #     )
    #     self.create_panorama_gif.emit(selected_item_name)
