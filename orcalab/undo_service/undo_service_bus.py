from typing import List
from orcalab.event_bus import create_event_bus
from orcalab.undo_service.command import BaseCommand


class UndoRequest:
    def can_undo(self, out: List[bool]):
        pass

    def can_redo(self, out: List[bool]):
        pass

    async def undo(self) -> None:
        pass

    async def redo(self) -> None:
        pass

    def add_command(self, command: BaseCommand) -> None:
        pass


UndoRequestBus = create_event_bus(UndoRequest)


class UndoNotification:
    pass


UndoNotificationBus = create_event_bus(UndoNotification)


def can_undo() -> bool:
    out = []
    UndoRequestBus().can_undo(out)
    if len(out) == 0:
        return False

    return out[0]


def can_redo() -> bool:
    out = []
    UndoRequestBus().can_redo(out)
    if len(out) == 0:
        return False

    return out[0]
