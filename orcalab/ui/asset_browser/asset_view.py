from typing import override
from PySide6 import QtCore, QtWidgets, QtGui


from orcalab.ui.asset_browser.thumbnail_view import ThumbnailView
from orcalab.ui.asset_browser.asset_model import AssetModel


class AssetView(ThumbnailView):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

    @override
    def _drag_started(self):

        # print("Drag started.")

        model = self._model
        assert isinstance(model, AssetModel)

        item = self._left_click_item
        assert item is not None

        info = model.info_at(item.index)

        asset_name = info.path
        mime_data = QtCore.QMimeData()
        asset_mime = "application/x-orca-asset"
        mime_data.setData(asset_mime, asset_name.encode("utf-8"))
        drag = QtGui.QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec(QtCore.Qt.CopyAction)

        self._drag_ended()
