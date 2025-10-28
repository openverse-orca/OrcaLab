from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.ui.asset_browser.asset_info import AssetInfo


class AssetInfoView(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._name_label = QtWidgets.QLabel()
        self._path_label = QtWidgets.QLabel()

        self._layout.addWidget(self._name_label)
        self._layout.addWidget(self._path_label)

    def set_asset_info(self, asset_info: AssetInfo | None):
        if asset_info is not None:
            self._name_label.setText(f"Name: {asset_info.name}")
            self._path_label.setText(f"Path: {asset_info.path}")
        else:
            self._name_label.setText("")
            self._path_label.setText("")
