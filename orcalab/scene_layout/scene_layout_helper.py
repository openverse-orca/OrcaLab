import ast
import logging
import math
from typing import List
import numpy as np
from orcalab.actor import AssetActor, BaseActor, GroupActor
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
