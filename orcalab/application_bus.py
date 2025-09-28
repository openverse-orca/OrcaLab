from orcalab.event_bus import create_event_bus
from typing import List

class ApplicationRequest:

    def get_cache_folder(self, output: List[str]) -> None:
        pass


ApplicationRequestBus = create_event_bus(ApplicationRequest)


class ApplicationNotification:
    pass


ApplicationNotificationBus = create_event_bus(ApplicationNotification)
