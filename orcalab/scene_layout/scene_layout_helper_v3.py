from dataclasses import dataclass
import json
import logging
import math
from typing import Any, Dict, List, Tuple, TypeAlias

import numpy as np

from orcalab.actor import AssetActor, BaseActor, GroupActor
from orcalab.actor_property import ActorPropertyType, PropertyOverride
from orcalab.entity_path import EntityPath, NameWithIndex
from orcalab.i18n import tr
from orcalab.local_scene import LocalScene
from orcalab.transform import Transform
from orcalab.metadata_service_bus import MetadataServiceRequestBus
from orcalab.path import Path
from orcalab.remote_scene import RemoteScene
from orcalab.scene_edit_bus import SceneEditRequestBus
from orcalab.scene_edit_types import AddActorRequest

logger = logging.getLogger(__name__)


@dataclass
class _PropertyOverride:
    property_name: str
    type: ActorPropertyType
    value: Any


_GroupKey: TypeAlias = Tuple[str, int]
_GroupOverridesDict: TypeAlias = Dict[_GroupKey, List[_PropertyOverride]]
_EntityOverridesDict: TypeAlias = Dict[EntityPath, _GroupOverridesDict]


@dataclass
class _ActorData:
    name: str
    path: str
    actor_type: str
    transform: Transform
    is_visible: bool
    is_parent_visible: bool
    is_locked: bool
    is_parent_locked: bool
    asset_path: str
    entity_overrides: _EntityOverridesDict
    children: List["_ActorData | None"]


@dataclass
class _LayoutData:
    version: str
    viewport_camera_transform: Transform | None
    actors: List[_ActorData]


def _to_list(v):
    return v.tolist() if hasattr(v, "tolist") else v


def _parse_dict(dict_data: dict, key: str) -> dict | None:
    if not isinstance(dict_data, dict):
        return None
    if key not in dict_data:
        return None

    data = dict_data[key]
    if not isinstance(data, dict):
        return None
    return data


def _parse_list(dict_data: dict, key: str) -> list | None:
    if not isinstance(dict_data, dict):
        return None
    if key not in dict_data:
        return None
    data = dict_data[key]
    if not isinstance(data, list):
        return None
    return data


def _parse_int(int_data: Any) -> int | None:
    try:
        return int(int_data)
    except ValueError:
        return None


def _parse_float(float_data: Any) -> float | None:
    try:
        value = float(float_data)
        if math.isnan(value):
            return None
        return value
    except ValueError:
        return None


def _parse_string(string_data: Any) -> str | None:
    if isinstance(string_data, str):
        return string_data
    return None


def _parse_bool(bool_data: Any) -> bool | None:
    if isinstance(bool_data, bool):
        return bool_data
    return None


def _parse_float_list(list_data: Any, n: int) -> List[float]:
    if isinstance(list_data, list) and len(list_data) == n:
        result: List[float] = []
        for item_data in list_data:
            value = _parse_float(item_data)
            if value is None:
                return [0.0] * n
            result.append(value)
        return result
    return [0.0] * n


def _entity_path_to_segments(entity_path: EntityPath) -> list[dict]:
    segments: list[dict] = []
    for seg in entity_path._segments:
        if seg.name == EntityPath.root_name:
            continue
        segments.append({"name": seg.name, "index": seg.index})
    return segments


def _parse_transform_dict(transform_data: dict) -> Transform:
    transform = Transform()
    if "position" in transform_data:
        floats = _parse_float_list(transform_data["position"], 3)
        transform.position = np.array(floats, dtype=float).reshape(3)
    if "rotation" in transform_data:
        floats = _parse_float_list(transform_data["rotation"], 4)
        transform.rotation = np.array(floats, dtype=float)
    if "scale" in transform_data:
        value = _parse_float(transform_data["scale"])
        if value is not None:
            transform.scale = value
    return transform


def _parse_entity_path(entity_path_list: Any) -> EntityPath:
    if not isinstance(entity_path_list, list):
        return EntityPath()

    segments: list[NameWithIndex] = [NameWithIndex(EntityPath.root_name, 0)]

    for seg in entity_path_list:
        if not isinstance(seg, dict):
            return EntityPath()
        if "name" not in seg or "index" not in seg:
            return EntityPath()
        if not isinstance(seg["name"], str) or not isinstance(seg["index"], int):
            return EntityPath()
        segments.append(NameWithIndex(seg["name"], seg["index"]))

    return EntityPath(segments)


def _parse_property_type(prop_type_data: Any) -> ActorPropertyType | None:
    prop_type = _parse_string(prop_type_data)
    if prop_type is None:
        return None
    if prop_type == "bool":
        return ActorPropertyType.BOOL
    elif prop_type == "float":
        return ActorPropertyType.FLOAT
    elif prop_type == "int":
        return ActorPropertyType.INTEGER
    elif prop_type == "string":
        return ActorPropertyType.STRING
    elif prop_type == "enum":
        return ActorPropertyType.ENUM
    elif prop_type == "asset":
        return ActorPropertyType.ASSET
    logger.error("unknow type")
    return None

def _property_type_to_string(prop_type: ActorPropertyType) -> str:
    if prop_type == ActorPropertyType.BOOL:
        return "bool"
    elif prop_type == ActorPropertyType.FLOAT:
        return "float"
    elif prop_type == ActorPropertyType.INTEGER:
        return "int"
    elif prop_type == ActorPropertyType.STRING:
        return "string"
    elif prop_type == ActorPropertyType.ENUM:
        return "enum"
    elif prop_type == ActorPropertyType.ASSET:
        return "asset"
    logger.error("unknow type")
    return ""


def _parse_value(prop_type: ActorPropertyType, value_data: Any) -> Any | None:
    if prop_type == ActorPropertyType.BOOL:
        return _parse_bool(value_data)
    elif prop_type == ActorPropertyType.FLOAT:
        return _parse_float(value_data)
    elif prop_type == ActorPropertyType.INTEGER:
        return _parse_int(value_data)
    elif prop_type == ActorPropertyType.STRING:
        return _parse_string(value_data)
    elif prop_type == ActorPropertyType.ENUM:
        return _parse_string(value_data)
    elif prop_type == ActorPropertyType.ASSET:
        return _parse_string(value_data)
    return None


class SceneLayoutV3Parser:
    def __init__(self) -> None:
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.data = _LayoutData(
            version="",
            viewport_camera_transform= None,
            actors=[],
        )

    def parse(self, layout_data: dict) -> _LayoutData | None:
        version = _parse_string(layout_data["version"])
        if version is None:
            self.warnings.append("version is missing")
            return None
        else:
            self.data.version = version

        if "viewport_camera_transform" in layout_data:
            self.data.viewport_camera_transform = _parse_transform_dict(
                layout_data["viewport_camera_transform"]
            )

        if "actors" in layout_data:
            self._parse_actors(layout_data["actors"])

        return self.data

    def _parse_actors(self, actors_data: list) -> None:
        if not isinstance(actors_data, list):
            return

        for actor_dict in actors_data:
            actor_data = self._parse_actor_dict(actor_dict)
            if actor_data is None:
                continue
            self.data.actors.append(actor_data)

    def _parse_actor_dict(self, actor_data: Any) -> _ActorData | None:
        if not isinstance(actor_data, dict):
            return None

        fields = ["name", "path", "type"]
        if not all(field in actor_data for field in fields):
            return None

        name = _parse_string(actor_data["name"])
        if name is None:
            return None
        path = _parse_string(actor_data["path"])
        if path is None:
            return None
        type = _parse_string(actor_data["type"])
        if type is None:
            return None

        transform = Transform()
        if "transform" in actor_data:
            transform = _parse_transform_dict(actor_data["transform"])

        is_visible = True
        is_parent_visible = True
        is_locked = False
        is_parent_locked = False

        if "is_visible" in actor_data:
            _is_visible = _parse_bool(actor_data["is_visible"])
            if _is_visible is not None:
                is_visible = _is_visible
        if "is_parent_visible" in actor_data:
            _is_parent_visible = _parse_bool(actor_data["is_parent_visible"])
            if _is_parent_visible is not None:
                is_parent_visible = _is_parent_visible
        if "is_locked" in actor_data:
            _is_locked = _parse_bool(actor_data["is_locked"])
            if _is_locked is not None:
                is_locked = _is_locked
        if "is_parent_locked" in actor_data:
            _is_parent_locked = _parse_bool(actor_data["is_parent_locked"])
            if _is_parent_locked is not None:
                is_parent_locked = _is_parent_locked

        asset_path = ""
        if "asset_path" in actor_data:
            _asset_path = _parse_string(actor_data["asset_path"])
            if _asset_path is not None:
                asset_path = _asset_path

        entity_overrides_dict: _EntityOverridesDict = {}
        entity_overrides = _parse_list(actor_data, "entity_overrides")
        if entity_overrides is not None:
            self._parse_entity_overrides_dict(entity_overrides_dict, entity_overrides)

        _actor_data = _ActorData(
            name=name,
            path=path,
            actor_type=type,
            transform=transform,
            is_visible=is_visible,
            is_parent_visible=is_parent_visible,
            is_locked=is_locked,
            is_parent_locked=is_parent_locked,
            asset_path=asset_path,
            entity_overrides=entity_overrides_dict,
            children=[],
        )
        
        children_list = _parse_list(actor_data, "children")
        if children_list is not None:
            for child_dict in children_list:
                child = self._parse_actor_dict(child_dict)
                if child is None:
                    continue
                _actor_data.children.append(child)

        return _actor_data

    def _parse_entity_overrides_dict(
        self, parent_dict: _EntityOverridesDict, entity_overrides_list: list
    ):
        for entity_override_dict in entity_overrides_list:
            fields = ["entity_path", "group_overrids"]
            if not all(field in entity_override_dict for field in fields):
                continue
            entity_path = _parse_entity_path(entity_override_dict["entity_path"])
            if entity_path.empty():
                continue

            group_override_list = _parse_list(entity_override_dict, "group_overrids")
            if group_override_list is None:
                continue

            _group_override_dict: _GroupOverridesDict = {}
            self._parse_group_override_dict(_group_override_dict, group_override_list)
            parent_dict[entity_path] = _group_override_dict

    def _parse_group_override_dict(
        self, parent_dict: _GroupOverridesDict, group_override_list: list
    ):
        for group_override_dict in group_override_list:
            if not isinstance(group_override_dict, dict):
                return

            fields = ["type_id", "type_index", "property_overrides"]
            if not all(field in group_override_dict for field in fields):
                return

            type_id = _parse_string(group_override_dict["type_id"])
            if type_id is None:
                return
            if not type_id.startswith("{") or not type_id.endswith("}"):
                return

            type_index = _parse_int(group_override_dict["type_index"])
            if type_index is None:
                return

            prop_override_list = _parse_list(group_override_dict, "property_overrides")
            if prop_override_list is None:
                return

            group_key = (type_id, type_index)
            _prop_override_list: List[_PropertyOverride] = []
            self._parse_property_override_list(_prop_override_list, prop_override_list)
            parent_dict[group_key] = _prop_override_list

    def _parse_property_override_list(
        self, out_list: List[_PropertyOverride], prop_override_list: list
    ):
        for prop_override_dict in prop_override_list:
            if not isinstance(prop_override_dict, dict):
                return

            fields = ["name", "type", "value"]
            if not all(field in prop_override_dict for field in fields):
                continue

            name = _parse_string(prop_override_dict["name"])
            if name is None:
                continue

            prop_type = _parse_property_type(prop_override_dict["type"])
            if prop_type is None:
                continue

            value = _parse_value(prop_type, prop_override_dict["value"])
            if value is None:
                continue

            out_list.append(_PropertyOverride(name, prop_type, value))


class SceneLayoutV3Serializer:
    def __init__(self) -> None:
        pass

    def serialize(self, layout_data: _LayoutData) -> dict:
        data: dict[str, Any] = {
            "version": layout_data.version,
        }

        if layout_data.viewport_camera_transform is not None:
            data["viewport_camera_transform"] = {
                "position": _to_list(layout_data.viewport_camera_transform.position),
                "rotation": _to_list(layout_data.viewport_camera_transform.rotation),
            }

        if layout_data.actors:
            data["actors"] = [
                self._actor_to_layout_dict(actor) for actor in layout_data.actors
            ]

        return data

    def _actor_to_layout_dict(self, actor: _ActorData) -> dict:
        data: dict[str, Any] = {
            "name": actor.name,
            "path": actor.path,
            "type": actor.actor_type,
            "transform": {
                "position": _to_list(actor.transform.position),
                "rotation": _to_list(actor.transform.rotation),
                "scale": actor.transform.scale,
            },
        }

        if not actor.is_visible:
            data["is_visible"] = actor.is_visible

        if not actor.is_parent_visible:
            data["is_parent_visible"] = actor.is_parent_visible

        if actor.is_locked:
            data["is_locked"] = actor.is_locked

        if actor.is_parent_locked:
            data["is_parent_locked"] = actor.is_parent_locked

        if actor.asset_path:
            data["asset_path"] = actor.asset_path

        if actor.entity_overrides:
            entity_overrides = self._to_entity_overrides_list(actor.entity_overrides)
            if entity_overrides:
                data["entity_overrides"] = entity_overrides

        if actor.children:
            children = []
            for child in actor.children:
                if child is None:
                    continue
                children.append(self._actor_to_layout_dict(child))
            data["children"] = children

        return data

    def _to_entity_overrides_list(
        self, entity_overrides_dict: _EntityOverridesDict
    ) -> List[dict]:
        entity_overrides = []
        for entity_path, groups_dict in entity_overrides_dict.items():

            d = self._to_entity_overrides_dict(entity_path, groups_dict)
            if d:
                entity_overrides.append(d)
        return entity_overrides

    def _to_entity_overrides_dict(
        self, entity_path: EntityPath, groups_dict: _GroupOverridesDict
    ) -> dict:
        entity_segments = _entity_path_to_segments(entity_path)
        group_overrides = []

        for group_key, propeties_list in groups_dict.items():
            d = self._to_group_overrides_dict(group_key, propeties_list)
            if d:
                group_overrides.append(d)

        if not group_overrides:
            return {}

        return {
            "entity_path": entity_segments,
            "group_overrids": group_overrides,
        }

    def _to_group_overrides_dict(
        self, group_key: _GroupKey, propeties_list: List[_PropertyOverride]
    ) -> dict:
        property_overrides = [self._to_override_dict(prop) for prop in propeties_list]

        if not property_overrides:
            return {}

        return {
            "type_id": group_key[0],
            "type_index": group_key[1],
            "property_overrides": property_overrides,
        }

    def _to_override_dict(self, override: _PropertyOverride) -> dict:
        return {
            "name": override.property_name,
            "value": override.value,
            "type": _property_type_to_string(override.type),
        }


class SceneLayoutHelperV3:
    VERSION = "3.0"

    def __init__(self, local_scene: LocalScene, remote_scene: RemoteScene) -> None:
        self.local_scene = local_scene
        self.remote_scene = remote_scene
        self.viewport_camera_transform = Transform()

    async def save_scene_layout(self, filename: str):
        layout_data = await self._create_layout_data()

        serializer = SceneLayoutV3Serializer()
        layout_dict = serializer.serialize(layout_data)

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(layout_dict, f, indent=4, ensure_ascii=False)
        logger.info("场景布局(v3)已保存至 %s", filename)

    async def create_empty_layout(self, file_path: str):
        layout_data = _LayoutData(
            version=self.VERSION,
            viewport_camera_transform=self.viewport_camera_transform,
            actors=[],
        )

        serializer = SceneLayoutV3Serializer()
        layout_dict = serializer.serialize(layout_data)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(layout_dict, f, indent=4)

    async def clear_layout(self):
        children = list(self.local_scene.root_actor.children)
        if children:
            await SceneEditRequestBus().delete_actors(children, undo=False)

    async def load_scene_layout(
        self, layout_dict: dict, errors: List[str], warnings: List[str]
    ):
        version = layout_dict.get("version", "")
        if version != self.VERSION:
            msg = tr(
                "场景布局(v3)版本不匹配，期望 {expected}，实际 {actual}",
                expected=self.VERSION,
                actual=version,
            )
            logger.error(msg)
            errors.append(msg)
            return False

        parser = SceneLayoutV3Parser()
        layout_data = parser.parse(layout_dict)
        if layout_data is None:
            msg = tr("场景布局(v3)文件格式错误")
            logger.error(msg)
            errors.append(msg)
            return False

        await self.clear_layout()

        requests: List[AddActorRequest] = []
        for actor_data in layout_data.actors:
            self._collect_layout_requests(
                requests, errors, warnings, actor_data, Path.root_path()
            )
        await SceneEditRequestBus().add_actors(requests, undo=False, source="layout")

        if layout_data.viewport_camera_transform is not None:
            await SceneEditRequestBus().set_flycamera_transform(
                layout_data.viewport_camera_transform
            )

    async def _create_layout_data(self) -> _LayoutData:
        viewport_camera_transform = await self.remote_scene.get_flycamera_transform()
        actors = []
        for child in self.local_scene.root_actor.children:
            actors.append(await self._create_actor_data(child))

        return _LayoutData(
            version=self.VERSION,
            viewport_camera_transform=viewport_camera_transform,
            actors=actors,
        )

    async def _create_actor_data(self, actor: BaseActor) -> _ActorData:
        actor_path = self.local_scene.get_actor_path(actor)
        assert actor_path is not None, "Actor must have a path"

        actor_type = "BaseActor"
        asset_path = ""

        children: List[_ActorData | None] = []
        if isinstance(actor, GroupActor):
            actor_type = "GroupActor"
            children = [
                await self._create_actor_data(child) for child in actor.children
            ]
        elif isinstance(actor, AssetActor):
            actor_type = "AssetActor"
            asset_path = actor.asset_path

        entity_overrides = await self._collect_entity_overrides(actor_path)

        actor_data = _ActorData(
            name=actor.name,
            path=actor_path.string(),
            actor_type=actor_type,
            transform=actor.transform,
            is_visible=actor.is_visible,
            is_parent_visible=actor.is_parent_visible,
            is_locked=actor.is_locked,
            is_parent_locked=actor.is_parent_locked,
            asset_path=asset_path,
            entity_overrides=entity_overrides,
            children=children,
        )

        return actor_data

    async def _collect_entity_overrides(self, actor_path: Path) -> _EntityOverridesDict:
        overrides = await self.remote_scene.get_actor_overrides(actor_path)
        if not overrides:
            return {}

        entity_overrides_dict: _EntityOverridesDict = {}
        for override in overrides:
            if override.entity_path not in entity_overrides_dict:
                entity_overrides_dict[override.entity_path] = {}
            groups_dict = entity_overrides_dict[override.entity_path]

            group_key = (override.component_type_id, override.component_type_index)
            if group_key not in groups_dict:
                groups_dict[group_key] = []
            propeties_list = groups_dict[group_key]

            propeties_list.append(
                _PropertyOverride(
                    property_name=override.property_name,
                    value=override.value,
                    type=override.property_type,
                )
            )

        return entity_overrides_dict

    def _collect_layout_requests(
        self,
        requests: List[AddActorRequest],
        errors: List[str],
        warnings: List[str],
        actor_data: _ActorData,
        parent_path: Path,
    ):
        name = actor_data.name
        if not Path.is_valid_name(name):
            msg = tr("跳过 {name}, Actor名称{name}非法。", name=name)
            warnings.append(msg)
            logger.warning(msg)
            return

        current_path = parent_path / actor_data.name

        if actor_data.actor_type == "AssetActor":
            asset_path = actor_data.asset_path
            output = []
            MetadataServiceRequestBus().get_asset_info(asset_path, output)
            if not output or output[0] is None:
                msg = tr(
                    "跳过 {path}, 资产{asset_path}不存在。",
                    path=current_path,
                    asset_path=asset_path,
                )
                warnings.append(msg)
                logger.warning(msg)
                return
            actor = AssetActor(name=name, asset_path=asset_path)
        else:
            actor = GroupActor(name=name)

        actor.transform = actor_data.transform
        actor.is_visible = actor_data.is_visible
        actor.is_parent_visible = actor_data.is_parent_visible
        actor.is_locked = actor_data.is_locked
        actor.is_parent_locked = actor_data.is_parent_locked

        property_overrides: List[PropertyOverride] = []
        if actor_data.entity_overrides:
            for entity_path, group_dict in actor_data.entity_overrides.items():
                if entity_path.empty():
                    continue

                for group_key, propeties_list in group_dict.items():
                    component_type_id = group_key[0]
                    component_type_index = group_key[1]

                    if not component_type_id:
                        continue

                    for prop in propeties_list:
                        property_overrides.append(
                            PropertyOverride(
                                entity_id=0,
                                entity_path=entity_path,
                                component_type_id=component_type_id,
                                component_type_index=component_type_index,
                                property_name=prop.property_name,
                                property_type=prop.type,
                                value=prop.value,
                            )
                        )

        request = AddActorRequest(actor, parent_path, -1, property_overrides)
        requests.append(request)

        if isinstance(actor, GroupActor):
            for child_data in actor_data.children:
                if child_data is None:
                    continue
                self._collect_layout_requests(
                    requests,
                    errors,
                    warnings,
                    child_data,
                    current_path,
                )
