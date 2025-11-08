from orcalab.event_bus import create_event_bus


class PanelRequest:

    def open_panel(self, name: str) -> None:
        pass

    def close_panel(self, name: str) -> None:
        pass

    def open_panel_area(self, name: str) -> None:
        pass

    def close_panel_area(self, name: str) -> None:
        pass


PanelRequestBus = create_event_bus(PanelRequest)


class PanelNotification:
    pass


PanelNotificationBus = create_event_bus(PanelNotification)
