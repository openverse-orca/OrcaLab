import asyncio
import json
import os
import shutil
import webbrowser
from typing import List, override
from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtCore import Qt
import logging
from orcalab.actor import BaseActor, GroupActor

from orcalab.ui.asset_browser.asset_info import AssetInfo
from orcalab.ui.asset_browser.asset_view import AssetView
from orcalab.ui.asset_browser.asset_model import AssetModel
from orcalab.ui.asset_browser.asset_info_view import AssetInfoView
from orcalab.ui.asset_browser.asset_tree_view import AssetTreeView
from orcalab.ui.asset_browser.apng_player import ApngPlayer
from orcalab.metadata_service import MetadataService
from orcalab.ui.asset_browser.thumbnail_render_bus import ThumbnailRenderRequestBus
from orcalab.ui.asset_browser.thumbnail_render_service import ThumbnailRenderService
from orcalab.http_service.http_service import HttpService
from orcalab.project_util import get_cache_folder
from orcalab.config_service import ConfigService

logger = logging.getLogger(__name__)
class AssetBrowser(QtWidgets.QWidget):

    add_item = QtCore.Signal(str, BaseActor)

    render_thumbnail = QtCore.Signal(list)
    on_render_thumbnail_finished = QtCore.Signal(list)
    on_upload_thumbnail_finished = QtCore.Signal()
    request_load_thumbnail = QtCore.Signal(int)

    def __init__(self):
        super().__init__()
        self._metadata_service = MetadataService()
        self._thumbnail_render_service = ThumbnailRenderService()
        self._http_service = HttpService()
        self._config_service = ConfigService()
        self._loading_thumbnails = set()
        self._model_connected = False
        self.is_admin =  self._http_service.is_admin()
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

        if self.is_admin:
            self.create_panorama_apng_button = QtWidgets.QPushButton("渲染缩略图")
            self.create_panorama_apng_button.setToolTip("渲染资产缩略图")
            self.create_panorama_apng_button.setStyleSheet(
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

        self.open_asset_store_button = QtWidgets.QPushButton("打开资产库")
        self.open_asset_store_button.setToolTip("在浏览器中打开资产库")
        self.open_asset_store_button.setStyleSheet(
            """
            QPushButton {
                background-color: #28a745;
                color: #ffffff;
                border: none;
                border-radius: 3px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
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

        self._tree_view = AssetTreeView()
        
        self._view = AssetView()
        self._model = AssetModel()
        self._view.set_model(self._model)
        self._view.set_loading_text("正在加载资产缩略图...")

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
        tool_bar_layout.addWidget(self.open_asset_store_button)
        tool_bar_layout.addSpacing(5)
        if self.is_admin:
            tool_bar_layout.addWidget(self.create_panorama_apng_button)
            tool_bar_layout.addSpacing(5)
        tool_bar_layout.addWidget(self.status_label)

        center_layout = QtWidgets.QVBoxLayout()
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        center_layout.addLayout(tool_bar_layout)
        center_layout.addWidget(self._view, 1)

        root_layout = QtWidgets.QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._tree_view)
        root_layout.addLayout(center_layout)
        root_layout.addWidget(self._info_view)

        self._view.selection_changed.connect(self._on_selection_changed)
        self._tree_view.category_selected.connect(self._on_category_selected)

    def _setup_connections(self):
        """设置信号连接"""
        self.include_search_box.textChanged.connect(self._on_include_filter_changed)
        self.exclude_search_box.textChanged.connect(self._on_exclude_filter_changed)
        self.open_asset_store_button.clicked.connect(self._on_open_asset_store_clicked)
        if self.is_admin:
            self.create_panorama_apng_button.clicked.connect(
                lambda: asyncio.create_task(self._on_create_panorama_apng_clicked())
            )
            self.on_render_thumbnail_finished.connect(
                lambda asset_paths: asyncio.create_task(self._on_render_thumbnail_finished(asset_paths))
            )
            self.on_upload_thumbnail_finished.connect(
                lambda: asyncio.create_task(self._on_upload_thumbnail_finished())
            )
        self.request_load_thumbnail.connect(
            lambda index: asyncio.create_task(self._load_thumbnail_for_index(index))
        )
    
    def _on_category_selected(self, category: str):
        self._model.category_filter = category
        self._model.apply_filters()
        self._view._scroll_bar.setValue(0)
        
    async def set_assets(self, assets: List[str]):
        if self.is_admin:
            self.create_panorama_apng_button.setDisabled(True)
        infos = []
        thumbnail_cache_path = get_cache_folder() / "thumbnail"
        exclude_assets = ['prefabs/mujococamera1080', 'prefabs/mujococamera256', 'prefabs/mujococamera512']
        
        # 只检查本地缓存，不从服务器下载
        for asset in assets:
            info = AssetInfo()
            info.name = asset.split("/")[-1]
            info.path = asset
            if info.path in exclude_assets:
                continue
            info.metadata = self._metadata_service.get_asset_info(asset)
            
            # 检查本地缓存，如果已下载则直接加载
            thumbnail_path = thumbnail_cache_path / (asset + "_panorama.apng")
            if thumbnail_path.exists():
                player = ApngPlayer(str(thumbnail_path))
                if player.is_valid():
                    player.set_scaled_size(QtCore.QSize(96, 96))
                    info.apng_player = player
            
            infos.append(info)
        
        self._view.set_loading_text(None)
        self._model.set_assets(infos)
        
        # 只在第一次连接信号
        if not self._model_connected:
            self._model.request_load_thumbnail.connect(self.request_load_thumbnail.emit)
            self._model_connected = True
        
        self._tree_view.set_assets(infos)
        if self.is_admin:
            self.create_panorama_apng_button.setText("渲染缩略图")
            self.create_panorama_apng_button.setDisabled(False)
        self.status_label.setText(f"{len(infos)} assets")
        
        # 主动触发一次可见项更新，加载初始可见的缩略图
        await asyncio.sleep(0.05)
        self._trigger_initial_thumbnail_load()

    def _on_include_filter_changed(self, text: str):
        self._model.include_filter = text
        self._model.apply_filters()

    def _on_exclude_filter_changed(self, text: str):
        self._model.exclude_filter = text
        self._model.apply_filters()

    def _on_open_asset_store_clicked(self):
        asset_store_url = self._config_service.web_server_url()
        try:
            webbrowser.open(asset_store_url)
            logger.info(f"Opening asset store: {asset_store_url}")
        except Exception as e:
            logger.error(f"Failed to open asset store: {e}")
    
    def _trigger_initial_thumbnail_load(self):
        """触发初始可见项的缩略图加载"""
        for item in self._view.visible_items:
            info = self._model.info_at(item.index)
            if info.apng_player is None and info.metadata is not None:
                if info.path not in self._loading_thumbnails:
                    self.request_load_thumbnail.emit(item.index)
    
    async def _load_thumbnail_for_index(self, index: int):
        """按需加载指定索引的缩略图"""
        try:
            info = self._model.info_at(index)
            if info.apng_player is not None:
                return
            
            if info.metadata is None:
                return
            
            # 避免重复下载
            if info.path in self._loading_thumbnails:
                return
            
            thumbnail_cache_path = get_cache_folder() / "thumbnail"
            thumbnail_path = thumbnail_cache_path / (info.path + "_panorama.apng")
            
            if thumbnail_path.exists():
                player = ApngPlayer(str(thumbnail_path))
                if player.is_valid():
                    player.set_scaled_size(QtCore.QSize(96, 96))
                    info.apng_player = player
                    self._model.notify_item_updated(index)
                return
            
            # 标记为正在加载
            self._loading_thumbnails.add(info.path)
            
            try:
                # 从服务器获取 URL 并下载
                url_result = await self._http_service.get_image_url(info.metadata['id'])
                if url_result is None or isinstance(url_result, Exception):
                    return
                
                image_url = json.loads(url_result)
                for picture_url in image_url['pictures']:
                    if picture_url['viewType'] == "dynamic":
                        await self._http_service.get_asset_thumbnail2cache(picture_url['imgUrl'], thumbnail_path)
                        
                        if thumbnail_path.exists():
                            player = ApngPlayer(str(thumbnail_path))
                            if player.is_valid():
                                player.set_scaled_size(QtCore.QSize(96, 96))
                                info.apng_player = player
                                self._model.notify_item_updated(index)
                        break
            finally:
                # 下载完成，移除标记
                self._loading_thumbnails.discard(info.path)
                
        except Exception as e:
            logger.error(f"Failed to load thumbnail for index {index}: {e}")
            self._loading_thumbnails.discard(info.path)

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

    async def _on_create_panorama_apng_clicked(self):
        """创建APNG全景图"""
        self.create_panorama_apng_button.setDisabled(True)
        self.create_panorama_apng_button.setText("渲染中...")
        assets = self._model.get_all_assets()
        asset_paths = []
        cache_thumbnail_path = get_cache_folder() / "thumbnail"
        for asset in assets:
            asset_path = asset.path.removesuffix('.spawnable')
            asset_paths.append(asset_path)
        if len(assets) == 0:
            self.create_panorama_apng_button.setText("渲染缩略图")
            self.create_panorama_apng_button.setDisabled(False)
            return
        await self._thumbnail_render_service.render_thumbnail(asset_paths)
        self.on_render_thumbnail_finished.emit(asset_paths)

    async def _on_render_thumbnail_finished(self, asset_paths: List[str]):
        asset_map = self._metadata_service.get_asset_map()
        if asset_map is None:
            self.create_panorama_apng_button.setText("渲染缩略图")
            self.create_panorama_apng_button.setDisabled(False)
            return
        self.create_panorama_apng_button.setText("加载中...")
        self.create_panorama_apng_button.setDisabled(True)
        await self._http_service.wait_for_upload_finished()

        self.on_upload_thumbnail_finished.emit()

    async def _on_upload_thumbnail_finished(self):
        tmp_path = os.path.join(os.path.expanduser("~"), ".orcalab", "tmp")
        subscription_metadata = await self._http_service.get_subscription_metadata()
        if subscription_metadata is None:
            self.create_panorama_apng_button.setText("渲染缩略图")
            self.create_panorama_apng_button.setDisabled(False)
            return
        subscription_metadata = json.loads(subscription_metadata)
        with open(os.path.join(get_cache_folder(), "metadata.json"), "w") as f:
            json.dump(subscription_metadata, f, ensure_ascii=False, indent=2)

        self._metadata_service.reload_metadata()
        all_assets = self._model.get_all_assets()
        # 移除相机
        asset_paths = [asset.path for asset in all_assets]
        if 'prefabs/mujococamera1080' in asset_paths:
            all_assets.pop(asset_paths.index('prefabs/mujococamera1080'))
            asset_paths.pop(asset_paths.index('prefabs/mujococamera1080'))
        if 'prefabs/mujococamera256' in asset_paths:
            all_assets.pop(asset_paths.index('prefabs/mujococamera256'))
            asset_paths.pop(asset_paths.index('prefabs/mujococamera256'))
        if 'prefabs/mujococamera512' in asset_paths:
            all_assets.pop(asset_paths.index('prefabs/mujococamera512'))
            asset_paths.pop(asset_paths.index('prefabs/mujococamera512'))
        # 预处理：拷贝本地缩略图，收集需要下载的任务
        new_assets = []
        download_tasks = []
        download_info = []  # (asset_index, cache_path)
        
        for asset in all_assets:
            new_assets.append(asset)
            tmp_thumbnail_path = os.path.join(tmp_path, f"{asset.path}_panorama.apng").__str__()
            cache_thumbnail_path = os.path.join(get_cache_folder(), "thumbnail", f"{asset.path}_panorama.apng").__str__()
            asset.metadata = self._metadata_service.get_asset_info(asset.path)
            if asset.metadata is None:
                if not os.path.exists(cache_thumbnail_path):
                    os.makedirs(os.path.dirname(cache_thumbnail_path), exist_ok=True)
                    try:
                        shutil.copy(tmp_thumbnail_path, cache_thumbnail_path)
                    except Exception as e:
                        logger.error(f"failed to copy {tmp_thumbnail_path} to {cache_thumbnail_path}: {e}")
                        continue
                    player = ApngPlayer(str(cache_thumbnail_path))
                    if player.is_valid():
                        player.set_scaled_size(QtCore.QSize(96, 96))
                        asset.apng_player = player
            else:
                if not os.path.exists(cache_thumbnail_path):
                    try:
                        pictures_url = asset.metadata['pictures']
                    except Exception as e:
                        logger.error(f"failed to get pictures url for {asset.path}: {e}")
                        continue
                    for picture_url in pictures_url:
                        if picture_url['viewType'] == "dynamic":
                            download_tasks.append(
                                self._http_service.get_asset_thumbnail2cache(picture_url['imgUrl'], cache_thumbnail_path)
                            )
                            download_info.append((len(new_assets) - 1, cache_thumbnail_path))
                            break
        
        # 并行下载所有缩略图
        if download_tasks:
            await asyncio.gather(*download_tasks, return_exceptions=True)
            
            # 为下载成功的资产创建播放器
            for asset_idx, cache_path in download_info:
                if os.path.exists(cache_path):
                    player = ApngPlayer(str(cache_path))
                    if player.is_valid():
                        player.set_scaled_size(QtCore.QSize(96, 96))
                        new_assets[asset_idx].apng_player = player
        
        self._model.set_assets(new_assets)
        self._tree_view.set_assets(new_assets)

        if os.path.exists(tmp_path):
            shutil.rmtree(tmp_path)

        self.create_panorama_apng_button.setText("渲染缩略图")
        self.create_panorama_apng_button.setDisabled(False)

