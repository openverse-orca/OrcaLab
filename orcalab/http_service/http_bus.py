from orcalab.event_bus import create_event_bus
from typing import List, Dict

class HttpServiceRequest:
    async def get_all_metadata(self, output: List[str] = None) -> str:
        pass

    async def get_subscription_metadata(self, output: List[str] = None) -> str:
        pass

    async def get_subscriptions(self, output: List[str] = None) -> str:
        pass

    async def post_asset_thumbnail(self, asset_id: str, thumbnail_path: List[str]) -> None:
        pass

    async def get_asset_thumbnail2cache(self, asset_url: str, asset_save_path: str) -> None:
        pass
    
    async def get_image_url(self, asset_id: str) -> str:
        pass
    
    def is_admin(self) -> bool:
        pass

HttpServiceRequestBus = create_event_bus(HttpServiceRequest)