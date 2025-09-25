from orcalab.event_bus import create_event_bus


class AssetServiceRequest:

    async def download_asset_to_file(self, url: str, file: str) -> None:
        pass

    async def download_asset_to_cache(self, url: str) -> None:
        pass


AssetServiceRequestBus = create_event_bus(AssetServiceRequest)


class AssetServiceNotification:

    async def on_asset_downloaded(self, file: str) -> None:
        pass


AssetServiceNotificationBus = create_event_bus(AssetServiceNotification)
