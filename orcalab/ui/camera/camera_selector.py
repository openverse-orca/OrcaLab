import asyncio
from tkinter import font
from PySide6 import QtCore, QtWidgets, QtGui

from typing import Any, List, override

from orcalab.ui.camera.camera_brief import CameraBrief
from orcalab.ui.camera.camera_brief_model import CameraBriefModel
from orcalab.ui.camera.camera_bus import (
    CameraNotification,
    CameraNotificationBus,
    CameraRequestBus,
)
from orcalab.ui.theme_service import ThemeService


class _CameraSelectorDelegate(QtWidgets.QStyledItemDelegate):

    def __init__(self, /, parent=...):
        super().__init__(parent)

        theme = ThemeService()
        self.source_color = theme.get_color("text_disable")

    @override
    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionViewItem,
        index: QtCore.QModelIndex | QtCore.QPersistentModelIndex,
    ) -> None:
        super().paint(painter, option, index)

        # Draw source on the right side.

        model = index.model()
        assert isinstance(model, CameraBriefModel)
        camera_brief = model.get_camera_brief(index.row())

        camera_brief.source

        rect: QtCore.QRect = option.rect
        rect.setRight(rect.right() - 5)

        font = painter.font()
        font.setItalic(True)

        align = (
            QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignRight
        )

        painter.save()
        painter.setPen(self.source_color)
        painter.setFont(font)
        painter.drawText(rect, align, camera_brief.source)
        painter.restore()


class CameraSelector(QtWidgets.QListView, CameraNotification):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)

        self._model = CameraBriefModel()
        self.setModel(self._model)
        self.setItemDelegate(_CameraSelectorDelegate(self))

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
            
        self.selectionModel().clearSelection()

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
