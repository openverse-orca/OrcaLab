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

    async def post_asset_subscribe(self, asset_package_id: str, output: List[str] = None) -> str:
        pass

    async def post_asset_unsubscribe(self, asset_package_id: str, output: List[str] = None) -> str:
        pass

    async def get_asset_subscription_status(self, asset_package_id: str, output: List[str] = None) -> str:
        pass

    async def get_my_metadata(self, output: List[str] = None) -> str:
        pass
    
    async def get_asset_detail(self, asset_id: str, output: List[str] = None) -> str:
        pass
    
    async def post_generate_task(self, task_data: dict, output: List[str] = None) -> str:
        pass
    
    async def get_generate_task_status(self, task_id: str, output: List[str] = None) -> str:
        pass
    
    async def get_user_generate_tasks(self, output: List[str] = None) -> str:
        pass
    
    async def post_upload_generate_usdz(self, task_data: dict, output: List[str] = None) -> str:
        pass
    
    async def post_cancel_asset_zip(self, task_id: str, output: List[str] = None) -> str:
        pass
    
    async def post_check_asset_version(self, version_data: dict, output: List[str] = None) -> str:
        pass
    
    async def post_upload_asset_zip(self, upload_data: dict, output: List[str] = None) -> str:
        pass
    
    async def post_upload_usdz(self, upload_data: dict, output: List[str] = None) -> str:
        pass
    
    async def post_upload_xml(self, upload_data: dict, output: List[str] = None) -> str:
        pass
    
    async def get_task_chain_progress(self, task_chain_id: str, output: List[str] = None) -> str:
        pass
    
    async def post_save_asset_draft(self, task_id: str, draft_data: dict, output: List[str] = None) -> str:
        pass
    
    async def delete_asset(self, asset_id: str, output: List[str] = None) -> str:
        pass
    
    async def search_assets(self, search_data: dict, output: List[str] = None) -> str:
        pass
    
    def is_admin(self) -> bool:
        pass

HttpServiceRequestBus = create_event_bus(HttpServiceRequest)