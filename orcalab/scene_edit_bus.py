from typing import Any, Dict, List, Sequence

from orcalab.actor import BaseActor, GroupActor
from orcalab.actor_property import ActorPropertyKey
from orcalab.math import Transform
from orcalab.event_bus import create_event_bus
from orcalab.path import Path
from orcalab.protos.edit_service_wrapper import CameraDataPNGResult
from orcalab.scene_edit_types import AddActorRequest


class SceneEditRequest:

    async def set_selection(
        self,
        selection: List[Path],
        undo: bool = True,
        source: str = "",
    ) -> None:
        pass

    async def set_active_actor(
        self,
        actor: BaseActor | Path | None,
        undo: bool = True,
        source: str = "",
    ) -> None:
        pass

    async def add_actor(
        self,
        actor: BaseActor,
        parent_actor: GroupActor | Path,
        undo: bool = True,
        source: str = "",
    ):
        pass

    async def add_actors(
        self,
        requests: List[AddActorRequest],
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

    async def delete_actors(
        self,
        actors: Sequence[BaseActor | Path],
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

    async def reparent_actors(
        self,
        actors: Sequence[BaseActor | Path],
        new_parent: BaseActor | Path,
        row: int,
        undo: bool = True,
        source: str = "",
    ):
        pass

    async def move_actors(
        self,
        old_actors: Sequence[BaseActor | Path],
        new_parent_paths: List[Path],
        insert_positions: List[int],
        undo: bool = True,
        source: str = "",
    ):
        pass

    async def duplicate_actors(
        self,
        actors: Sequence[BaseActor | Path],
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

    async def set_transform(
        self,
        actor: BaseActor | Path,
        transform: Transform,
        local: bool,
        undo: bool = True,
        source: str = "",
    ) -> None:
        pass

    async def start_change_transform_batch(self, actors: Sequence[BaseActor | Path]):
        pass

    async def end_change_transform_batch(self, actors: Sequence[BaseActor | Path]):
        pass

    async def set_transform_batch(
        self,
        actors: Sequence[BaseActor | Path],
        transforms: Sequence[Transform],
        undo: bool = True,
        source: str = "",
    ) -> None:
        pass

    def get_editing_actor_path(self, out: List[Path]):
        pass

    def get_all_actors(self, out: List[Dict[Path, BaseActor]]):
        pass

    def get_selection(self, out: List[List[Path]]):
        pass

    async def set_actor_visible(
        self,
        actor: BaseActor | Path,
        visible: bool,
        undo: bool = False,
        source: str = "",
    ):
        pass

    async def set_actor_locked(
        self,
        actor: BaseActor | Path,
        locked: bool,
        undo: bool = False,
        source: str = "",
    ):
        pass

    async def set_selection_and_active_actor(
        self,
        selection: List[Path],
        actor: BaseActor | Path | None,
        undo: bool = True,
        source: str = "",
    ) -> None:
        pass

    async def set_highlight_joint(self, entity_id: int, highlight: bool) -> None:
        """Highlight or unhighlight a single joint in the viewport.
        Args:
            entity_id (int): The EntityId of the joint entity (from TreePropertyNode.name).
            highlight (bool): True to highlight, False to clear.
        """
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

    async def on_active_actor_changed(
        self,
        old_active_actor: Path | None,
        new_active_actor: Path | None,
        source: str = "",
    ) -> None:
        pass

    async def on_transforms_changed(
        self,
        actor_paths: List[Path],
        old_transforms: List[Transform],
        new_transforms: List[Transform],
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

    async def on_actor_added_failed(
        self,
        actor: BaseActor,
        parent_actor_path: Path,
        source: str,
    ):
        pass

    async def before_actor_added_batch(self):
        pass

    async def on_actor_added_batch(self, error: str):
        pass

    async def before_actors_deleted(self, actor_paths: List[Path], source: str):
        pass

    async def on_actors_deleted(self, actor_paths: List[Path], source: str):
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

    async def before_actor_reparented(self):
        pass

    async def on_actor_reparented(self):
        pass

    async def on_property_changed(
        self,
        property_key: ActorPropertyKey,
        value: Any,
        source: str,
    ):
        pass

    async def on_property_read_only_changed(
        self,
        actor_path: Path,
        group_prefix: str,
        property_name: str,
        read_only: bool,
    ):
        pass

    async def get_camera_png(self, camera_name: str, png_path: str, png_name: str):
        pass

    async def get_camera_data_png(
        self,
        camera_name: str,
        png_path: str,
        index: int,
        output: list[CameraDataPNGResult] = None,
    ) -> CameraDataPNGResult:
        pass

    async def get_actor_asset_aabb(self, actor_path: Path, output: List[float]):
        pass

    async def on_actor_visible_changed(
        self, actor_path: Path, paths_to_update: List[Path], visible: bool, source: str
    ):
        pass

    async def on_actor_locked_changed(
        self, actor_path: Path, paths_to_update: List[Path], locked: bool, source: str
    ):
        pass


SceneEditNotificationBus = create_event_bus(SceneEditNotification)
