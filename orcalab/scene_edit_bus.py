from typing import Any, List, Tuple

from orcalab.actor import BaseActor, GroupActor
from orcalab.actor_property import ActorPropertyKey
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

    async def add_actor(
        self,
        actor: BaseActor,
        parent_actor: GroupActor | Path,
        undo: bool = True,
        source: str = "",
    ):
        pass

    def can_delete_actor(self, out: List[bool], actor: BaseActor | Path):
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

    # Property Editing
    #
    # --- Non-Drag Pattern:
    #
    # set_property(undo=True)
    #
    # --- Drag Pattern:
    #
    # start_change_property()
    # set_property(undo=False)
    # ...
    # set_property(undo=False)
    # set_property(undo=True)
    # end_change_property()
    #

    async def set_property(
        self,
        property_key: ActorPropertyKey,
        value: Any,
        undo: bool,
        source: str = "",
    ):
        pass

    def start_change_property(self, property_key: ActorPropertyKey):
        pass

    def end_change_property(self, property_key: ActorPropertyKey):
        pass

    def start_change_transform(self, actor: BaseActor | Path):
        pass

    def end_change_transform(self, actor: BaseActor | Path):
        pass

    async def set_transform(
        self,
        actor: BaseActor | Path,
        transform: Transform,
        local: bool,
        undo: bool = True,
        source: str = "",
    ) -> None:
        pass

    def get_editing_actor_path(self, out: List[Path]):
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

    async def on_property_changed(
        self,
        property_key: ActorPropertyKey,
        value: Any,
        source: str,
    ):
        pass

    async def get_camera_png(self, camera_name: str, png_path: str, png_name: str):
        pass

    async def get_actor_asset_aabb(self, actor_path: Path, output: List[float]):
        pass


SceneEditNotificationBus = create_event_bus(SceneEditNotification)
