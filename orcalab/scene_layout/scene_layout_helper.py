import ast
import logging
import math
from typing import Any, List
import numpy as np
from orcalab.actor import AssetActor, BaseActor, GroupActor
from orcalab.actor_property import ActorPropertyKey, ActorPropertyType
from orcalab.local_scene import LocalScene
from orcalab.metadata_service_bus import MetadataServiceRequestBus
import json
import pathlib
from orcalab.transform import Transform
from orcalab.path import Path
from orcalab.scene_edit_bus import SceneEditRequestBus
from orcalab.scene_edit_types import AddActorRequest

from PySide6 import QtCore, QtWidgets, QtGui
from orcalab.application_util import get_remote_scene

logger = logging.getLogger(__name__)


def _show_scrollable_warning(parent, title: str, message: str, detail: str):
    dialog = QtWidgets.QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setMinimumSize(600, 400)

    layout = QtWidgets.QVBoxLayout(dialog)

    msg_label = QtWidgets.QLabel(message)
    msg_label.setWordWrap(True)
    layout.addWidget(msg_label)

    text_edit = QtWidgets.QTextEdit()
    text_edit.setReadOnly(True)
    text_edit.setPlainText(detail)
    layout.addWidget(text_edit)

    button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok)
    button_box.accepted.connect(dialog.accept)
    layout.addWidget(button_box)

    dialog.exec()


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
        self.flycamera_transform = Transform()

    def actor_to_layout_dict(self, actor: AssetActor | GroupActor) -> dict:
        def _to_list(v):
            return v.tolist() if hasattr(v, "tolist") else v

        actor_path = self.local_scene.get_actor_path(actor)
        path_str = actor_path._p if actor_path is not None else "/"
        data = {
            "name": actor.name,
            "path": path_str,
            "transform": {
                "position": compact_array(_to_list(actor.transform.position)),
                "rotation": compact_array(_to_list(actor.transform.rotation)),
                "scale": actor.transform.scale,
            },
            "is_visible": actor.is_visible,
            "is_parent_visible": actor.is_parent_visible,
            "is_locked": actor.is_locked,
            "is_parent_locked": actor.is_parent_locked,
        }

        if actor.name == "root":
            new_fields = {
                "version": self.version,
                "flycamera_transform": {
                    "position": compact_array(_to_list(self.flycamera_transform.position)),
                    "rotation": compact_array(_to_list(self.flycamera_transform.rotation)),
                    "scale": self.flycamera_transform.scale,
                },
            }
            data = {**new_fields, **data}

        if isinstance(actor, AssetActor):
            data["type"] = "AssetActor"
            data["asset_path"] = getattr(actor, "_asset_path", getattr(actor, "asset_path", ""))
            data["modified_properties"] = self.collect_modified_properties(actor)
        elif isinstance(actor, GroupActor):
            data["type"] = "GroupActor"
            data["children"] = [
                self.actor_to_layout_dict(child) for child in actor.children
            ]

        return data

    def save_scene_layout(self, filename: str):
        root = self.local_scene.root_actor
        scene_layout_dict = self.actor_to_layout_dict(root)

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(scene_layout_dict, f, indent=4, ensure_ascii=False)
        logger.info("场景布局已保存至 %s", filename)

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
    def collect_modified_properties(actor: AssetActor) -> list:
        result = []
        for group in actor.property_groups:
            component_type = group.name
            entity_path = group.hint
            for prop in group.properties:
                if prop.is_modified():
                    entry = {
                        "entity_path": entity_path,
                        "component_type": component_type,
                        "property_name": prop.name(),
                        "type": prop.value_type().name,
                        "value": prop.value(),
                    }
                    result.append(entry)
        return result

    @staticmethod
    def _find_tree_node_by_display_name(nodes, display_name: str):
        if not nodes:
            return None
        for node in nodes:
            found = SceneLayoutHelper._find_tree_node_by_display_name(node.children, display_name)
            if found is not None:
                return found
            if node.display_name == display_name:
                    return node
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

    @staticmethod
    def _find_prop_v2(actor: AssetActor, entity_path: str, component_type: str | None, property_name: str):
        for group in actor.property_groups:
            if group.hint != entity_path:
                continue
            if component_type is not None and group.name != component_type:
                continue

            dot_pos = property_name.rfind(".")
            if dot_pos != -1:
                node_display_name = property_name[:dot_pos]
                prop_name = property_name[dot_pos + 1:]
                node = SceneLayoutHelper._find_tree_node_by_display_name(group.tree_data, node_display_name)
                if node is not None:
                    for prop in node.properties:
                        if prop.name() == prop_name:
                            return prop, group.prefix, property_name, group
            else:
                for prop in group.properties:
                    if prop.name() == property_name:
                        return prop, group.prefix, property_name, group

        return None, "", "", None

    @staticmethod
    def _find_prop_by_legacy_name(actor: AssetActor, group_prefix: str, prop_name: str):
        for group in actor.property_groups:
            if group.prefix != group_prefix:
                continue

            dot_pos = prop_name.rfind(".")
            if dot_pos != -1:
                node_display_name = prop_name[:dot_pos]
                engine_prop_name = prop_name[dot_pos + 1:]
                node = SceneLayoutHelper._find_tree_node_by_display_name(group.tree_data, node_display_name)
                if node is not None:
                    for prop in node.properties:
                        if prop.name() == engine_prop_name:
                            return prop, prop_name
            else:
                for prop in group.properties:
                    if prop.name() == prop_name:
                        return prop, prop_name

        return None, ""

    async def clear_layout(self):
        children = list(self.local_scene.root_actor.children)
        if children:
            await SceneEditRequestBus().delete_actors(children, undo=False)

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

        await self.clear_layout()
        errors: List[str] = []
        await self._create_actor_from_scene_layout(data, errors=errors)

        if errors:
            error_detail = "\n".join(errors)
            logger.warning("加载场景布局时部分Actor创建失败:\n%s", error_detail)
            QtCore.QTimer.singleShot(
                0,
                lambda: _show_scrollable_warning(
                    window,
                    "加载场景布局警告",
                    f"场景布局 '{filename}' 加载过程中部分Actor创建失败:",
                    error_detail,
                ),
            )

        return True

    async def _create_actor_from_scene_layout(
        self,
        actor_data,
        errors: List[str],
    ):
        requests: List[AddActorRequest] = []
        post_add_items: list = []

        self._collect_layout_requests(actor_data, None, requests, post_add_items, errors)

        if actor_data.get("name") == "root":
            flycamera_transform_data = actor_data.get("flycamera_transform", {})
            if flycamera_transform_data:
                await SceneEditRequestBus().set_flycamera_transform(self.flycamera_transform)
            else:
                await self.get_flycamera_transform()

        if requests:
            try:
                await SceneEditRequestBus().add_actors(requests, undo=False, source="layout")
            except Exception as e:
                logger.warning("Batch add actors failed: %s", e)
                for actor, _ in post_add_items:
                    if isinstance(actor, AssetActor):
                        errors.append(
                            f"创建 Actor {actor.name} 失败: {e}, asset_path: {actor.asset_path}"
                        )
                    else:
                        errors.append(
                            f"创建 Actor {actor.name} 失败: {e}"
                        )
                return

        for actor, actor_data_item in post_add_items:
            actor_path = self.local_scene.get_actor_path(actor)
            if actor_path is None:
                continue
            try:
                if not actor.is_visible or not actor.is_parent_visible:
                    await SceneEditRequestBus().set_actor_visible(actor_path, False, undo=False, source="layout")
                if actor.is_locked or actor.is_parent_locked:
                    await SceneEditRequestBus().set_actor_locked(actor_path, True, undo=False, source="layout")

                if isinstance(actor, AssetActor):
                    await self._apply_modified_properties(actor, actor_data_item)
            except Exception as e:
                if isinstance(actor, AssetActor):
                    error_msg = (
                        f"创建 Actor {actor.name} 后处理失败: {e}, asset_path: {actor.asset_path}"
                    )
                    logger.warning(error_msg)
                    errors.append(error_msg)

    def _collect_layout_requests(
        self,
        actor_data,
        parent_path: Path | None,
        requests: List[AddActorRequest],
        post_add_items: list,
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
            current_path = Path("/")
            flycamera_transform_data = actor_data.get("flycamera_transform", {})
            if flycamera_transform_data:
                flycamera_position = np.array(
                    ast.literal_eval(flycamera_transform_data["position"]), dtype=float
                ).reshape(3)
                flycamera_rotation = np.array(
                    ast.literal_eval(flycamera_transform_data["rotation"]), dtype=float
                )
                flycamera_scale = flycamera_transform_data.get("scale", 1.0)
                self.flycamera_transform = Transform(flycamera_position, flycamera_rotation, flycamera_scale)
        else:
            if actor_type == "AssetActor":
                asset_path = actor_data.get("asset_path", "")
                output = []
                MetadataServiceRequestBus().get_asset_info(asset_path, output)
                if not output or output[0] is None:
                    errors.append(
                        f"跳过 Actor {name}: 资产不存在, asset_path: {asset_path}"
                    )
                    logger.warning("跳过 Actor %s: 资产不存在, asset_path: %s", name, asset_path)
                    return
                actor = AssetActor(name=name, asset_path=asset_path)
            else:
                actor = GroupActor(name=name)

            actor.transform = transform

            actor.is_visible = is_visible
            actor.is_parent_visible = is_parent_visible
            actor.is_locked = is_locked
            actor.is_parent_locked = is_parent_locked

            assert parent_path is not None
            requests.append(AddActorRequest(actor, parent_path))
            current_path = parent_path / name
            post_add_items.append((actor, actor_data))

        if isinstance(actor, GroupActor):
            for child_data in actor_data.get("children", []):
                self._collect_layout_requests(child_data, current_path, requests, post_add_items, errors)

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

            entity_path: str | None = entry.get("entity_path", None)
            component_type: str | None = entry.get("component_type", None)
            property_name: str | None = entry.get("property_name", None)
            prop_name: str | None = entry.get("name", None)

            matched_prop = None
            matched_group_prefix = group_prefix
            matched_key_prop_name = property_name or prop_name or ""
            matched_group = None

            if entity_path is not None and property_name is not None:
                matched_prop, matched_group_prefix, matched_key_prop_name, matched_group = self._find_prop_v2(
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

            key = ActorPropertyKey(actor_path, matched_group_prefix, matched_key_prop_name, prop_type)
            try:
                await SceneEditRequestBus().set_property(key, value, undo=False, source="layout")
            except Exception as e:
                logger.warning("应用属性失败 %s.%s: %s", group_prefix, prop_name, e)

    async def set_flycamera_transform(self):
        await SceneEditRequestBus().set_flycamera_transform(self.flycamera_transform)

    async def get_flycamera_transform(self):
        remote_scene = get_remote_scene()
        self.flycamera_transform = await remote_scene.get_flycamera_transform()