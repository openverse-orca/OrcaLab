from orcalab.event_bus import create_event_bus


class SimulationRequest:
    async def start_simulation(self) -> None:
        pass

    async def stop_simulation(self) -> None:
        pass


SimulationRequestBus = create_event_bus(SimulationRequest)


class SimulationNotification:
    async def on_simulation_start(self) -> None:
        pass

    async def on_simulation_stop(self) -> None:
        pass


SimulationNotificationBus = create_event_bus(SimulationNotification)
