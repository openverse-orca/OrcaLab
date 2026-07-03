import asyncio
from typing import Any, Dict, List, Tuple
from typing_extensions import override
from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.actor import BaseActor, GroupActor, AssetActor
from orcalab.actor_util import make_unique_name
from orcalab.application_util import get_local_scene
from orcalab.entity_info import EntityInfo
from orcalab.entity_path import EntityPath, FullEntityPath
from orcalab.local_scene import LocalScene
from orcalab.path import Path
from orcalab.pyside_util import connect
from orcalab.scene_edit_bus import (
    SceneEditRequestBus,
    SceneEditNotification,
    SceneEditNotificationBus,
)

from orcalab.selection_data import SelectionData
from orcalab.ui.actor_outline_model import ActorOutlineModel
from orcalab.ui.collapsible.collapsible_section import SectionHeader
from orcalab.ui.fonts.font_service import FontService
from orcalab.ui.rename_dialog import RenameDialog
from orcalab.ui.icon_util import make_icon
from orcalab.ui.xml_viewer_dialog import XmlViewerDialog, _is_robot_actor

import logging

logger = logging.getLogger(__name__)

OUTLINE_BUTTON_GAP = 2


def _visibility_lock_button_rects(
    row_rect: QtCore.QRect,
) -> Tuple[QtCore.QRect, QtCore.QRect]:
    tail_size = max(12, row_rect.height() - 8)
    gap = OUTLINE_BUTTON_GAP
    y = row_rect.top() + (row_rect.height() - tail_size) // 2
    r = row_rect.x() + row_rect.width()

    lock_rect = QtCore.QRect(r - 4 - tail_size, y, tail_size, tail_size)
    eye_rect = QtCore.QRect(
        r - 4 - tail_size - gap - tail_size, y, tail_size, tail_size
    )

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
        index: QtCore.QModelIndex | QtCore.QPersistentModelIndex,
    ):
        if not index.isValid():
            super().paint(painter, option, index)
            return

        node = index.internalPointer()

        # PySide6's type hint for QStyleOptionViewItem is not great,
        # so we need to use Any to access the state, font, rect, and palette attributes.
        option_any: Any = option
        state: QtWidgets.QStyle.StateFlag = option_any.state
        font: QtGui.QFont = option_any.font
        rect: QtCore.QRect = option_any.rect
        palette: QtGui.QPalette = option_any.palette

        hovered = bool(state & QtWidgets.QStyle.StateFlag.State_MouseOver)
        selected = bool(state & QtWidgets.QStyle.StateFlag.State_Selected)

        tree_view = self.parent()
        assert isinstance(tree_view, QtWidgets.QTreeView)
        is_expanded = (
            tree_view.isExpanded(index)
            if isinstance(tree_view, QtWidgets.QTreeView)
            else True
        )

        if isinstance(node, EntityInfo):
            entity_info_font = FontService().apply_font_modifiers("entity_info", font)
            painter.setFont(entity_info_font)
            SectionHeader.paint_at(
                painter=painter,
                rect=rect,
                title=node.name,
                collapsed=not is_expanded,
                has_children=False,
                hovered=hovered,
                selected=selected,
                widget=tree_view,
                show_divider=False,
            )
            return

        actor = node
        if not isinstance(actor, BaseActor):
            super().paint(painter, option, index)
            return

        painter.setFont(font)
        model = index.model()
        has_children = model.hasChildren(index) if model else False

        color = palette.color(
            QtGui.QPalette.ColorGroup.Active,
            QtGui.QPalette.ColorRole.Text,
        )
        self._ensure_icons(color)
        eye_icon = self._eye_visible_icon if actor.is_visible else self._eye_hidden_icon
        lock_icon = (
            self._lock_locked_icon if actor.is_locked else self._lock_unlocked_icon
        )
        assert eye_icon is not None and lock_icon is not None

        SectionHeader.paint_at(
            painter=painter,
            rect=rect,
            title=actor.name,
            collapsed=not is_expanded,
            has_children=False,
            hovered=hovered,
            selected=selected,
            widget=tree_view,
            tail_items=[("eye", eye_icon), ("lock", lock_icon)],
            show_divider=False,
        )


class ActorOutline(QtWidgets.QTreeView, SceneEditNotification):

    def __init__(self):
        super().__init__()
        self.setHeaderHidden(True)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.setItemDelegate(ActorOutlineDelegate(self))

        self._fs = FontService()
        self._fs.bind_widget_font(self, "outline")

        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(QtCore.Qt.DropAction.CopyAction)

        self.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )

        self._current_index = QtCore.QModelIndex()
        self._current_actor: BaseActor | None = None
        self._current_actor_path: Path | None = None

        self._brach_areas: dict[QtCore.QModelIndex, QtCore.QRect] = {}
        self._left_mouse_pressed = False
        self._left_mouse_pressed_position: QtCore.QPointF | None = None

        self.reparent_mime = "application/x-orca-actor-reparent"

        self._temp_expaned_items: List[Path | FullEntityPath] = []

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

        self.set_selection(new_selection)

    @override
    async def on_actor_locked_changed(
        self, actor_path: Path, paths_to_update: list, locked: bool, source: str = ""
    ):
        if not locked:
            return

        local_scene = self.actor_model().local_scene
        selection = local_scene.selection()
        actors = selection.selected_actors
        active_actor_path = selection.active_actor_path
        active_entity_path = selection.active_entity_path

        if not actors and active_actor_path is None:
            return

        locked_set = set(paths_to_update)
        new_actors = []
        for p in actors:
            if p not in locked_set:
                new_actors.append(p)

        def need_update():
            if len(new_actors) != len(actors):
                return True
            if active_actor_path in locked_set:
                return True
            return False

        if not need_update():
            return

        if active_actor_path in locked_set:
            active_actor_path = None
            active_entity_path = EntityPath()

        new_selection = SelectionData(new_actors, active_actor_path, active_entity_path)
        self.set_selection(new_selection)
        await SceneEditRequestBus().set_selection(new_selection, source="actor_outline")

    def _select_active_entity(self, selection: SelectionData) -> bool:
        if selection.active_actor_path is None:
            if not selection.active_entity_path.empty():
                logger.error("Active entity is set but active actor is None.")
            return False

        model = self.actor_model()
        local_scene = model.local_scene

        actor = local_scene.find_actor_by_path(selection.active_actor_path)
        if not isinstance(actor, AssetActor):
            if not selection.active_entity_path.empty():
                logger.error(
                    "Active entity is set but active actor is not an AssetActor."
                )
            return False

        if selection.active_entity_path.empty():
            return False

        index = model.get_index_for_entity(actor, selection.active_entity_path)
        if not index.isValid():
            logger.error("Invalid index for active entity.")
            return False

        selection_model = self.selectionModel()
        selection_model.clearSelection()
        SelectionFlag = QtCore.QItemSelectionModel.SelectionFlag
        flags = SelectionFlag.Select | SelectionFlag.Rows
        selection_model.select(index, flags)

        self.scrollTo(index)
        return True

    def _select_actors(self, selection: SelectionData):
        selection_model = self.selectionModel()
        selection_model.clearSelection()

        model = self.actor_model()
        local_scene = model.local_scene

        actor_indices = []
        for actor_path in selection.selected_actors:
            actor = local_scene.find_actor_by_path(actor_path)
            if actor is None:
                logger.warning(f"Actor not found for path: {actor_path}")
                continue

            index = model.get_index_from_actor(actor)
            if not index.isValid():
                logger.warning(f"Invalid index for actor: {actor_path}")

            SelectionFlag = QtCore.QItemSelectionModel.SelectionFlag
            flags = SelectionFlag.Select | SelectionFlag.Rows
            selection_model.select(index, flags)
            actor_indices.append(index)

        if len(actor_indices) == 1:
            self.scrollTo(actor_indices[0])

    def set_selection(self, selection: SelectionData):
        """
        只考虑UI层的选中逻辑，不涉及数据层的选中状态管理。
        - Actor支持多选
        - Entity只支持单选
        - Actor和Entity不能同时选中
        - Entity优先于Actor
        """

        if self._select_active_entity(selection):
            return

        self._select_actors(selection)

    def _on_node_expanded(self, index: QtCore.QModelIndex):
        if not index.isValid():
            return

        node = index.internalPointer()
        if not isinstance(node, AssetActor):
            return

        actor_path = self.actor_model().local_scene.get_actor_path(node)
        if actor_path is None:
            return

        local_scene = self.actor_model().local_scene
        existing_root = local_scene.get_entity_root(actor_path)
        if existing_root is not None:
            return

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
        actor_outline_model = self.actor_model()
        local_scene = actor_outline_model.local_scene

        index = self.indexAt(position)
        self._current_index = index

        is_root = False
        is_entity = False

        if not index.isValid():
            self._current_actor = local_scene.root_actor
            self._current_actor_path = Path.root_path()
            is_root = True
        else:
            ptr = index.internalPointer()

            if isinstance(ptr, BaseActor):
                self._current_actor = ptr
                self._current_actor_path = local_scene.get_actor_path(
                    self._current_actor
                )
            elif isinstance(ptr, EntityInfo):
                self._current_actor = None
                self._current_actor_path = None
                is_entity = True
            else:
                logger.error(
                    "[Coding Error] Invalid node type in actor outline: {}".format(
                        type(ptr)
                    )
                )
                self._current_actor = None
                self._current_actor_path = None
                return

        menu = QtWidgets.QMenu()

        action_add_group = QtGui.QAction("添加组")
        connect(action_add_group.triggered, self._add_group)
        menu.addAction(action_add_group)

        if self._current_index.isValid() and not is_entity:
            menu.addSeparator()

            action_delete = QtGui.QAction("删除")
            connect(action_delete.triggered, self._delete_actor)
            action_delete.setEnabled(not is_root)
            menu.addAction(action_delete)

            action_rename = QtGui.QAction("重命名")
            connect(action_rename.triggered, self._open_rename_dialog)
            action_rename.setEnabled(not is_root)
            menu.addAction(action_rename)

        menu.addSeparator()

        action_expand = QtGui.QAction("递归展开")
        connect(action_expand.triggered, lambda: self._recursive_expand_action(True))
        action_expand.setEnabled(index.isValid())
        menu.addAction(action_expand)

        action_collapse = QtGui.QAction("递归折叠")
        connect(action_collapse.triggered, lambda: self._recursive_expand_action(False))
        action_collapse.setEnabled(index.isValid())
        menu.addAction(action_collapse)

        if (isinstance(self._current_actor, AssetActor) and _is_robot_actor(self._current_actor)):
            menu.addSeparator()
            action_view_xml = QtGui.QAction("查看 XML")
            connect(action_view_xml.triggered, self._show_xml_viewer)
            menu.addAction(action_view_xml)

        menu.exec(self.mapToGlobal(position))

    def _show_xml_viewer(self):
        dialog = XmlViewerDialog(self)
        dialog.setModal(True)
        dialog.show()
        if self._current_actor_path is not None:
            dialog.fetch_for_actor(self._current_actor_path)

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

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._left_mouse_pressed = True
            self._left_mouse_pressed_position = event.position()

            index = self.indexAt(event.position().toPoint())

            if index.isValid():
                ptr = index.internalPointer()
                if isinstance(ptr, BaseActor):
                    local_scene = self.actor_model().local_scene
                    actor, actor_path = local_scene.get_actor_and_path(ptr)
                    self._current_actor = actor
                    self._current_actor_path = actor_path

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            if not self._left_mouse_pressed:
                return

            self._left_mouse_pressed = False

            pos = event.position().toPoint()
            index = self.indexAt(pos)

            branch_area = self._brach_areas.get(index)
            if branch_area is not None and branch_area.contains(pos):
                self.setExpanded(index, not self.isExpanded(index))
                return

            if self._toggle_actor_state(pos, index):
                return

            selection = SelectionData()
            shift = QtCore.Qt.KeyboardModifier.ShiftModifier in event.modifiers()
            if self._update_selection_data(selection, index, shift):
                self.set_selection(selection)
                asyncio.create_task(
                    SceneEditRequestBus().set_selection(
                        selection, source="actor_outline"
                    )
                )

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

    def _toggle_actor_state(
        self, pos: QtCore.QPoint, index: QtCore.QModelIndex
    ) -> bool:
        if not index.isValid():
            return False

        ptr = index.internalPointer()
        if isinstance(ptr, BaseActor):
            row_rect = self.visualRect(index)
            eye_rect, lock_rect = _visibility_lock_button_rects(row_rect)
            if eye_rect.contains(pos):
                self._toggle_actor_visibile(index)
                return True
            if lock_rect.contains(pos):
                self._toggle_actor_locked(index)
                return True

        return False

    def _update_selection_data(
        self,
        selection: SelectionData,
        index: QtCore.QModelIndex,
        shift: bool,
    ) -> bool:
        if not index.isValid():
            if shift:
                # 按住shift点击空白区域没有任何效果
                return False

            # 点击空白区域，清空选中
            return True

        local_scene = self.actor_model().local_scene
        ptr = index.internalPointer()

        if isinstance(ptr, BaseActor):
            actor_path = local_scene.get_actor_path(ptr)
            if actor_path is None:
                logger.error("Actor path not found for actor: {}".format(ptr))
                return False

            if ptr.is_locked or ptr.is_parent_locked:
                # 点击锁定的actor没有任何效果
                return False

            selected = actor_path in local_scene.selected_actors
            active = actor_path == local_scene.active_actor_path

            if shift:
                # 按住shift点击一个actor
                selection.selected_actors = local_scene.selected_actors
                selection.active_actor_path = local_scene.active_actor_path

                if selected:
                    if active:
                        # 如果是active actor，取消选中，清空active actor
                        selection.selected_actors.remove(actor_path)
                        selection.active_actor_path = None
                    else:
                        # 如果不是active actor，设为active，选择保持选择不变
                        selection.active_actor_path = actor_path
                else:
                    # 如果未选中，则添加到选中列表中
                    selection.selected_actors.append(actor_path)
                    selection.active_actor_path = actor_path

                return True
            else:
                if not selected:
                    # 点击一个未选中的actor，选中并且设为active actor
                    selection.selected_actors = [actor_path]
                    selection.active_actor_path = actor_path
                    return True
                else:
                    # 点击一个已选中的actor, 没有任何效果
                    pass

        elif isinstance(ptr, EntityInfo):
            if shift:
                # 按住shift点击Entity没有任何效果
                return False

            asset_actor = local_scene.find_actor_by_entity_id(ptr.entity_id)
            if asset_actor is None:
                logger.error(
                    "Asset actor not found for entity: {}".format(ptr.entity_path)
                )
                return False

            if asset_actor.is_locked or asset_actor.is_parent_locked:
                # 点击锁定的actor下的entity没有任何效果
                return False

            actor_path = local_scene.get_actor_path(asset_actor)
            if actor_path is None:
                logger.error(
                    "Actor path not found for actor: {}".format(asset_actor.name)
                )
                return False

            selection.selected_actors = [actor_path]
            selection.active_actor_path = actor_path
            selection.active_entity_path = ptr.entity_path
            return True

        return False

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

    def _save_expaneded_items(
        self, parent: QtCore.QModelIndex, parent_actor_path: Path | None
    ):
        model = self.actor_model()
        local_scene = model.local_scene

        for i in range(model.rowCount(parent)):
            child = model.index(i, 0, parent)
            if not self.isExpanded(child):
                continue

            ptr = child.internalPointer()
            if isinstance(ptr, BaseActor):
                actor_path = local_scene.get_actor_path(ptr)
                if actor_path is not None:
                    self._temp_expaned_items.append(actor_path)
                    self._save_expaneded_items(child, actor_path)
            elif isinstance(ptr, EntityInfo):
                entity_path = ptr.entity_path
                assert parent_actor_path is not None
                full_entity_path = FullEntityPath(parent_actor_path, entity_path)
                self._temp_expaned_items.append(full_entity_path)
                self._save_expaneded_items(child, parent_actor_path)

    def _expand_actor(self, actor_path: Path):
        model = self.actor_model()
        local_scene = model.local_scene

        actor = local_scene.find_actor_by_path(actor_path)
        if actor is None:
            return

        index = model.get_index_from_actor(actor)
        if not index.isValid():
            return

        def do_expand():
            self.setExpanded(index, True)

        QtCore.QTimer.singleShot(10, do_expand)

    def _expand_entity(self, full_entity_path: FullEntityPath):
        model = self.actor_model()
        local_scene = model.local_scene

        actor = local_scene.find_actor_by_path(full_entity_path.actor_path)
        if not isinstance(actor, AssetActor):
            return

        entity_root = actor.entity_root
        entity_info = entity_root.find_entity_info_by_path(full_entity_path.entity_path)
        if entity_info is None:
            return

        index = model.get_index_for_entity(actor, entity_info.entity_path)
        if not index.isValid():
            return

        def do_expand():
            self.setExpanded(index, True)

        QtCore.QTimer.singleShot(10, do_expand)

    def _restore_expanded_items(self):
        for item in self._temp_expaned_items:
            if isinstance(item, Path):
                self._expand_actor(item)
            elif isinstance(item, FullEntityPath):
                self._expand_entity(item)

    def _before_reset_model(self):
        self._temp_expaned_items.clear()
        self._save_expaneded_items(QtCore.QModelIndex(), None)

    def _after_reset_model(self):
        model = self.actor_model()
        local_scene = model.local_scene

        self.set_selection(local_scene.selection())

        self._restore_expanded_items()
        self._temp_expaned_items.clear()