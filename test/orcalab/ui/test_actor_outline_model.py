import os
import sys
import asyncio

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QModelIndex, Qt, qInstallMessageHandler
from PySide6.QtTest import QAbstractItemModelTester

from orcalab.actor import AssetActor, GroupActor
from orcalab.entity_info import EntityInfo
from orcalab.entity_path import EntityPath, NameWithIndex
from orcalab.local_scene import LocalScene
from orcalab.path import Path
from orcalab.ui.actor_outline_model import ActorOutlineModel


@pytest.fixture
def q_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def outline_model(q_app):
    local_scene = LocalScene()
    group = GroupActor("group")
    asset = AssetActor("asset", "assets/test.prefab")

    local_scene.add_actor(group, Path.root_path())
    group_path = local_scene.get_actor_path(group)
    assert group_path is not None
    local_scene.add_actor(asset, group_path)

    root_entity = EntityInfo(
        entity_id=1,
        name="root_entity",
        entity_path=EntityPath([NameWithIndex("root_entity", 0)]),
        children=[],
    )
    child_entity = EntityInfo(
        entity_id=2,
        name="child_entity",
        entity_path=EntityPath(
            [NameWithIndex("root_entity", 0), NameWithIndex("child_entity", 0)]
        ),
        children=[],
        parent=root_entity,
    )
    root_entity.children = [child_entity]

    asset_path = local_scene.get_actor_path(asset)
    assert asset_path is not None
    local_scene.set_entity_root(asset_path, root_entity)

    model = ActorOutlineModel(local_scene)
    model.set_root_group(local_scene.pseudo_root_actor)
    return model, asset, root_entity, child_entity


def test_get_actor_resolves_entity_index_to_asset_actor(outline_model):
    model, asset, root_entity, _ = outline_model

    asset_index = model.get_index_from_actor(asset)
    entity_index = model.index(0, 0, asset_index)

    assert entity_index.isValid()
    assert entity_index.internalPointer() is root_entity.children[0]
    assert model.get_actor(entity_index) is asset


def test_parent_of_root_entity_is_its_asset_actor(outline_model):
    model, asset, root_entity, _ = outline_model

    asset_index = model.get_index_from_actor(asset)
    entity_index = model.index(0, 0, asset_index)

    assert entity_index.isValid()
    assert entity_index.internalPointer() is root_entity.children[0]
    assert model.parent(entity_index) == asset_index


def test_parent_of_nested_entity_is_parent_entity(outline_model):
    model, asset, root_entity, child_entity = outline_model

    asset_index = model.get_index_from_actor(asset)
    child_entity_index = model.index(0, 0, asset_index)

    assert child_entity_index.isValid()
    assert child_entity_index.internalPointer() is child_entity

    parent_index = model.parent(child_entity_index)

    assert parent_index == asset_index


def test_get_index_for_top_level_entity_uses_asset_children(outline_model):
    model, asset, _, child_entity = outline_model

    child_entity_index = model.get_index_for_entity(asset, child_entity.entity_path)

    assert child_entity_index.isValid()
    assert child_entity_index.internalPointer() is child_entity
    assert model.parent(child_entity_index) == model.get_index_from_actor(asset)


def test_qabstract_item_model_tester_handles_outline_model_updates(q_app):
    local_scene = LocalScene()
    group = GroupActor("group")
    nested_group = GroupActor("nested_group")
    asset = AssetActor("asset", "assets/test.prefab")
    sibling_asset = AssetActor("sibling_asset", "assets/other.prefab")

    local_scene.add_actor(group, Path.root_path())
    group_path = local_scene.get_actor_path(group)
    assert group_path is not None
    local_scene.add_actor(nested_group, group_path)
    nested_group_path = local_scene.get_actor_path(nested_group)
    assert nested_group_path is not None
    local_scene.add_actor(asset, nested_group_path)
    local_scene.add_actor(sibling_asset, group_path)

    root_entity = EntityInfo(
        entity_id=10,
        name="root_entity",
        entity_path=EntityPath([NameWithIndex("root_entity", 0)]),
        children=[],
    )
    child_entity = EntityInfo(
        entity_id=11,
        name="child_entity",
        entity_path=EntityPath(
            [NameWithIndex("root_entity", 0), NameWithIndex("child_entity", 0)]
        ),
        children=[],
        parent=root_entity,
    )
    grandchild_entity = EntityInfo(
        entity_id=12,
        name="grandchild_entity",
        entity_path=EntityPath(
            [
                NameWithIndex("root_entity", 0),
                NameWithIndex("child_entity", 0),
                NameWithIndex("grandchild_entity", 0),
            ]
        ),
        children=[],
        parent=child_entity,
    )
    child_entity.children = [grandchild_entity]
    root_entity.children = [child_entity]

    asset_path = local_scene.get_actor_path(asset)
    assert asset_path is not None
    local_scene.set_entity_root(asset_path, root_entity)

    model = ActorOutlineModel(local_scene)
    model.set_root_group(local_scene.pseudo_root_actor)

    messages: list[tuple[object, str]] = []

    def handler(message_type, context, message):
        messages.append((message_type, message))

    previous_handler = qInstallMessageHandler(handler)
    try:
        tester = QAbstractItemModelTester(
            model,
            QAbstractItemModelTester.FailureReportingMode.Warning,
        )
        tester.setUseFetchMore(False)

        root_index = QModelIndex()
        top_group_index = model.index(0, 0, root_index)
        nested_group_index = model.index(0, 0, top_group_index)
        asset_index = model.index(0, 0, nested_group_index)
        child_entity_index = model.index(0, 0, asset_index)
        grandchild_entity_index = model.index(0, 0, child_entity_index)

        assert model.rowCount(root_index) == 1
        assert model.rowCount(top_group_index) == 2
        assert model.rowCount(nested_group_index) == 1
        assert model.rowCount(asset_index) == 1
        assert model.rowCount(child_entity_index) == 1
        assert model.data(grandchild_entity_index, Qt.ItemDataRole.DisplayRole) == (
            "grandchild_entity"
        )

        original_asset_path = asset_path
        local_scene.rename_actor(asset, "asset_renamed")
        asyncio.run(
            model.on_actor_renamed(original_asset_path, "asset_renamed", source="test")
        )

        renamed_asset_path = local_scene.get_actor_path(asset)
        assert renamed_asset_path is not None
        assert renamed_asset_path == nested_group_path / "asset_renamed"
        renamed_asset_index = model.index(0, 0, nested_group_index)
        assert model.data(renamed_asset_index, Qt.ItemDataRole.DisplayRole) == (
            "asset_renamed"
        )

        asyncio.run(
            model.on_entity_hierarchy_loaded(
                renamed_asset_path,
                root_entity,
                source="test",
            )
        )

        reloaded_child_entity_index = model.index(0, 0, renamed_asset_index)
        reloaded_grandchild_entity_index = model.index(0, 0, reloaded_child_entity_index)
        assert reloaded_grandchild_entity_index.isValid()
        assert model.parent(reloaded_grandchild_entity_index) == reloaded_child_entity_index
    finally:
        qInstallMessageHandler(previous_handler)

    tester_messages = [message for _, message in messages if "QAbstractItemModelTester" in message]
    assert tester_messages == []