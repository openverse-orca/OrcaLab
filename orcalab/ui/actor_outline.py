import asyncio
from typing import Tuple, override
from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.actor import BaseActor, GroupActor, AssetActor
from orcalab.actor_util import make_unique_name
from orcalab.application_util import get_local_scene
from orcalab.entity_info import EntityInfo
from orcalab.local_scene import LocalScene
from orcalab.path import Path
from orcalab.pyside_util import connect
from orcalab.scene_edit_bus import (
    SceneEditRequestBus,
    SceneEditNotification,
    SceneEditNotificationBus,
)

from orcalab.ui.actor_outline_model import ActorOutlineModel
from orcalab.ui.rename_dialog import RenameDialog
from orcalab.ui.icon_util import make_icon

import logging

logger = logging.getLogger(__name__)

OUTLINE_BUTTON_GAP = 2


def _visibility_lock_button_rects(
    row_rect: QtCore.QRect,
) -> Tuple[QtCore.QRect, QtCore.QRect]:
    h = row_rect.height()
    y = row_rect.top() + (row_rect.height() - h) // 2
    r = row_rect.right()

    lock_rect = QtCore.QRect(r - h, y, h, h)
    eye_rect = QtCore.QRect(r - 2 * h - OUTLINE_BUTTON_GAP, y, h, h)

    return eye_rect, lock_rect


class ActorOutlineDelegate(QtWidgets.QStyledItemDelegate):

    def __init__(self, /, parent=...):
        super().__init__(parent)
        self._eye_visible_icon: QtGui.QIcon | None = None
        self._eye_hidden_icon: QtGui.QIcon | None = None
        self._lock_locked_icon: QtGui.QIcon | None = None
        self._lock_unlocked_icon: QtGui.QIcon | None = None

    def _ensure_icons(self, color: QtGui.QColor):
        if self._eye_visible_icon is None:
            self._eye_visible_icon = make_icon(":/icons/eye-open.svg", color)
            self._eye_hidden_icon = make_icon(":/icons/eye-close.svg", color)
            self._lock_locked_icon = make_icon(":/icons/lock-close-filled.svg", color)
            self._lock_unlocked_icon = make_icon(":/icons/lock-open.svg", color)

    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionViewItem,
        index: QtCore.QModelIndex,
    ):
        if not index.isValid():
            super().paint(painter, option, index)
            return

        node = index.internalPointer()
        if isinstance(node, EntityInfo):
            text_option = QtWidgets.QStyleOptionViewItem(option)
            font = text_option.font
            font.setItalic(True)
            text_option.font = font
            text_rect = QtCore.QRect(option.rect)
            text_rect.setRight(text_rect.right() - 4)
            text_option.rect = text_rect
            super().paint(painter, text_option, index)
            return

        actor = node
        if not isinstance(actor, BaseActor):
            super().paint(painter, option, index)
            return

        color = option.palette.color(
            QtGui.QPalette.ColorGroup.Active,
            QtGui.QPalette.ColorRole.Text,
        )
        self._ensure_icons(color)
        eye_rect, lock_rect = _visibility_lock_button_rects(option.rect)
        text_rect = QtCore.QRect(option.rect)
        text_rect.setRight(eye_rect.left() - OUTLINE_BUTTON_GAP)
        h = option.rect.height()
        text_option = QtWidgets.QStyleOptionViewItem(option)
        text_option.rect = text_rect
        super().paint(painter, text_option, index)
        eye_icon = self._eye_visible_icon if actor.is_visible else self._eye_hidden_icon
        eye_pixmap = eye_icon.pixmap(QtCore.QSize(h, h))
        painter.drawPixmap(eye_rect, eye_pixmap)
        lock_icon = (
            self._lock_locked_icon if actor.is_locked else self._lock_unlocked_icon
        )
        lock_pixmap = lock_icon.pixmap(QtCore.QSize(h, h))
        painter.drawPixmap(lock_rect, lock_pixmap)


class ActorOutline(QtWidgets.QTreeView, SceneEditNotification):

    def __init__(self):
        super().__init__()
        self.setHeaderHidden(True)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.setItemDelegate(ActorOutlineDelegate(self))

        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(QtCore.Qt.DropAction.CopyAction)

        self.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )

        self._current_index = QtCore.QModelIndex()
        self._current_actor: BaseActor | None = None

        self._brach_areas: dict[QtCore.QModelIndex, QtCore.QRect] = {}
        self._left_mouse_pressed = False
        self._left_mouse_pressed_position: QtCore.QPointF | None = None

        self.reparent_mime = "application/x-orca-actor-reparent"

        self._temp_expaned_actor_paths = []

        self._fetched_entity_actors: set[Path] = set()

    def connect_bus(self):
        SceneEditNotificationBus.connect(self)

    def disconnect_bus(self):
        SceneEditNotificationBus.disconnect(self)

    def set_actor_model(self, model: ActorOutlineModel):
        self.setModel(model)
        connect(model.modelAboutToBeReset, self._before_reset_model)
        connect(model.modelReset, self._after_reset_model)
        self.expanded.connect(self._on_node_expanded)

    def actor_model(self) -> ActorOutlineModel:
        model = self.model()
        if not isinstance(model, ActorOutlineModel):
            raise Exception("Invalid actor model.")
        return model

    @override
    async def on_selection_changed(self, old_selection, new_selection, source=""):
        if source == "actor_outline":
            return

        actors = []

        for actor_path in new_selection:
            local_scene = get_local_scene()
            actor = local_scene.find_actor_by_path(actor_path)
            assert actor is not None
            actors.append(actor)

        self.set_actor_selection(actors)

    @override
    async def on_active_entity_changed(
        self,
        old_active_entity: tuple | None,
        new_active_entity: tuple | None,
        source: str = "",
    ) -> None:
        if source == "actor_outline":
            return

        if new_active_entity is None:
            selection_model = self.selectionModel()
            node = None
            current = selection_model.currentIndex()
            if current.isValid():
                node = current.internalPointer()
            if isinstance(node, EntityInfo):
                selection_model.clearSelection()
            return

        actor_path, entity_id = new_active_entity
        model = self.actor_model()
        local_scene = model.local_scene

        actor = local_scene.find_actor_by_path(actor_path)
        if actor is None:
            return

        entity_info = local_scene.find_entity_info_by_id(actor_path, entity_id)
        if entity_info is None:
            return

        entity_index = model.get_index_from_entity_info(actor_path, entity_info)
        if not entity_index.isValid():
            return

        self._select_entity_index(entity_index)

    def _select_entity_index(self, entity_index: QtCore.QModelIndex):
        parent_index = entity_index.parent()
        while parent_index.isValid():
            if not self.isExpanded(parent_index):
                self.expand(parent_index)
            parent_index = parent_index.parent()

        self.scrollTo(entity_index)

        selection_model = self.selectionModel()
        selection_model.clearSelection()

        flags = (
            QtCore.QItemSelectionModel.SelectionFlag.Select
            | QtCore.QItemSelectionModel.SelectionFlag.Rows
        )
        selection_model.select(entity_index, flags)

    def set_actor_selection(self, actors: list[BaseActor]):
        selection_model = self.selectionModel()
        selection_model.clearSelection()

        model = self.actor_model()
        for actor in actors:
            index = model.get_index_from_actor(actor)
            if not index.isValid():
                raise Exception("Invalid actor.")

            flags = (
                QtCore.QItemSelectionModel.SelectionFlag.Select
                | QtCore.QItemSelectionModel.SelectionFlag.Rows
            )
            selection_model.select(index, flags)
            self.scrollTo(index)

    def _on_node_expanded(self, index: QtCore.QModelIndex):
        if not index.isValid():
            return

        node = index.internalPointer()
        if not isinstance(node, AssetActor):
            return

        actor_path = self.actor_model().local_scene.get_actor_path(node)
        if actor_path is None:
            return

        if actor_path in self._fetched_entity_actors:
            return

        self._fetched_entity_actors.add(actor_path)

        async def _fetch():
            await SceneEditRequestBus().fetch_entity_hierarchy(
                actor_path, source="actor_outline"
            )

        asyncio.create_task(_fetch())

    def _recursive_expand(self, index: QtCore.QModelIndex, expanded: bool):
        if not index.isValid():
            return

        self.setExpanded(index, expanded)

        model = self.actor_model()
        row_count = model.rowCount(index)
        for i in range(row_count):
            child = model.index(i, 0, index)
            self._recursive_expand(child, expanded)

    def _recursive_expand_action(self, expanded: bool):
        index = self._current_index
        if not index.isValid():
            return
        self._recursive_expand(index, expanded)

    @QtCore.Slot()
    def show_context_menu(self, position):
        self._current_index = self.indexAt(position)

        actor_outline_model = self.actor_model()
        local_scene: LocalScene = actor_outline_model.local_scene

        is_root = False
        current_node = None
        if self._current_index.isValid():
            current_node = self._current_index.internalPointer()

        is_entity_node = isinstance(current_node, EntityInfo)

        if current_node is None:
            current_actor = local_scene.root_actor
            is_root = True
        elif isinstance(current_node, BaseActor):
            current_actor = current_node
        elif isinstance(current_node, EntityInfo):
            current_actor = actor_outline_model.get_actor(self._current_index)
        else:
            current_actor = local_scene.root_actor
            is_root = True

        self._current_actor = current_actor
        self._current_actor_path = local_scene.get_actor_path(self._current_actor)

        menu = QtWidgets.QMenu()

        if is_entity_node:
            action_expand = QtGui.QAction("递归展开")
            connect(action_expand.triggered, lambda: self._recursive_expand_action(True))
            menu.addAction(action_expand)

            action_collapse = QtGui.QAction("递归折叠")
            connect(action_collapse.triggered, lambda: self._recursive_expand_action(False))
            menu.addAction(action_collapse)
        else:
            action_add_group = QtGui.QAction("Add Group")
            connect(action_add_group.triggered, self._add_group)
            menu.addAction(action_add_group)

            if self._current_index.isValid():
                menu.addSeparator()

                action_delete = QtGui.QAction("Delete")
                connect(action_delete.triggered, self._delete_actor)
                action_delete.setEnabled(not is_root)
                menu.addAction(action_delete)

                action_rename = QtGui.QAction("Rename")
                connect(action_rename.triggered, self._open_rename_dialog)
                action_rename.setEnabled(not is_root)
                menu.addAction(action_rename)

            menu.addSeparator()

            action_expand = QtGui.QAction("递归展开")
            connect(action_expand.triggered, lambda: self._recursive_expand_action(True))
            menu.addAction(action_expand)

            action_collapse = QtGui.QAction("递归折叠")
            connect(action_collapse.triggered, lambda: self._recursive_expand_action(False))
            menu.addAction(action_collapse)

        menu.exec(self.mapToGlobal(position))

    async def _add_group(self):
        parent_actor = self._current_actor
        parent_actor_path = self._current_actor_path

        assert parent_actor is not None
        assert parent_actor_path is not None

        if not isinstance(parent_actor, GroupActor):
            parent_actor = parent_actor.parent
            parent_actor_path = parent_actor_path.parent()

        assert isinstance(parent_actor, GroupActor)

        new_group_name = make_unique_name("group", parent_actor)
        actor = GroupActor(name=new_group_name)

        await SceneEditRequestBus().add_actor(
            actor, parent_actor, undo=True, source="actor_outline"
        )

    async def _delete_actor(self):
        if self._current_actor is None:
            return

        selection = self._selected_actor_paths()
        if self._current_actor_path in selection:
            bus = SceneEditRequestBus()
            await bus.delete_actors(selection)
        else:
            await SceneEditRequestBus().delete_actor(
                self._current_actor, undo=True, source="actor_outline"
            )

    def _open_rename_dialog(self):

        local_scene = get_local_scene()
        assert self._current_actor_path is not None
        assert self._current_actor is not None

        def can_rename_actor(actor_path: Path, name: str):
            return local_scene.can_rename_actor(actor_path, name)

        dialog = RenameDialog(self._current_actor_path, can_rename_actor, self)

        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            assert dialog.new_name is not None
            asyncio.create_task(
                SceneEditRequestBus().rename_actor(
                    self._current_actor,
                    dialog.new_name,
                    undo=True,
                    source="actor_outline",
                )
            )

    def _get_node_at_pos(self, pos: QtCore.QPoint):
        index = self.indexAt(pos)
        if not index.isValid():
            return None, None, None
        node = index.internalPointer()
        if isinstance(node, BaseActor):
            actor_outline_model = self.actor_model()
            actor, actor_path = actor_outline_model.local_scene.get_actor_and_path(node)
            return node, actor_path, False
        elif isinstance(node, EntityInfo):
            actor_outline_model = self.actor_model()
            actor_path = actor_outline_model._find_actor_path_for_entity_index(index)
            return node, actor_path, True
        return None, None, None

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._left_mouse_pressed = True
            self._left_mouse_pressed_position = event.position()
            node, actor_path, is_entity = self._get_node_at_pos(event.position().toPoint())
            if isinstance(node, BaseActor):
                self._current_actor = node
                self._current_actor_path = actor_path

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            if not self._left_mouse_pressed:
                return

            self._left_mouse_pressed = False

            pos = event.position().toPoint()
            index = self.indexAt(pos)

            if index.isValid():
                node = index.internalPointer()

                if isinstance(node, BaseActor):
                    row_rect = self.visualRect(index)
                    eye_rect, lock_rect = _visibility_lock_button_rects(row_rect)
                    if eye_rect.contains(pos):
                        self._toggle_actor_visibile(index)
                        return
                    if lock_rect.contains(pos):
                        self._toggle_actor_locked(index)
                        return

            node, actor_path, is_entity = self._get_node_at_pos(pos)

            if is_entity and isinstance(node, EntityInfo):
                if not actor_path:
                    return

                branch_area = self._brach_areas.get(index)
                if branch_area and branch_area.contains(pos):
                    self.setExpanded(index, not self.isExpanded(index))
                    return

                async def _do_select_entity():
                    await SceneEditRequestBus().set_active_entity(
                        actor_path, node.entity_id, source="actor_outline"
                    )

                self._select_entity_index(index)
                asyncio.create_task(_do_select_entity())
                return

            if node is None or actor_path is None:
                return

            if not actor_path.is_root():
                branch_area = self._brach_areas.get(index)
                if branch_area and branch_area.contains(pos):
                    self.setExpanded(index, not self.isExpanded(index))
                    return

            async def _do_set_selection(
                actor_paths: list[Path], active_path: Path | None
            ):
                _actors, _ = get_local_scene().normalize_actors(actor_paths)
                self.set_actor_selection(_actors)

                bus = SceneEditRequestBus()
                await bus.set_selection_and_active_actor(actor_paths, active_path, source="actor_outline")

            def do_set_selection(actor_paths: list[Path], active_path: Path | None):
                asyncio.create_task(_do_set_selection(actor_paths, active_path))

            shift = event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier
            if shift:
                if actor_path == Path.root_path():
                    pass
                else:
                    actor_paths = self._selected_actor_paths()
                    if actor_path in actor_paths:
                        if actor_path == self.actor_model().local_scene.active_actor:
                            actor_paths.remove(actor_path)
                    else:
                        actor_paths.append(actor_path)
                    do_set_selection(actor_paths, actor_path)
            else:
                if actor_path == Path.root_path():
                    do_set_selection([], None)
                else:
                    do_set_selection([actor_path], actor_path)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        if not self._left_mouse_pressed or self._left_mouse_pressed_position is None:
            return

        if self._current_actor_path is None or self._current_actor_path.is_root():
            return

        actor_paths = self._selected_actor_paths()
        if actor_paths:
            if self._current_actor_path in actor_paths:
                parent = self._current_actor_path.parent()
                for actor_path in actor_paths:
                    if actor_path.parent() != parent:
                        return

        distance = (
            event.position() - self._left_mouse_pressed_position
        ).manhattanLength()
        if distance < QtWidgets.QApplication.startDragDistance():
            return

        self._left_mouse_pressed = False

        if self._current_actor_path in actor_paths:
            data_string = ";".join(str(p) for p in actor_paths)
        else:
            data_string = self._current_actor_path.string()
        data = data_string.encode("utf-8")

        mime_data = QtCore.QMimeData()
        mime_data.setData("application/x-orca-actor-reparent", data)

        self.startDrag(QtCore.Qt.DropAction.CopyAction)
        drag = QtGui.QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec(QtCore.Qt.DropAction.CopyAction)

        self._current_actor_path = None
        self._current_actor = None

    def _toggle_actor_visibile(self, index: QtCore.QModelIndex):
        actor_outline_model = self.actor_model()
        actor = actor_outline_model.get_actor(index)
        if actor is None:
            return
        local_scene: LocalScene = actor_outline_model.local_scene
        actor_path = local_scene.get_actor_path(actor)
        if actor_path is None:
            return

        actor.is_visible = not actor.is_visible
        if actor.is_parent_visible:
            asyncio.create_task(
                SceneEditRequestBus().set_actor_visible(
                    actor_path, actor.is_visible, False, source="actor_outline"
                )
            )
        self.viewport().update(self.visualRect(index))

    def _toggle_actor_locked(self, index: QtCore.QModelIndex):
        actor_outline_model = self.actor_model()
        actor = actor_outline_model.get_actor(index)
        if actor is None:
            return
        local_scene: LocalScene = actor_outline_model.local_scene
        actor_path = local_scene.get_actor_path(actor)
        if actor_path is None:
            return

        actor.is_locked = not actor.is_locked
        asyncio.create_task(
            SceneEditRequestBus().set_actor_locked(
                actor_path, actor.is_locked, False, source="actor_outline"
            )
        )
        self.viewport().update(self.visualRect(index))

    def _selected_actor_paths(self) -> list[Path]:
        indexes = self.selectedIndexes()
        if not indexes:
            return []

        actor_paths = []
        actor_outline_model = self.actor_model()
        local_scene = actor_outline_model.local_scene

        for index in indexes:
            node = index.internalPointer()
            if isinstance(node, BaseActor):
                actor_path = local_scene.get_actor_path(node)
                if actor_path is not None:
                    actor_paths.append(actor_path)

        return actor_paths

    def paintEvent(self, event):
        self._brach_areas.clear()
        return super().paintEvent(event)

    def drawBranches(self, painter, rect, index):
        node = index.internalPointer()
        if isinstance(node, (BaseActor, EntityInfo)):
            self._brach_areas[index] = rect

        return super().drawBranches(painter, rect, index)

    def _before_reset_model(self):
        self._temp_expaned_actor_paths.clear()
        self._fetched_entity_actors.clear()

        model = self.actor_model()
        local_scene = model.local_scene

        def collect_expaneded_actors(parent: QtCore.QModelIndex):
            for i in range(model.rowCount(parent)):
                child = model.index(i, 0, parent)
                if self.isExpanded(child):
                    node = child.internalPointer()
                    if isinstance(node, BaseActor):
                        actor_path = local_scene.get_actor_path(node)
                        if actor_path is not None:
                            self._temp_expaned_actor_paths.append(actor_path)
                    collect_expaneded_actors(child)

        collect_expaneded_actors(QtCore.QModelIndex())

    def _after_reset_model(self):

        model = self.actor_model()
        local_scene = model.local_scene

        actors, actor_paths = local_scene.normalize_actors(local_scene.selection)
        self.set_actor_selection(actors)

        for actor_path in self._temp_expaned_actor_paths:
            actor = local_scene.find_actor_by_path(actor_path)
            if actor is not None:
                index = model.get_index_from_actor(actor)
                if index.isValid():
                    QtCore.QTimer.singleShot(
                        10, lambda index=index: self.setExpanded(index, True)
                    )

        self._temp_expaned_actor_paths.clear()


if __name__ == "__main__":
    import sys
    from actor_outline_model import ActorOutlineModel
    from orcalab.actor import GroupActor, AssetActor

    app = QtWidgets.QApplication(sys.argv)

    local_scene = LocalScene()
    local_scene.add_actor(GroupActor("g1"), Path("/"))
    local_scene.add_actor(GroupActor("g2"), Path("/"))
    local_scene.add_actor(GroupActor("g3"), Path("/"))
    local_scene.add_actor(GroupActor("g4"), Path("/g2"))
    local_scene.add_actor(AssetActor("a1", "spw_name"), Path("/g3"))

    model = ActorOutlineModel(local_scene)
    model.set_root_group(local_scene.root_actor)

    def on_request_reparent(actor_path: Path, new_parent_path: Path, row: int):
        if row < 0:
            logger.debug(f"reparent {actor_path} to end of {new_parent_path}")
        else:
            logger.debug(f"reparent {actor_path} to row {row} of {new_parent_path}")

    model.request_reparent.connect(on_request_reparent)

    actor_outline = ActorOutline()
    actor_outline.set_actor_model(model)
    actor_outline.show()

    app.exec()
