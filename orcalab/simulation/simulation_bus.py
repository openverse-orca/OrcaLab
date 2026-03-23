from enum import Enum, auto
from orcalab.event_bus import create_event_bus
from typing import List


class SimulationState(Enum):
    Stopped = auto()
    Launching = auto()
    Running = auto()
    Failed = auto()


class SimulationRequest:
    async def start_simulation(self, program_name: str | None = None) -> None:
        pass

    async def stop_simulation(self) -> None:
        pass

    def get_simulation_state(self, out: List[SimulationState]) -> None:
        pass


SimulationRequestBus = create_event_bus(SimulationRequest)


class SimulationNotification:
    async def on_simulation_state_changed(
        self, old_state: SimulationState, new_state: SimulationState
    ) -> None:
        pass


SimulationNotificationBus = create_event_bus(SimulationNotification)
