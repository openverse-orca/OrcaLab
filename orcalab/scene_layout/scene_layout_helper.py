import math
from typing import List
import numpy as np
from orcalab.actor import AssetActor, BaseActor, GroupActor
from orcalab.local_scene import LocalScene
import json

from orcalab.math import Transform
from orcalab.path import Path
from orcalab.scene_edit_bus import SceneEditRequestBus


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

    def save_layout(self, root_actor: GroupActor, file_path: str):
        layout_dict = {
            "version": self.version,
        }
        self.actor_to_dict(layout_dict, root_actor)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(layout_dict, f, indent=4)

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

    async def load_layout(self, file_path: str) -> dict:
        with open(file_path, "r", encoding="utf-8") as f:
            layout_dict = json.load(f)

        actors: List[_ActorData] = []
        self.deserialize_actors(actors, layout_dict, None)

        await self.clear_layout()
        await self._load_layout(actors)

        return layout_dict

    async def clear_layout(self):
        for actor in self.local_scene.root_actor.children:
            await SceneEditRequestBus().delete_actor(actor, undo=False)

    def serialize_transform(self, transform: Transform) -> dict:
        data = {}
        data["position"] = compact_array(transform.position.tolist())
        data["rotation"] = compact_array(transform.rotation.tolist())
        data["scale"] = transform.scale
        return data

    def deserialize_float3(self, text: str) -> List[float]:
        l = parse_compact_array(text)
        if len(l) != 3 or any(math.isnan(x) for x in l):
            return [0.0, 0.0, 0.0]
        return l

    def deserialize_transform(self, data: dict) -> Transform:
        transform = Transform()

        if "position" and data.get("position") is not None:
            position = self.deserialize_float3(data["position"])
            transform.position = np.array(position, dtype=float)

        if "rotation" and data.get("rotation") is not None:
            rotation = self.deserialize_float3(data["rotation"])
            transform.rotation = np.array(rotation, dtype=float)

        if "scale" in data and data.get("scale") is not None:
            scale = float(data["scale"])
            if not math.isnan(scale):
                transform.scale = scale
        return transform

    def actor_to_dict(self, data: dict, actor: BaseActor):
        actor_path = self.local_scene.get_actor_path(actor)
        assert actor_path is not None

        data["name"] = actor.name
        data["path"] = actor_path.string()
        data["transform"] = self.serialize_transform(actor.transform)

        if isinstance(actor, AssetActor):
            data["type"] = "AssetActor"
            data["asset_path"] = actor.asset_path

        if isinstance(actor, GroupActor):
            data["type"] = "GroupActor"

            children = []
            for child in actor.children:
                _data = {}
                self.actor_to_dict(_data, child)
                children.append(_data)

            data["children"] = children

    def _assert_field_type(self, data: dict, field: str, expected_type: type):
        if field not in data or not isinstance(data[field], expected_type):
            raise ValueError(f"Invalid or missing '{field}' field.")

    def deserialize_actors(
        self,
        actors: List[_ActorData],
        data: dict,
        parent_actor: BaseActor | None = None,
    ):

        self._assert_field_type(data, "name", str)
        self._assert_field_type(data, "path", str)
        self._assert_field_type(data, "type", str)
        self._assert_field_type(data, "transform", dict)

        name = data["name"]
        path = Path(data["path"])
        actor_type = data["type"]
        transform = self.deserialize_transform(data["transform"])

        if actor_type == "AssetActor":
            self._assert_field_type(data, "asset_path", str)
            asset_path = data["asset_path"]
            actor = AssetActor(name=name, asset_path=asset_path)
        else:
            actor = GroupActor(name=name)

        actor.transform = transform

        actors.append(_ActorData(actor, path, parent_actor))

        if isinstance(actor, GroupActor):
            for child_data in data.get("children", []):
                self.deserialize_actors(actors, child_data, actor)

    async def _load_layout(self, actor_datas: List[_ActorData]):
        for actor_data in actor_datas:
            assert isinstance(actor_data.parent, GroupActor)
            if actor_data.path.is_root():
                continue

            await SceneEditRequestBus().add_actor(
                actor=actor_data.actor, parent_actor=actor_data.parent
            )
