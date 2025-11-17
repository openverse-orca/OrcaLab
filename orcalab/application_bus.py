from orcalab.actor import AssetActor
from orcalab.event_bus import create_event_bus
from typing import List

from orcalab.local_scene import LocalScene
from orcalab.math import Transform


class ApplicationRequest:
    async def add_item_to_scene(
        self, asset_path: str, output: List[AssetActor] = None
    ) -> None:
        pass

    async def add_item_to_scene_with_transform(
        self, asset_path: str, transform: Transform, output: List[AssetActor] = None
    ) -> None:
        pass

    def get_local_scene(self, output: List[LocalScene]):
        pass


ApplicationRequestBus = create_event_bus(ApplicationRequest)


class ApplicationNotification:
    pass


ApplicationNotificationBus = create_event_bus(ApplicationNotification)


def get_local_scene() -> LocalScene:
    local_scene_list = []
    ApplicationRequestBus().get_local_scene(local_scene_list)

    if local_scene_list and isinstance(local_scene_list[0], LocalScene):
        return local_scene_list[0]

    raise RuntimeError("Failed to get LocalScene from ApplicationRequestBus")
