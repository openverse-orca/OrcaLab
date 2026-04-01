import asyncio
from typing import List, Tuple, override

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, QMimeData, Signal

from orcalab.actor import BaseActor, GroupActor
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
        # actor to be reparented
        self.actors = actors
        self.actor_paths = actor_paths

        # new parent
        self.parent = parent
        self.parent_path = parent_path


class ActorOutlineModel(QAbstractItemModel, SceneEditNotification):
    # actor path, new parent path, index to insert at (-1 means append to the end)
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

    def get_actor(self, index: QModelIndex) -> BaseActor:
        if not index.isValid():
            return self.m_root_group

        if index.model() != self:
            raise ValueError("Index does not belong to this model.")

        actor = index.internalPointer()
        if not isinstance(actor, BaseActor):
            raise ValueError("Invalid actor.")

        return actor

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

    @override
    def index(self, row, column, /, parent=...):
        if row < 0 or column < 0 or column >= self.column_count:
            return QModelIndex()

        if not parent.isValid():
            if row < len(self.m_root_group.children):
                child = self.m_root_group.children[row]
                if child is not None:
                    return self.createIndex(row, column, child)
        else:
            if parent.column() == 0:
                parent_actor = self.get_actor(parent)
                if isinstance(parent_actor, GroupActor):
                    if row < len(parent_actor.children):
                        child = parent_actor.children[row]
                        return self.createIndex(row, column, child)

        return QModelIndex()

    @override
    def parent(self, child):
        super().parent()
        if not child.isValid():
            return QModelIndex()

        actor = self.get_actor(child)

        parent_actor = actor.parent
        if parent_actor == self.m_root_group:
            return QModelIndex()

        return self.get_index_from_actor(parent_actor)

    @override
    def rowCount(self, /, parent=...):
        if not parent.isValid():
            if self.m_root_group is not None:
                return len(self.m_root_group.children)
        else:
            if parent.column() == 0:
                actor = self.get_actor(parent)
                if isinstance(actor, GroupActor):
                    return len(actor.children)
        return 0

    @override
    def columnCount(self, /, parent=...):
        return 1

    @override
    def data(self, index, /, role=...):
        if not index.isValid():
            return None

        actor = self.get_actor(index)

        if index.column() == 0:
            if role == Qt.ItemDataRole.DisplayRole:
                return actor.name

        return None

    @override
    def flags(self, index, /):
        ItemFlag = Qt.ItemFlag

        if not index.isValid():
            return ItemFlag.ItemIsDropEnabled

        f = (
            ItemFlag.ItemIsEnabled
            | ItemFlag.ItemIsSelectable
            # | ItemFlag.ItemIsDragEnabled
            | ItemFlag.ItemIsDropEnabled
            # | ItemFlag.ItemIsEditable
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

            # This signal is used for debug only now.
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
            # decode asset name robustly
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

        # print(f"drop {parent_actor_path}, row: {row}, col:{column}")

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
        # The insert operation was started but failed
        # Reset the entire model to ensure view is in sync with actual data
        self.beginResetModel()
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
