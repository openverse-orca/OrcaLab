from orcalab.event_bus import create_event_bus
from typing import List

from orcalab.path import Path


class ApplicationRequest:

    def get_cache_folder(self, output: List[str]) -> None:
        pass

    def set_selection(self, selection: List[Path]) -> None:
        pass

    def undo(self) -> None:
        pass

    def redo(self) -> None:
        pass


ApplicationRequestBus = create_event_bus(ApplicationRequest)


class ApplicationNotification:

    def on_selection_changed(
        self,
        old_selection: List[Path],
        new_selection: List[Path],
        source: str = "",
    ) -> None:
        pass


ApplicationNotificationBus = create_event_bus(ApplicationNotification)
