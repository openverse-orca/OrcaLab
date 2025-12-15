from PySide6 import QtCore, QtWidgets, QtGui
from typing import Any, List

from orcalab.ui.camera.camera_brief import CameraBrief


class CameraBriefModel(QtCore.QAbstractListModel):
    def __init__(self):
        super().__init__()
        self._cameras: List[CameraBrief] = []

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        return len(self._cameras)

    def data(self, index: QtCore.QModelIndex, role: QtCore.Qt.ItemDataRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._cameras)):
            return None

        camera = self._cameras[index.row()]

        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            return camera.name
        return None

    def set_cameras(self, camera_list: List[CameraBrief]):
        self.beginResetModel()
        self._cameras = camera_list
        self.endResetModel()

    def get_camera_brief(self, row: int) -> CameraBrief:
        if 0 <= row < len(self._cameras):
            return self._cameras[row]

        raise IndexError("CameraBriefModel: Row index out of range")
