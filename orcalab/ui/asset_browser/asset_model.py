from typing import List
from typing_extensions import override
from PySide6 import QtCore, QtWidgets, QtGui
import logging

from orcalab.ui.asset_browser.asset_info import AssetInfo
from orcalab.ui.asset_browser.thumbnail_model import ThumbnailModel
from orcalab.ui.asset_browser.apng_player import ApngPlayer

logger = logging.getLogger(__name__)


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
        if self._filtered_assets[index].metadata is not None:
            name = self._filtered_assets[index].metadata.get('name', '')
            if isinstance(name, str) and name:
                return name
        return self._filtered_assets[index].name

    def info_at(self, index: int) -> AssetInfo:
        return self._filtered_assets[index]

    def set_assets(self, asset_list: List[AssetInfo]) -> None:
        self._all_assets = asset_list
        self.apply_filters()

    def apply_filters(self):
        try:
            list1 = self._apply_category_filter(self._all_assets)
            list2 = self._apply_include_filter(list1)
            list3 = self._apply_exclude_filter(list2)
            self._filtered_assets = list3
            self.data_updated.emit()
        except Exception as e:
            logger.error("[搜索诊断] apply_filters 异常: %s, include=%r, exclude=%r, category=%r",
                         e, self.include_filter, self.exclude_filter, self.category_filter, exc_info=True)
            self._filtered_assets = self._all_assets
            self.data_updated.emit()

    def get_all_assets(self) -> List[AssetInfo]:
        return self._all_assets
    
    def notify_item_updated(self, index: int) -> None:
        self.item_updated.emit(index)
    
    def _apply_category_filter(self, input: List[AssetInfo]):
        if self.category_filter == "":
            return input

        result: List[AssetInfo] = []
        for asset in input:
            if asset.pak_id != "":
                if self.category_filter == asset.pak_id:
                    result.append(asset)
                    continue
            if asset.metadata is not None:
                category_path = asset.metadata.get('categoryPath', '')
                if isinstance(category_path, str) and category_path.startswith(self.category_filter):
                    result.append(asset)
            else:
                if self.category_filter == "/other":
                    result.append(asset)
        return result

    def _matches_filter(self, asset: AssetInfo, keyword: str) -> bool:
        if keyword in asset.name.lower():
            return True
        if asset.metadata is None:
            return False
        english_name = asset.metadata.get('englishName', '')
        name = asset.metadata.get('name', '')
        if isinstance(english_name, str) and keyword in english_name.lower():
            return True
        if isinstance(name, str) and keyword in name:
            return True
        return False

    def _apply_include_filter(self, input: List[AssetInfo]):
        if not self.include_filter:
            return input
        keyword = self.include_filter.lower()
        return [a for a in input if self._matches_filter(a, keyword)]

    def _apply_exclude_filter(self, input: List[AssetInfo]):
        if not self.exclude_filter:
            return input
        keyword = self.exclude_filter.lower()
        return [a for a in input if not self._matches_filter(a, keyword)]
