import asyncio
from PySide6 import QtCore, QtWidgets, QtGui

from typing import Any, List, override

from orcalab.ui.camera.camera_brief import CameraBrief
from orcalab.ui.camera.camera_brief_model import CameraBriefModel
from orcalab.ui.camera.camera_bus import (
    CameraNotification,
    CameraNotificationBus,
    CameraRequestBus,
)


class CameraSelector(QtWidgets.QListView, CameraNotification):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)

        self._model = CameraBriefModel()
        self.setModel(self._model)

        self.selectionModel().selectionChanged.connect(self._on_selection_changed)

        self._block = False

    def connect_buses(self):
        CameraNotificationBus.connect(self)

    def disconnect_buses(self):
        CameraNotificationBus.disconnect(self)

    def set_cameras(
        self, camera_list: List[CameraBrief], viewport_camera_index: int
    ) -> None:
        self._model.set_cameras(camera_list)
        self._set_selected_camera(viewport_camera_index)

    def _get_selected_camera_index(self) -> int:
        rows = self.selectionModel().selectedRows()
        if rows:
            index = rows[0]
            camera_brief = self._model.get_camera_brief(index.row())
            return camera_brief.index

        raise ValueError("No camera is currently selected")

    def _set_selected_camera(self, camera_index: int) -> None:
        self._block = True

        for row in range(self._model.rowCount()):
            camera_brief = self._model.get_camera_brief(row)
            if camera_brief.index == camera_index:
                index = self._model.index(row)
                self.selectionModel().select(
                    index, QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect
                )
                self._block = False
                return

        self._block = False

    def _on_selection_changed(self, selected, deselected):
        if self._block:
            return

        camera_index = self._get_selected_camera_index()
        asyncio.create_task(CameraRequestBus().set_viewport_camera(camera_index))

    @override
    def on_viewport_camera_changed(self, camera_index: int) -> None:
        selected_camera_index = self._get_selected_camera_index()
        if selected_camera_index == camera_index:
            return

        self._set_selected_camera(camera_index)
