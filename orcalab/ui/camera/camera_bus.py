from typing import List
from orcalab.event_bus import create_event_bus
from orcalab.math import Transform
from orcalab.ui.camera.camera_brief import CameraBrief


class CameraRequest:
    async def set_viewport_camera(self, camera_index: int) -> None:
        pass

    async def get_viewport_camera_transform(self, output: list[Transform]) -> Transform:
        pass


CameraRequestBus = create_event_bus(CameraRequest)


class CameraNotification:
    def on_viewport_camera_changed(self, camera_index: int) -> None:
        pass

    def on_cameras_changed(
        self, cameras: List[CameraBrief], viewport_camera_index: int
    ) -> None:
        pass


CameraNotificationBus = create_event_bus(CameraNotification)
