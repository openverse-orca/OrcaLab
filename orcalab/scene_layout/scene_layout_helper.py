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
        self.version = "2.0"

    @staticmethod
    def _node_stable_key(node) -> str:
        """返回节点的稳定标识符：使用 Name 属性的 original_value（跨 session 不变的初始名）。
        如果不存在则退回到 display_name。"""
        name_prop = next((p for p in node.properties if p.name() == "Name"), None)
        if name_prop is not None:
            orig = name_prop.original_value()
            if isinstance(orig, str) and orig:
                return orig
        return node.display_name

    @staticmethod
    def _resolve_entity_path_for_node(actor: AssetActor, node) -> str | None:
        """根据 TreePropertyNode.name 中的 entity_id 从 EntityInfo 层级中解析 entity_path。
        node.name 格式为 'entityId:componentId' 或 'entityId'。
        """
        entity_root = actor.entity_root
        if entity_root is None:
            return None
        try:
            entity_id = int(node.name.split(":")[0])
        except (ValueError, TypeError, AttributeError):
            return None
        entity_info = entity_root.find_by_entity_id(entity_id)
        if entity_info is not None:
            return entity_info.entity_path
        return None

    @staticmethod
    def _collect_modified_tree_props(nodes, group_prefix: str, component_type: str, actor: AssetActor) -> list:
        result = []
        for node in nodes:
            entity_path = SceneLayoutHelper._resolve_entity_path_for_node(actor, node)
            for prop in node.properties:
                if prop.is_modified():
                    entry = {
                        "group_prefix": group_prefix,
                        "component_type": component_type,
                        "property_name": prop.name(),
                        "type": prop.value_type().name,
                        "value": prop.value(),
                    }
                    if entity_path is not None:
                        entry["entity_path"] = entity_path
                    else:
                        stable_key = SceneLayoutHelper._node_stable_key(node)
                        entry["name"] = f"{stable_key}.{prop.name()}"
                    result.append(entry)
            result.extend(SceneLayoutHelper._collect_modified_tree_props(node.children, group_prefix, component_type, actor))
        return result

    @staticmethod
    def collect_modified_properties(actor: AssetActor) -> list:
        result = []
        for group in actor.property_groups:
            component_type = group.name
            entity_path = group.hint
            for prop in group.properties:
                if prop.value_type() == ActorPropertyType.TREE:
                    continue
                if prop.is_modified():
                    entry = {
                        "entity_path": entity_path,
                        "component_type": component_type,
                        "property_name": prop.name(),
                        "type": prop.value_type().name,
                        "value": prop.value(),
                    }
                    result.append(entry)
            result.extend(SceneLayoutHelper._collect_modified_tree_props(group.tree_data, group.prefix, component_type, actor))
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

    @staticmethod
    def _sync_tree_display_names(nodes: list) -> None:
        """同步关节叶节点的 display_name 与 Name 属性值（加载 layout 后调用）。"""
        for node in nodes:
            SceneLayoutHelper._sync_tree_display_names(node.children)
            if not node.name.startswith("e:"):
                for prop in node.properties:
                    if prop.name() == "Name":
                        val = prop.value()
                        if isinstance(val, str) and val:
                            node.display_name = val
                        break

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

        layout_version = data.get("version", "1.0")
        if layout_version not in ("1.0", "2.0"):
            logger.error("不支持的场景布局版本: %s", layout_version)
            return False

        if layout_version == "1.0":
            logger.warning("加载旧版(v1.0)场景布局，建议重新保存以升级到 v2.0 格式")

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

        is_visible = actor_data.get("is_visible", True)
        is_parent_visible = actor_data.get("is_parent_visible", True)
        is_locked = actor_data.get("is_locked", False)
        is_parent_locked = actor_data.get("is_parent_locked", False)
        
        if name == "root":
            actor = self.local_scene.root_actor
        else:

            if actor_type == "AssetActor":
                asset_path = actor_data.get("asset_path", "")
                actor = AssetActor(name=name, asset_path=asset_path)
            else:
                actor = GroupActor(name=name)

            actor.transform = transform

            actor.is_visible = is_visible
            actor.is_parent_visible = is_parent_visible
            actor.is_locked = is_locked
            actor.is_parent_locked = is_parent_locked

            try:
                assert parent is not None
                await SceneEditRequestBus().add_actor(actor=actor, parent_actor=parent)

                actor_path = self.local_scene.get_actor_path(actor)
                if actor.is_visible == False or actor.is_parent_visible == False:
                    await SceneEditRequestBus().set_actor_visible(actor_path, False, undo=False, source="layout")
                if actor.is_locked or actor.is_parent_locked:
                    await SceneEditRequestBus().set_actor_locked(actor_path, True, undo=False, source="layout")

                if isinstance(actor, AssetActor):
                    await self._apply_modified_properties(actor, actor_data)
                    # 属性应用完毕后同步关节显示名，确保 UI 按钮文字正确
                    for group in actor.property_groups:
                        SceneLayoutHelper._sync_tree_display_names(group.tree_data)
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
            type_str: str = entry.get("type", "")
            value: Any = entry.get("value")

            prop_type = _type_map.get(type_str)
            if prop_type is None or prop_type == ActorPropertyType.TREE:
                continue

            entity_path: str | None = entry.get("entity_path", None)
            component_type: str | None = entry.get("component_type", None)
            property_name: str | None = entry.get("property_name", None)
            prop_name: str | None = entry.get("name", None)

            matched_prop = None
            matched_group_prefix = group_prefix
            matched_key_prop_name = property_name or prop_name or ""

            if entity_path is not None and property_name is not None:
                matched_prop, matched_group_prefix, matched_key_prop_name = self._find_prop_v2(
                    actor, entity_path, component_type, property_name
                )

            if matched_prop is None and prop_name is not None:
                matched_prop, engine_key_name = self._find_prop_by_legacy_name(
                    actor, group_prefix, prop_name
                )
                if matched_prop is not None:
                    matched_group_prefix = group_prefix
                    matched_key_prop_name = engine_key_name

            if matched_prop is not None:
                try:
                    matched_prop.set_value(value)
                except Exception:
                    pass

                key = ActorPropertyKey(
                    actor_path, matched_group_prefix,
                    matched_key_prop_name,
                    prop_type,
                )
                try:
                    await SceneEditRequestBus().set_property(key, value, undo=False, source="layout")
                except Exception as e:
                    logger.warning("应用属性失败 %s.%s: %s", matched_group_prefix, property_name or prop_name, e)

    @staticmethod
    def _find_prop_v2(
        actor: AssetActor,
        entity_path: str,
        component_type: str | None,
        property_name: str,
    ) -> tuple | tuple[None, str, str]:
        """v2.0 格式：使用 entity_path + component_type + property_name 三元组寻址。
        group.hint 存储 entity_path，group.name 存储 component_type。
        对于普通属性：group.hint == entity_path 直接匹配。
        对于树形属性：entity_path 可能是子实体路径，需在 group 的 tree_data 中搜索。
        返回 (prop, group_prefix, key_property_name)，key_property_name 用于 ActorPropertyKey。"""
        for group in actor.property_groups:
            if group.hint != entity_path:
                continue
            if component_type is not None and group.name != component_type:
                continue

            for prop in group.properties:
                if prop.name() == property_name:
                    return prop, group.prefix, property_name

            matched_prop, key_prop_name = SceneLayoutHelper._find_prop_in_tree_by_entity_id_for_path(
                actor, group.tree_data, entity_path, property_name
            )
            if matched_prop is not None:
                return matched_prop, group.prefix, key_prop_name

        for group in actor.property_groups:
            if component_type is not None and group.name != component_type:
                continue

            matched_prop, key_prop_name = SceneLayoutHelper._find_prop_in_tree_by_entity_id_for_path(
                actor, group.tree_data, entity_path, property_name
            )
            if matched_prop is not None:
                return matched_prop, group.prefix, key_prop_name

        return None, "", ""

    @staticmethod
    def _find_prop_in_tree_by_entity_id_for_path(
        actor: AssetActor,
        nodes,
        entity_path: str,
        property_name: str,
    ) -> tuple | tuple[None, str]:
        """在树形属性节点中，根据 entity_path 转换为 entity_id 后查找属性。"""
        entity_root = actor.entity_root
        if entity_root is None:
            return None, ""

        entity_info = entity_root.find_by_entity_path(entity_path)
        if entity_info is None:
            return None, ""

        return SceneLayoutHelper._find_prop_in_tree_by_entity_id(
            nodes, entity_info.entity_id, property_name
        )

    @staticmethod
    def _find_prop_by_entity_path(
        actor: AssetActor,
        group_prefix: str,
        entity_path: str,
        component_type: str | None,
        property_name: str,
    ) -> tuple | tuple[None, str]:
        """v2.0 格式：使用 entity_path 在 EntityInfo 层级中定位 Entity，
        获取运行时 entity_id，再在 TreePropertyNode 中找到对应属性。"""
        entity_root = actor.entity_root
        if entity_root is None:
            return None, ""

        entity_info = entity_root.find_by_entity_path(entity_path)
        if entity_info is None:
            return None, ""

        runtime_entity_id = entity_info.entity_id

        for group in actor.property_groups:
            if group.prefix != group_prefix:
                continue
            if component_type is not None and group.name != component_type:
                continue
            matched_prop, engine_key_name = SceneLayoutHelper._find_prop_in_tree_by_entity_id(
                group.tree_data, runtime_entity_id, property_name
            )
            if matched_prop is not None:
                return matched_prop, engine_key_name

        return None, ""

    @staticmethod
    def _find_prop_in_tree_by_entity_id(
        nodes, entity_id: int, property_name: str
    ) -> tuple | tuple[None, str]:
        """在树形属性节点中根据 entity_id 和 property_name 查找属性。"""
        for node in nodes:
            try:
                node_entity_id = int(node.name.split(":")[0])
            except (ValueError, TypeError, AttributeError):
                node_entity_id = None

            if node_entity_id == entity_id:
                for prop in node.properties:
                    if prop.name() == property_name:
                        return prop, f"{node.name}.{prop.name()}"

            found_prop, found_key = SceneLayoutHelper._find_prop_in_tree_by_entity_id(
                node.children, entity_id, property_name
            )
            if found_prop is not None:
                return found_prop, found_key

        return None, ""

    @staticmethod
    def _find_prop_by_legacy_name(
        actor: AssetActor,
        group_prefix: str,
        prop_name: str,
    ) -> tuple | tuple[None, str]:
        """v1.0 兼容格式：使用 display_name.PropName 在树形属性中查找。"""
        for group in actor.property_groups:
            if group.prefix != group_prefix:
                continue
            if "." in prop_name:
                dot = prop_name.index(".")
                node_display_name = prop_name[:dot]
                leaf_name = prop_name[dot + 1:]
                node = SceneLayoutHelper._find_tree_node_by_display_name(group.tree_data, node_display_name)
                if node is not None:
                    matched_prop = next(
                        (p for p in node.properties if p.name() == leaf_name), None
                    )
                    if matched_prop is not None:
                        return matched_prop, f"{node.name}.{leaf_name}"
            else:
                for prop in group.properties:
                    if prop.name() == prop_name:
                        return prop, prop_name
        return None, ""
