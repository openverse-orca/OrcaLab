import ast
import logging
from typing import Any, List
import numpy as np
from orcalab.actor import AssetActor, BaseActor, GroupActor
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
from orcalab.i18n import tr

logger = logging.getLogger(__name__)

def compact_array(arr):
    return "[" + ",".join(str(x) for x in arr) + "]"


def parse_compact_array(s: str):
    s = s.strip().lstrip("[").rstrip("]")
    return [float(x) for x in s.split(",") if x]

class SceneLayoutHelper:
    def __init__(self, local_scene: LocalScene) -> None:
        self.local_scene = local_scene
        self.version = "2.0"
        self.flycamera_transform = Transform()

    async def clear_layout(self):
        children = list(self.local_scene.root_actor.children)
        if children:
            await SceneEditRequestBus().delete_actors(children, undo=False)

    async def load_scene_layout(self, layout_data: dict, errors: List[str]):
        layout_version = layout_data.get("version", "1.0")
        if layout_version not in ("1.0", "2.0"):
            logger.error("不支持的场景布局版本: %s", layout_version)
            return False

        if layout_version == "1.0":
            logger.warning("加载旧版(v1.0)场景布局，建议重新保存以升级到 v2.0 格式")

        await self.clear_layout()
        await self._create_actor_from_scene_layout(layout_data, errors=errors)
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
                            tr(
                                "创建 Actor {name} 失败: {error}, asset_path: {asset_path}",
                                name=actor.name,
                                error=e,
                                asset_path=actor.asset_path,
                            )
                        )
                    else:
                        errors.append(
                            tr(
                                "创建 Actor {name} 失败: {error}",
                                name=actor.name,
                                error=e,
                            )
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

            except Exception as e:
                if isinstance(actor, AssetActor):
                    error_msg = tr(
                        "创建 Actor {name} 后处理失败: {error}, asset_path: {asset_path}",
                        name=actor.name,
                        error=e,
                        asset_path=actor.asset_path,
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
                        tr(
                            "跳过 Actor {name}: 资产不存在, asset_path: {asset_path}",
                            name=name,
                            asset_path=asset_path,
                        )
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

    async def set_flycamera_transform(self):
        await SceneEditRequestBus().set_flycamera_transform(self.flycamera_transform)

    async def get_flycamera_transform(self):
        remote_scene = get_remote_scene()
        self.flycamera_transform = await remote_scene.get_flycamera_transform()
