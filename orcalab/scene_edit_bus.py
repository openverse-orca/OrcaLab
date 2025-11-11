from typing import List, Tuple

from orcalab.actor import BaseActor, GroupActor
from orcalab.math import Transform
from orcalab.event_bus import create_event_bus
from orcalab.path import Path


class SceneEditRequest:

    async def set_selection(
        self,
        selection: List[Path],
        undo: bool = True,
        source: str = "",
    ) -> None:
        """Set the current selection.
        Args:
            selection (List[Path]): The new selection. A list of actor paths. An empty list clears the selection.
            undo (bool): Whether this action should be undoable.
            source (str): The source of the selection change. Useful for avoiding feedback loops.
        """
        pass

    async def set_transform(
        self,
        actor: BaseActor | Path,
        transform: Transform,
        local: bool,
        undo: bool = True,
        source: str = "",
    ) -> None:
        """Set the transform of an actor.

        Args:
            actor (BaseActor | Path): The actor or path of the actor to set the transform for.
            transform (Transform): The new transform to set.
            local (bool): Whether the transform is in local space. If False, the transform is in world space.
            undo (bool): Whether this action should be undoable.
            source (str): The source of the transform change. Useful for avoiding feedback loops.
        """
        pass

    def record_old_transform(self, actor: BaseActor | Path):
        pass

    def get_actor_and_path(
        self, out: List[Tuple[BaseActor, Path]], actor: BaseActor | Path
    ):
        pass

    def can_rename_actor(
        self, out: List[Tuple[bool, str]], actor: BaseActor | Path, new_name: str
    ):
        pass

    async def add_actor(
        self,
        actor: BaseActor,
        parent_actor: GroupActor | Path,
        undo: bool = True,
        source: str = "",
    ):
        pass

    async def delete_actor(
        self,
        actor: BaseActor | Path,
        undo: bool = True,
        source: str = "",
    ):
        pass

    async def rename_actor(
        self,
        actor: BaseActor,
        new_name: str,
        undo: bool = True,
        source: str = "",
    ):
        pass

    async def reparent_actor(
        self,
        actor: BaseActor | Path,
        new_parent: BaseActor | Path,
        row: int,
        undo: bool = True,
        source: str = "",
    ):
        pass


SceneEditRequestBus = create_event_bus(SceneEditRequest)


class SceneEditNotification:

    async def on_selection_changed(
        self,
        old_selection: List[Path],
        new_selection: List[Path],
        source: str = "",
    ) -> None:
        pass

    async def on_transform_changed(
        self,
        actor_path: Path,
        transform: Transform,
        local: bool,
        source: str,
    ) -> None:
        pass

    async def before_actor_added(
        self,
        actor: BaseActor,
        parent_actor_path: Path,
        source: str,
    ):
        pass

    async def on_actor_added(
        self,
        actor: BaseActor,
        parent_actor_path: Path,
        source: str,
    ):
        pass

    async def before_actor_deleted(
        self,
        actor_path: Path,
        source: str,
    ):
        pass

    async def on_actor_deleted(
        self,
        actor_path: Path,
        source: str,
    ):
        pass

    async def before_actor_renamed(
        self,
        actor_path: Path,
        new_name: str,
        source: str,
    ):
        pass

    async def on_actor_renamed(
        self,
        actor_path: Path,
        new_name: str,
        source: str,
    ):
        pass

    async def before_actor_reparented(
        self,
        actor_path: Path,
        new_parent_path: Path,
        row: int,
        source: str,
    ):
        pass

    async def on_actor_reparented(
        self,
        actor_path: Path,
        new_parent_path: Path,
        row: int,
        source: str,
    ):
        pass

    async def get_camera_png(self, camera_name: str, png_path: str, png_name: str):
        pass

    async def get_actor_asset_aabb(self, actor_path: Path, output: List[float] = None):
        pass


SceneEditNotificationBus = create_event_bus(SceneEditNotification)


def get_actor_and_path(actor: BaseActor | Path) -> Tuple[BaseActor, Path]:
    result = []
    SceneEditRequestBus().get_actor_and_path(result, actor)
    if result:
        return result[0]

    raise Exception("Actor not found")


def can_rename_actor(actor: BaseActor | Path, new_name: str) -> Tuple[bool, str]:
    result = []
    SceneEditRequestBus().can_rename_actor(result, actor, new_name)
    if result:
        return result[0]
    return False, "No bus handler"


def make_unique_name(base_name: str, parent: BaseActor | Path) -> str:
    parent, _ = get_actor_and_path(parent)
    if not isinstance(parent, GroupActor):
        raise Exception("Parent must be a GroupActor")

    existing_names = {child.name for child in parent.children}

    counter = 1
    # base_name 可能是一个路径，因此以最后一个 / 之后作为名字
    base_name = base_name.split("/")[-1]
    new_name = f"{base_name}_{counter}"
    while new_name in existing_names:
        counter += 1
        new_name = f"{base_name}_{counter}"

    return new_name
