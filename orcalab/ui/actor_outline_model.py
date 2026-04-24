import asyncio
from typing import List, Tuple, override

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, QMimeData, Signal

from orcalab.actor import AssetActor, BaseActor, GroupActor
from orcalab.entity_info import EntityInfo
from orcalab.local_scene import LocalScene
from orcalab.path import Path
from orcalab.scene_edit_bus import (
    SceneEditNotification,
    SceneEditNotificationBus,
    SceneEditRequestBus,
)

import logging

logger = logging.getLogger(__name__)


class ReparentData:
    def __init__(
        self,
        actors: List[BaseActor],
        actor_paths: List[Path],
        parent: BaseActor,
        parent_path: Path,
    ):
        self.actors = actors
        self.actor_paths = actor_paths
        self.parent = parent
        self.parent_path = parent_path


class ActorOutlineModel(QAbstractItemModel, SceneEditNotification):
    request_reparent = Signal(Path, Path, int)
    add_item = Signal(str, BaseActor)

    def __init__(self, local_scene: LocalScene, parent=None):
        super().__init__(parent)
        self.column_count = 1
        self.m_root_group: GroupActor | None = None
        self.reparent_mime = "application/x-orca-actor-reparent"
        self.local_scene = local_scene

    def connect_bus(self):
        SceneEditNotificationBus.connect(self)

    def disconnect_bus(self):
        SceneEditNotificationBus.disconnect(self)

    def _node_from_index(self, index: QModelIndex) -> BaseActor | EntityInfo | None:
        if not index.isValid():
            return self.m_root_group
        node = index.internalPointer()
        if isinstance(node, (BaseActor, EntityInfo)):
            return node
        return None

    def get_actor(self, index: QModelIndex) -> BaseActor:
        if not index.isValid():
            return self.m_root_group

        if index.model() != self:
            raise ValueError("Index does not belong to this model.")

        node = index.internalPointer()
        if isinstance(node, BaseActor):
            return node
        if isinstance(node, EntityInfo):
            actor_path = self._find_actor_path_for_entity_index(index)
            if actor_path is not None:
                actor = self.local_scene.find_actor_by_path(actor_path)
                if actor is not None:
                    return actor
            raise ValueError("Cannot resolve actor for EntityInfo node.")

        raise ValueError("Invalid node.")

    def _find_actor_path_for_entity_index(self, index: QModelIndex) -> Path | None:
        current = index
        while current.isValid():
            node = current.internalPointer()
            if isinstance(node, AssetActor):
                return self.local_scene.get_actor_path(node)
            current = current.parent()
        return None

    def get_index_from_actor(self, actor: BaseActor) -> QModelIndex:
        if not isinstance(actor, BaseActor):
            raise ValueError("Invalid actor.")

        if actor == self.m_root_group:
            return QModelIndex()

        parent_actor = actor.parent
        if parent_actor is None:
            raise Exception("Actor that is not pseudo root should always has a parent.")

        index = -1
        children = parent_actor.children
        for i, child in enumerate(children):
            if child == actor:
                index = i
                break

        if index == -1:
            raise Exception("Child not found from it's parent.")

        return self.createIndex(index, 0, actor)

    def get_index_from_entity_info(
        self, actor_path: Path, entity_info: EntityInfo
    ) -> QModelIndex:
        entity_root = self.local_scene.get_entity_root(actor_path)
        if entity_root is None:
            return QModelIndex()

        if entity_root is entity_info:
            actor = self.local_scene.find_actor_by_path(actor_path)
            if actor is None:
                return QModelIndex()
            self.get_index_from_actor(actor)
            return self.createIndex(0, 0, entity_info)

        parent_entity, row = self._find_parent_and_row(entity_root, entity_info)
        if parent_entity is None:
            return QModelIndex()

        if parent_entity is entity_root:
            actor = self.local_scene.find_actor_by_path(actor_path)
            if actor is None:
                return QModelIndex()
            return self.createIndex(row, 0, entity_info)

        parent_index = self.get_index_from_entity_info(actor_path, parent_entity)
        if not parent_index.isValid():
            return QModelIndex()
        return self.createIndex(row, 0, entity_info)

    def _find_parent_and_row(
        self, root: EntityInfo, target: EntityInfo
    ) -> Tuple[EntityInfo | None, int]:
        for i, child in enumerate(root.children):
            if child is target:
                return root, i
            result_parent, result_row = self._find_parent_and_row(child, target)
            if result_parent is not None:
                return result_parent, result_row
        return None, -1

    @override
    def index(self, row, column, /, parent=...):
        if row < 0 or column < 0 or column >= self.column_count:
            return QModelIndex()

        if not parent.isValid():
            if self.m_root_group is not None and row < len(self.m_root_group.children):
                child = self.m_root_group.children[row]
                if child is not None:
                    return self.createIndex(row, column, child)
        else:
            if parent.column() != 0:
                return QModelIndex()

            node = parent.internalPointer()

            if isinstance(node, GroupActor):
                if row < len(node.children):
                    child = node.children[row]
                    return self.createIndex(row, column, child)

            elif isinstance(node, AssetActor):
                entity_root = self.local_scene.get_entity_root(
                    self.local_scene.get_actor_path(node)
                )
                if entity_root is not None:
                    if row == 0:
                        return self.createIndex(0, column, entity_root)

            elif isinstance(node, EntityInfo):
                if row < len(node.children):
                    child = node.children[row]
                    return self.createIndex(row, column, child)

        return QModelIndex()

    @override
    def parent(self, child):
        super().parent()
        if not child.isValid():
            return QModelIndex()

        node = child.internalPointer()

        if isinstance(node, BaseActor):
            parent_actor = node.parent
            if parent_actor == self.m_root_group:
                return QModelIndex()
            return self.get_index_from_actor(parent_actor)

        elif isinstance(node, EntityInfo):
            actor_path = self._find_actor_path_for_entity_index(child)
            if actor_path is None:
                return QModelIndex()

            entity_root = self.local_scene.get_entity_root(actor_path)
            if entity_root is None:
                return QModelIndex()

            if node is entity_root:
                actor = self.local_scene.find_actor_by_path(actor_path)
                if actor is None:
                    return QModelIndex()
                return self.get_index_from_actor(actor)

            parent_entity, _ = self._find_parent_and_row(entity_root, node)
            if parent_entity is None:
                return QModelIndex()

            if parent_entity is entity_root:
                actor = self.local_scene.find_actor_by_path(actor_path)
                if actor is None:
                    return QModelIndex()
                return self.createIndex(0, 0, entity_root)

            return self.createIndex(child.row(), 0, parent_entity)

        return QModelIndex()

    @override
    def rowCount(self, /, parent=...):
        if not parent.isValid():
            if self.m_root_group is not None:
                return len(self.m_root_group.children)
        else:
            if parent.column() != 0:
                return 0

            node = parent.internalPointer()

            if isinstance(node, GroupActor):
                return len(node.children)

            elif isinstance(node, AssetActor):
                actor_path = self.local_scene.get_actor_path(node)
                entity_root = self.local_scene.get_entity_root(actor_path)
                return 1 if entity_root is not None else 0

            elif isinstance(node, EntityInfo):
                return len(node.children)

        return 0

    @override
    def columnCount(self, /, parent=...):
        return 1

    @override
    def data(self, index, /, role=...):
        if not index.isValid():
            return None

        node = index.internalPointer()

        if index.column() == 0:
            if role == Qt.ItemDataRole.DisplayRole:
                if isinstance(node, BaseActor):
                    return node.name
                elif isinstance(node, EntityInfo):
                    return node.name

            if role == Qt.ItemDataRole.DecorationRole:
                pass

            if role == Qt.ItemDataRole.UserRole:
                if isinstance(node, EntityInfo):
                    return "entity"

        return None

    @override
    def flags(self, index, /):
        ItemFlag = Qt.ItemFlag

        if not index.isValid():
            return ItemFlag.ItemIsDropEnabled

        node = index.internalPointer()

        if isinstance(node, EntityInfo):
            return ItemFlag.ItemIsEnabled | ItemFlag.ItemIsSelectable

        f = (
            ItemFlag.ItemIsEnabled
            | ItemFlag.ItemIsSelectable
            | ItemFlag.ItemIsDropEnabled
        )

        return f

    def set_root_group(self, group: GroupActor):
        if not isinstance(group, GroupActor):
            raise TypeError("Root group must be an instance of GroupActor.")

        self.beginResetModel()
        self.m_root_group = group
        self.endResetModel()

    def supportedDropActions(self):
        return Qt.DropAction.CopyAction | Qt.DropAction.MoveAction

    def supportedDragActions(self):
        return Qt.DropAction.CopyAction

    def dropMimeData(self, data: QMimeData, action, row, column, parent):
        logger.debug("drop")
        if data.hasFormat(self.reparent_mime):
            ok, reparent_data = self.prepare_reparent_data(
                data,
                action,
                row,
                column,
                parent,
            )

            if not ok:
                return False

            assert reparent_data is not None

            self.request_reparent.emit("", reparent_data.parent_path, row)

            new_parent_paths: List[Path] = [reparent_data.parent_path] * len(reparent_data.actor_paths)
            insert_positions: List[int] = [row] * len(reparent_data.actor_paths)

            async def _do_reparent():
                await SceneEditRequestBus().move_actors(
                    reparent_data.actor_paths,
                    new_parent_paths,
                    insert_positions,
                    undo=True,
                    source="actor_outline",
                )

            logger.debug(
                f"reparent {reparent_data.actor_paths} to {reparent_data.parent_path} at {row}"
            )
            asyncio.create_task(_do_reparent())

            return True

        if data.hasFormat("application/x-orca-asset"):
            ba = data.data("application/x-orca-asset")
            try:
                asset_name = bytes(ba).decode("utf-8")
            except Exception:
                try:
                    asset_name = ba.data().decode("utf-8")
                except Exception:
                    asset_name = str(ba)

            parent_actor = self.get_actor(parent)

            self.add_item.emit(asset_name, parent_actor)
            return True

        return False

    def canDropMimeData(self, data: QMimeData, action, row, column, parent):
        if data.hasFormat("application/x-orca-asset"):
            parent_actor = self.get_actor(parent)
            if not isinstance(parent_actor, GroupActor):
                return False
            return True

        if data.hasFormat(self.reparent_mime):
            ok, reparent_data = self.prepare_reparent_data(
                data,
                action,
                row,
                column,
                parent,
            )
            return ok

        return False

    @override
    def mimeData(self, indexes):
        if len(indexes) == 0:
            return QMimeData()

        actor = self.get_actor(indexes[0])

        actor_path = self.local_scene.get_actor_path(actor)
        if actor_path is None:
            return QMimeData()

        mime_data = QMimeData()
        mime_data.setData(self.reparent_mime, actor_path.string().encode("utf-8"))
        return mime_data

    def mimeTypes(self):
        return [self.reparent_mime, "application/x-orca-asset"]

    def prepare_reparent_data(
        self,
        mime_data: QMimeData,
        action,
        row,
        column,
        parent: QModelIndex,
    ) -> Tuple[bool, ReparentData | None]:
        if not mime_data.hasFormat(self.reparent_mime):
            return False, None

        if action not in [Qt.DropAction.CopyAction, Qt.DropAction.MoveAction]:
            return False, None

        if column > 0:
            return False, None

        parent_actor = self.get_actor(parent)

        parent_actor_path = self.local_scene.get_actor_path(parent_actor)
        if parent_actor_path is None:
            return False, None

        data_str = mime_data.data(self.reparent_mime).data().decode("utf-8")

        path_strs = data_str.split(";")
        actors: List[BaseActor] = []
        actor_paths: List[Path] = []
        new_parent_paths: List[Path] = []
        insert_positions: List[int] = []
        for path_str in path_strs:
            if not path_str:
                continue

            actor_path = Path(path_str)
            actor = self.local_scene.find_actor_by_path(actor_path)
            if actor is None:
                continue

            actors.append(actor)
            actor_paths.append(actor_path)
            new_parent_paths.append(parent_actor_path)
            insert_positions.append(row)

        ok, err = self.local_scene.can_move_actors(
            actors, new_parent_paths, insert_positions
        )
        if not ok:
            return False, None

        if len(actors) == 0:
            return False, None

        return True, ReparentData(actors, actor_paths, parent_actor, parent_actor_path)

    @override
    async def before_actor_added(
        self,
        actor: BaseActor,
        parent_actor_path: Path,
        source: str,
    ):
        parent_actor, _ = self.local_scene.get_actor_and_path(parent_actor_path)
        parent_index = self.get_index_from_actor(parent_actor)
        child_count = len(parent_actor.children)

        self.beginInsertRows(parent_index, child_count, child_count)

    @override
    async def on_actor_added(
        self,
        actor: BaseActor,
        parent_actor_path: Path,
        source: str,
    ):
        self.endInsertRows()

    @override
    async def on_actor_added_failed(
        self,
        actor: BaseActor,
        parent_actor_path: Path,
        source: str,
    ):
        self.endResetModel()

    @override
    async def before_actors_deleted(self, actor_paths: List[Path], source: str):
        self.beginResetModel()

    @override
    async def on_actors_deleted(self, actor_paths: List[Path], source: str):
        self.endResetModel()

    @override
    async def before_actor_renamed(
        self,
        actor_path: Path,
        new_name: str,
        source: str,
    ):
        pass

    @override
    async def on_actor_renamed(
        self,
        actor_path: Path,
        new_name: str,
        source: str,
    ):
        new_path = actor_path.parent() / new_name
        actor, _ = self.local_scene.get_actor_and_path(new_path)
        index = self.get_index_from_actor(actor)
        self.dataChanged.emit(index, index)

    @override
    async def before_actor_reparented(self):
        self.beginResetModel()

    @override
    async def on_actor_reparented(self):
        self.endResetModel()

    @override
    async def on_actor_visible_changed(
        self, actor_path: Path, paths_to_update: list, visible: bool, source: str = ""
    ):
        actor, _ = self.local_scene.get_actor_and_path(actor_path)
        index = self.get_index_from_actor(actor)
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.DecorationRole])

    @override
    async def on_actor_locked_changed(
        self, actor_path: Path, paths_to_update: list, locked: bool, source: str = ""
    ):
        actor, _ = self.local_scene.get_actor_and_path(actor_path)
        index = self.get_index_from_actor(actor)
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.DecorationRole])

    @override
    async def before_actor_added_batch(self):
        self.beginResetModel()

    @override
    async def on_actor_added_batch(self, error: str):
        self.endResetModel()

    @override
    async def on_entity_hierarchy_loaded(
        self,
        actor_path: Path,
        entity_root: EntityInfo,
        source: str = "",
    ) -> None:
        actor = self.local_scene.find_actor_by_path(actor_path)
        if actor is None:
            return

        actor_index = self.get_index_from_actor(actor)
        if not actor_index.isValid():
            return

        self.beginInsertRows(actor_index, 0, 0)
        self.endInsertRows()


if __name__ == "__main__":
    import unittest
    from orcalab.actor import AssetActor
    from PySide6.QtTest import QAbstractItemModelTester
    from PySide6.QtCore import QModelIndex, Qt

    class TestAddFunction(unittest.TestCase):
        def test_empty_path_is_invalid(self):
            local_scene = LocalScene()

            local_scene.add_actor(GroupActor("g1"), Path("/"))
            local_scene.add_actor(GroupActor("g2"), Path("/"))
            local_scene.add_actor(GroupActor("g3"), Path("/"))
            local_scene.add_actor(GroupActor("g4"), Path("/g2"))
            local_scene.add_actor(AssetActor("a1", "spw_name"), Path("/g3"))

            model = ActorOutlineModel(local_scene)
            model.set_root_group(local_scene.root_actor)

            self.assertEqual(model.rowCount(QModelIndex()), 3)
            index1 = model.index(0, 0, QModelIndex())
            self.assertEqual(index1.isValid(), True)
            self.assertEqual(index1.data(Qt.DisplayRole), "g1")
            self.assertEqual(
                model.parent(model.index(0, 0, QModelIndex())).isValid(), False
            )
            self.assertEqual(
                model.parent(model.index(1, 0, QModelIndex())).isValid(), False
            )
            self.assertEqual(
                model.parent(model.index(2, 0, QModelIndex())).isValid(), False
            )

            mode = QAbstractItemModelTester.FailureReportingMode.Fatal
            tester = QAbstractItemModelTester(model, mode)

    unittest.main()
