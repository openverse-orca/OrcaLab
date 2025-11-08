from orcalab.event_bus import create_event_bus
from orcalab.ui.user_event import KeyCode, MouseAction, MouseButton, KeyAction


class UserEventRequest:
    def queue_mouse_event(
        self,
        x: float,
        y: float,
        button: MouseButton,
        action: MouseAction,
    ) -> None:
        pass

    def queue_mouse_wheel_event(self, delta: int) -> None:
        pass

    def queue_key_event(self, key: KeyCode, action: KeyAction) -> None:
        pass


UserEventRequestBus = create_event_bus(UserEventRequest)


class UserEventNotification:
    pass


UserEventNotificationBus = create_event_bus(UserEventNotification)
