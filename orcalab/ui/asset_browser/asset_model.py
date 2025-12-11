from typing import List, override
from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.ui.asset_browser.asset_info import AssetInfo
from orcalab.ui.asset_browser.thumbnail_model import ThumbnailModel
from orcalab.ui.asset_browser.apng_player import ApngPlayer


class AssetModel(ThumbnailModel):
    
    request_load_thumbnail = QtCore.Signal(int)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._all_assets: List[AssetInfo] = []
        self._filtered_assets: List[AssetInfo] = []
        self.include_filter = ""
        self.exclude_filter = ""
        self.category_filter : str = ""

    @override
    def size(self) -> int:
        return len(self._filtered_assets)

    @override
    def image_at(self, index: int) -> QtGui.QImage:
        image = QtGui.QImage(128, 128, QtGui.QImage.Format_ARGB32)
        random_color = QtGui.QColor(
            (index * 25) % 256, (index * 50) % 256, (index * 75) % 256
        )
        image.fill(random_color)
        return image

    @override
    def movie_at(self, index: int) -> ApngPlayer | None:
        if index < 0 or index >= len(self._filtered_assets):
            return None
        
        info = self._filtered_assets[index]
        if info.apng_player is None and info.metadata is not None:
            self.request_load_thumbnail.emit(index)
        
        return info.apng_player


    @override
    def text_at(self, index: int) -> str:
        return self._filtered_assets[index].name

    def info_at(self, index: int) -> AssetInfo:
        return self._filtered_assets[index]

    def set_assets(self, asset_list: List[AssetInfo]) -> None:
        self._all_assets = asset_list
        self.apply_filters()

    def apply_filters(self):
        list1 = self._apply_category_filter(self._all_assets)
        list2 = self._apply_include_filter(list1)
        list3 = self._apply_exclude_filter(list2)
        self._filtered_assets = list3
        self.data_updated.emit()

    def get_all_assets(self) -> List[AssetInfo]:
        return self._all_assets
    
    def notify_item_updated(self, index: int) -> None:
        """通知指定索引的项已更新"""
        self.item_updated.emit(index)
    
    def _apply_category_filter(self, input: List[AssetInfo]):
        if self.category_filter == "":
            return input

        result: List[AssetInfo] = []
        for asset in input:
            if asset.metadata is not None:
                if asset.metadata['categoryPath'].startswith(self.category_filter):
                    result.append(asset)
            else:
                if self.category_filter == "/other":
                    result.append(asset)
        return result

    def _apply_include_filter(self, input: List[AssetInfo]):
        if not self.include_filter:
            return input

        result: List[AssetInfo] = []
        include_lower = self.include_filter.lower()
        for asset in input:
            if include_lower in asset.name.lower():
                result.append(asset)

        return result

    def _apply_exclude_filter(self, input: List[AssetInfo]):
        if not self.exclude_filter:
            return input

        result: List[AssetInfo] = []
        exclude_lower = self.exclude_filter.lower()
        for asset in input:
            if exclude_lower not in asset.name.lower():
                result.append(asset)

        return result
