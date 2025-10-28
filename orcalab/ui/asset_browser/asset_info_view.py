from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.ui.asset_browser.asset_info import AssetInfo


class AssetInfoView(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)


    def set_asset_info(self, asset_info: AssetInfo):
        """设置资产信息以显示"""
        pass