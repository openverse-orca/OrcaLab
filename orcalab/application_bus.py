from orcalab.event_bus import create_event_bus
from typing import Any, List, TYPE_CHECKING

from orcalab.math import Transform
from orcalab.actor import AssetActor

if TYPE_CHECKING:
    from orcalab.local_scene import LocalScene
    from orcalab.remote_scene import RemoteScene


class ApplicationRequest:
    async def add_item_to_scene(
        self, asset_path: str, output: List[AssetActor] = None
    ) -> None:
        pass

    async def add_item_to_scene_with_transform(
        self, asset_path: str, transform: Transform, output: List[AssetActor] = None
    ) -> None:
        pass

    def get_local_scene(self, output: List["LocalScene"]):
        pass

    def get_remote_scene(self, output: List["RemoteScene"]):
        pass

    def get_widget(self, name: str, output: List[Any]):
        pass


ApplicationRequestBus = create_event_bus(ApplicationRequest)


class ApplicationNotification:
    pass


ApplicationNotificationBus = create_event_bus(ApplicationNotification)
