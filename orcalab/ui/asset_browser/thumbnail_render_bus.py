from orcalab.event_bus import create_event_bus

class ThumbnailRenderRequest:
    async def render_thumbnail(self, asset_paths: list[str]) -> None:
        pass

ThumbnailRenderRequestBus = create_event_bus(ThumbnailRenderRequest)


class ThumbnailRenderNotification:
    async def on_thumbnail_rendered(self, asset_path: str, thumbnail_files: list[str]) -> None:
        pass

ThumbnailRenderNotificationBus = create_event_bus(ThumbnailRenderNotification)