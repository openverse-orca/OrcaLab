import ast
import logging
import math
from typing import Any, List
import numpy as np
from orcalab.actor import AssetActor, BaseActor, GroupActor
from orcalab.actor_property import ActorPropertyKey, ActorPropertyType
from orcalab.local_scene import LocalScene
import json
import pathlib
from orcalab.math import Transform
from orcalab.path import Path
from orcalab.scene_edit_bus import SceneEditRequestBus

from PySide6 import QtCore, QtWidgets, QtGui


logger = logging.getLogger(__name__)


def compact_array(arr):
    return "[" + ",".join(str(x) for x in arr) + "]"


def parse_compact_array(s: str):
    s = s.strip().lstrip("[").rstrip("]")
    return [float(x) for x in s.split(",") if x]


class _ActorData:
    def __init__(self, actor: BaseActor, path: Path, parent_actor: BaseActor | None):
        self.actor = actor
        self.path = path
        self.parent = parent_actor


class SceneLayoutHelper:
    def __init__(self, local_scene: LocalScene) -> None:
        self.local_scene = local_scene
        self.version = "1.0"

    @staticmethod
    def _collect_modified_tree_props(nodes, group_prefix: str) -> list:
        result = []
        for node in nodes:
            for prop in node.properties:
                if prop.is_modified():
                    result.append({
                        "group_prefix": group_prefix,
                        "name": f"{node.display_name}.{prop.name()}",
                        "type": prop.value_type().name,
                        "value": prop.value(),
                    })
            result.extend(SceneLayoutHelper._collect_modified_tree_props(node.children, group_prefix))
        return result

    @staticmethod
    def collect_modified_properties(actor: AssetActor) -> list:
        result = []
        for group in actor.property_groups:
            for prop in group.properties:
                if prop.value_type() == ActorPropertyType.TREE:
                    continue
                if prop.is_modified():
                    result.append({
                        "group_prefix": group.prefix,
                        "name": prop.name(),
                        "type": prop.value_type().name,
                        "value": prop.value(),
                    })
            result.extend(SceneLayoutHelper._collect_modified_tree_props(group.tree_data, group.prefix))
        return result

    @staticmethod
    def _find_tree_node_by_display_name(nodes, display_name: str):
        for node in nodes:
            if node.display_name == display_name:
                return node
            found = SceneLayoutHelper._find_tree_node_by_display_name(node.children, display_name)
            if found is not None:
                return found
        return None

    async def clear_layout(self):
        for actor in self.local_scene.root_actor.children:
            await SceneEditRequestBus().delete_actor(actor, undo=False)

    def create_empty_layout(self, file_path: str):
        layout_dict = {
            "version": self.version,
            "name": "root",
            "path": "/",
            "transform": {
                "position": "[0.0,0.0,0.0]",
                "rotation": "[1,0,0,0]",
                "scale": 1.0,
            },
            "type": "GroupActor",
            "children": [],
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(layout_dict, f, indent=4)

    async def load_scene_layout(self, window: QtWidgets.QWidget, filename: str):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.exception("读取场景布局文件失败: %s", e)
            return False

        await self._clear_scene_layout(self.local_scene.root_actor)
        errors: List[str] = []
        await self._create_actor_from_scene_layout(data, None, errors=errors)

        if errors:
            error_detail = "\n".join(errors)
            logger.warning("加载场景布局时部分Actor创建失败:\n%s", error_detail)
            QtCore.QTimer.singleShot(
                0,
                lambda: QtWidgets.QMessageBox.warning(
                    window,
                    "加载场景布局警告",
                    f"场景布局 '{filename}' 加载过程中部分Actor创建失败:\n\n{error_detail}",
                    QtWidgets.QMessageBox.StandardButton.Ok,
                ),
            )

        return True

    async def _clear_scene_layout(self, actor):
        if isinstance(actor, GroupActor):
            for child_actor in actor.children:
                await self._clear_scene_layout(child_actor)
        if actor != self.local_scene.root_actor:
            await SceneEditRequestBus().delete_actor(actor)

        await SceneEditRequestBus().set_selection([], undo=False)

    async def _create_actor_from_scene_layout(
        self,
        actor_data,
        parent: GroupActor | None,
        errors: List[str],
    ):

        name = actor_data["name"]
        actor_type = actor_data.get("type", "BaseActor")

        transform_data = actor_data.get("transform", {})
        position = np.array(
            ast.literal_eval(transform_data["position"]), dtype=float
        ).reshape(3)
        rotation = np.array(ast.literal_eval(transform_data["rotation"]), dtype=float)
        scale = transform_data.get("scale", 1.0)
        transform = Transform(position, rotation, scale)

        if name == "root":
            actor = self.local_scene.root_actor
        else:

            if actor_type == "AssetActor":
                asset_path = actor_data.get("asset_path", "")
                actor = AssetActor(name=name, asset_path=asset_path)
            else:
                actor = GroupActor(name=name)

            actor.transform = transform

            try:
                assert parent is not None
                await SceneEditRequestBus().add_actor(actor=actor, parent_actor=parent)
                if isinstance(actor, AssetActor):
                    await self._apply_modified_properties(actor, actor_data)
            except Exception as e:

                if isinstance(actor, AssetActor):
                    error_msg = (
                        f"创建 Actor {name} 失败: {e}, asset_path: {actor.asset_path}"
                    )
                    logger.warning(error_msg)
                    errors.append(error_msg)

        if isinstance(actor, GroupActor):
            for child_data in actor_data.get("children", []):
                await self._create_actor_from_scene_layout(child_data, actor, errors)

    async def _apply_modified_properties(self, actor: AssetActor, actor_data: dict):
        saved = actor_data.get("modified_properties", [])
        if not saved:
            return

        actor_path = self.local_scene.get_actor_path(actor)
        if actor_path is None:
            return

        _type_map = {t.name: t for t in ActorPropertyType}

        for entry in saved:
            group_prefix: str = entry.get("group_prefix", "")
            prop_name: str = entry.get("name", "")
            type_str: str = entry.get("type", "")
            value: Any = entry.get("value")

            prop_type = _type_map.get(type_str)
            if prop_type is None or prop_type == ActorPropertyType.TREE:
                continue

            # 在 actor.property_groups 中找到对应属性并更新 Python 侧值
            # 对于树形子属性，engine_key_name 使用当前 EntityId（运行时稳定），
            # 而 prop_name 中存储的是 display_name（跨 session 稳定）
            matched_prop = None
            engine_key_name = prop_name
            for group in actor.property_groups:
                if group.prefix != group_prefix:
                    continue
                if "." in prop_name:
                    # 树形子属性：格式为 "display_name.PropName"
                    dot = prop_name.index(".")
                    node_display_name = prop_name[:dot]
                    leaf_name = prop_name[dot + 1:]
                    node = SceneLayoutHelper._find_tree_node_by_display_name(group.tree_data, node_display_name)
                    if node is not None:
                        matched_prop = next(
                            (p for p in node.properties if p.name() == leaf_name), None
                        )
                        engine_key_name = f"{node.name}.{leaf_name}"
                else:
                    for prop in group.properties:
                        if prop.name() == prop_name:
                            matched_prop = prop
                            break
                if matched_prop is not None:
                    break

            if matched_prop is not None:
                try:
                    matched_prop.set_value(value)
                except Exception:
                    pass

            key = ActorPropertyKey(actor_path, group_prefix, engine_key_name, prop_type)
            try:
                await SceneEditRequestBus().set_property(key, value, undo=False, source="layout")
            except Exception as e:
                logger.warning("应用属性失败 %s.%s: %s", group_prefix, prop_name, e)
