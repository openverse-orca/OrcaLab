from orcalab.actor import AssetActor
from orcalab.event_bus import create_event_bus
from typing import List

from orcalab.math import Transform

class ApplicationRequest:

    def get_cache_folder(self, output: List[str]) -> None:
        pass
    
    async def add_item_to_scene(self, asset_path: str, output: List[AssetActor] = None) -> None:
        pass

    async def add_item_to_scene_with_transform(self, asset_path: str, transform: Transform, output: List[AssetActor] = None) -> None:
        pass

ApplicationRequestBus = create_event_bus(ApplicationRequest)


class ApplicationNotification:
    pass


ApplicationNotificationBus = create_event_bus(ApplicationNotification)
