from enum import Enum
from orcalab.event_bus import create_event_bus


class ManipulatorType(Enum):
    Translate = 0
    Rotate = 1
    Scale = 2


class StateSyncRequest:
    async def set_manipulator_type(self, type: ManipulatorType):
        pass


StateSyncRequestBus = create_event_bus(StateSyncRequest)


class StateSyncNotification:

    def on_manipulator_type_changed(self, type: ManipulatorType):
        pass


StateSyncNotificationBus = create_event_bus(StateSyncNotification)
