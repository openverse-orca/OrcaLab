import asyncio
from tkinter import font
import logging
from collections import defaultdict
from PySide6 import QtCore, QtWidgets, QtGui

from typing import Any, List, override

from orcalab.path import Path
from orcalab.scene_edit_bus import SceneEditNotification, SceneEditNotificationBus
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

    def _is_group_row(self, model: QtGui.QStandardItemModel, index: QtCore.QModelIndex) -> bool:
        if not index.isValid():
            return False
        item = model.itemFromIndex(index)
        if not item:
            return False
        return item.data(QtCore.Qt.ItemDataRole.UserRole) is None

    @override
    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionViewItem,
        index: QtCore.QModelIndex | QtCore.QPersistentModelIndex,
    ) -> None:
        model = index.model()
        if not isinstance(model, QtGui.QStandardItemModel):
            super().paint(painter, option, index)
            return

        is_group = self._is_group_row(model, index)
        if is_group:
            option_copy = QtWidgets.QStyleOptionViewItem(option)
            option_copy.state &= ~(
                QtWidgets.QStyle.StateFlag.State_Selected
                | QtWidgets.QStyle.StateFlag.State_HasFocus
            )
            font = painter.font()
            font.setBold(True)
            painter.save()
            painter.setFont(font)
            super().paint(painter, option_copy, index)
            painter.restore()
            return

        super().paint(painter, option, index)

        # 相机行：右侧绘制 source（辅助信息）
        item = model.itemFromIndex(index)
        camera_brief = item.data(QtCore.Qt.ItemDataRole.UserRole) if item else None
        if not isinstance(camera_brief, CameraBrief) or not camera_brief.source:
            return

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


class CameraSelector(QtWidgets.QTreeView, CameraNotification, SceneEditNotification):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setHeaderHidden(True)
        self.setRootIsDecorated(True)

        self._model = QtGui.QStandardItemModel()
        self.setModel(self._model)
        self.setItemDelegate(_CameraSelectorDelegate(self))

        self.selectionModel().selectionChanged.connect(self._on_selection_changed)

        self._block = False
        self._last_viewport_camera_index = -1
        # 本地已更新的相机 actor_path（如 reparent 后），避免被后端旧列表覆盖
        self._displayed_briefs: dict[int, CameraBrief] = {}

    def connect_bus(self):
        CameraNotificationBus.connect(self)
        SceneEditNotificationBus.connect(self)

    def disconnect_bus(self):
        CameraNotificationBus.disconnect(self)
        SceneEditNotificationBus.disconnect(self)

    def set_cameras(
        self, camera_list: List[CameraBrief], viewport_camera_index: int
    ) -> None:
        # 若本地有更新过的 actor_path（如 reparent 后），优先使用，避免被后端旧列表覆盖
        for cam in camera_list:
            if cam.index in self._displayed_briefs:
                cam.actor_path = self._displayed_briefs[cam.index].actor_path
        # 按 actor_path 分组；actor_path 为空时按 source 分组
        groups: dict[str, List[CameraBrief]] = defaultdict(list)
        for cam in camera_list:
            key = (cam.actor_path or "").strip()
            if not key:
                key = (cam.source or "").strip()
            groups[key].append(cam)

        self._model.removeRows(0, self._model.rowCount())
        for group_name in sorted(groups.keys(), key=lambda x: (x, x)):
            display_name = group_name.lstrip("/") or group_name
            group_item = QtGui.QStandardItem(display_name)
            group_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
            group_item.setSelectable(False)
            for brief in groups[group_name]:
                child = QtGui.QStandardItem(brief.name)
                child.setData(brief, QtCore.Qt.ItemDataRole.UserRole)
                child.setFlags(
                    QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
                )
                group_item.appendRow(child)
            self._model.appendRow(group_item)

        self.expandAll()
        self._last_viewport_camera_index = viewport_camera_index
        self._displayed_briefs = {b.index: b for b in camera_list}
        self._set_selected_camera(viewport_camera_index)

    def _collect_all_camera_briefs(self) -> List[CameraBrief]:
        briefs: List[CameraBrief] = []
        for row in range(self._model.rowCount()):
            group_item = self._model.item(row)
            if not group_item:
                continue
            for r in range(group_item.rowCount()):
                child = group_item.child(r)
                if not child:
                    continue
                brief = child.data(QtCore.Qt.ItemDataRole.UserRole)
                if isinstance(brief, CameraBrief):
                    briefs.append(brief)
        return briefs

    @override
    async def on_actor_reparented(
        self,
        actor_path: Path,
        new_parent_path: Path,
        row: int,
        source: str,
    ) -> None:
        briefs = self._collect_all_camera_briefs()
        if not briefs:
            return
        old_prefix = actor_path.string()
        new_actor_path = new_parent_path.append(actor_path.name())
        new_prefix = new_actor_path.string()
        for b in briefs:
            ap = (b.actor_path or "").strip()
            if ap == old_prefix:
                b.actor_path = new_prefix
            elif ap.startswith(old_prefix + "/"):
                b.actor_path = new_prefix + ap[len(old_prefix) :]
        try:
            viewport_index = self._get_selected_camera_index()
        except ValueError:
            viewport_index = self._last_viewport_camera_index
        self.set_cameras(briefs, viewport_index)

    def _get_selected_camera_index(self) -> int:
        indexes = self.selectionModel().selectedIndexes()
        if not indexes: # TODO: 这里不要使用异常
            raise ValueError("No camera is currently selected")
        idx = indexes[0]
        item = self._model.itemFromIndex(idx)
        if not item:
            raise ValueError("No camera is currently selected")
        brief = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(brief, CameraBrief):
            return brief.index
        raise ValueError("No camera is currently selected")

    def _set_selected_camera(self, camera_index: int) -> None:
        self._block = True

        for row in range(self._model.rowCount()):
            group_item = self._model.item(row)
            if not group_item:
                continue
            for r in range(group_item.rowCount()):
                child = group_item.child(r)
                if not child:
                    continue
                brief = child.data(QtCore.Qt.ItemDataRole.UserRole)
                if isinstance(brief, CameraBrief) and brief.index == camera_index:
                    group_index = self._model.index(row, 0)
                    child_index = self._model.index(r, 0, group_index)
                    self.selectionModel().select(
                        child_index,
                        QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect,
                    )
                    self._block = False
                    return
        self.selectionModel().clearSelection()

        self._block = False

    def _on_selection_changed(self, selected, deselected):
        if self._block:
            return
        try:
            camera_index = self._get_selected_camera_index()
        except ValueError:
            return
        asyncio.create_task(CameraRequestBus().set_viewport_camera(camera_index))

    @override
    def on_viewport_camera_changed(self, camera_index: int) -> None:
        self._last_viewport_camera_index = camera_index
        try:
            if self._get_selected_camera_index() == camera_index:
                return
        except ValueError:
            pass
        self._set_selected_camera(camera_index)
