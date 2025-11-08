from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.ui.asset_browser.asset_info import AssetInfo
from orcalab.metadata_service_bus import AssetMetadata


class AssetInfoView(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._name_label = QtWidgets.QLabel()
        self._path_label = QtWidgets.QLabel()
        self._metadata_label = QtWidgets.QLabel()

        self._name_label.setWordWrap(True)
        self._path_label.setWordWrap(True)
        self._metadata_label.setWordWrap(True)

        self._layout.addWidget(self._name_label)
        self._layout.addWidget(self._path_label)
        self._layout.addWidget(self._metadata_label)
        self._layout.addStretch(1)

    def set_asset_info(self, asset_info: AssetInfo | None):
        if asset_info is not None:
            self._name_label.setText(f"Name: {asset_info.name}")
            self._path_label.setText(f"Path: {asset_info.path}")
            self.set_metadata_info(asset_info.metadata)
        else:
            self._name_label.setText("")
            self._path_label.setText("")
            self._metadata_label.setText("")


    def set_metadata_info(self, metadata_info: AssetMetadata | None):
        if metadata_info is not None:
            metadata_str = (f"ID: {metadata_info['id']}\n" + 
            f"Parent Package ID: {metadata_info['parentPackageId']}\n" + 
            f"Category: {metadata_info['category']}\n" + 
            f"Type: {metadata_info['type']}\n" + 
            f"Author: {metadata_info['author']}")
            self._metadata_label.setText(metadata_str)
        else:
            self._metadata_label.setText("No metadata available")