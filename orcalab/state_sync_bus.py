from enum import Enum
from orcalab.event_bus import create_event_bus


class ManipulatorType(Enum):
    Translate = 0
    Rotate = 1
    Scale = 2


class StateSyncRequest:
    async def set_manipulator_type(self, type: ManipulatorType):
        pass

    async def set_debug_draw(self, enabled: bool):
        pass


    async def set_runtime_grab(self, enabled: bool):
        pass


StateSyncRequestBus = create_event_bus(StateSyncRequest)


class StateSyncNotification:

    def on_manipulator_type_changed(self, type: ManipulatorType):
        pass

    def on_debug_draw_changed(self, enabled: bool):
        pass

    def on_runtime_grab_changed(self, enabled: bool):
        pass

StateSyncNotificationBus = create_event_bus(StateSyncNotification)
