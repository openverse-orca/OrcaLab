from orcalab.entity_path import EntityPath
from orcalab.path import Path


class SelectionData:
    """Unified state is easier to manage and makes a lot of operations atomic (GRPC calls and undo/redo)."""

    def __init__(
        self,
        selected_actors: list[Path] | None = None,
        active_actor_path: Path | None = None,
        active_entity_path: EntityPath = EntityPath(),
    ):
        self.selected_actors = selected_actors if selected_actors is not None else []
        self.active_actor_path = active_actor_path
        self.active_entity_path = active_entity_path

    def __eq__(self, other):
        # ALWAYS sort the selected_actors list before comparing!
        if not isinstance(other, SelectionData):
            return False
        return (
            self.selected_actors == other.selected_actors
            and self.active_actor_path == other.active_actor_path
            and self.active_entity_path == other.active_entity_path
        )

    def normalize(self):
        """Normalize the selection data by sorting the selected_actors list."""
        self.selected_actors.sort()

    def normalized(self) -> "SelectionData":
        """Return a new SelectionData instance with normalized data."""
        normalized = SelectionData()
        normalized.selected_actors = sorted(self.selected_actors)
        normalized.active_actor_path = self.active_actor_path
        normalized.active_entity_path = self.active_entity_path
        return normalized

    def clone(self) -> "SelectionData":
        """Return a deep copy of the SelectionData instance."""
        return SelectionData(
            selected_actors=self.selected_actors.copy(),
            active_actor_path=self.active_actor_path,
            active_entity_path=self.active_entity_path,
        )

    def __repr__(self):
        return f"SelectionData(selected_actors={self.selected_actors}, active_actor_path={self.active_actor_path}, active_entity_path={self.active_entity_path})"


class BackendSelectionData:
    """Selection data used in the backend, active_entity is represented by id."""

    def __init__(
        self,
        selected_actors: list[Path] | None = None,
        active_actor: Path | None = None,
        active_entity: int = 0,
    ):
        self.selected_actors = selected_actors if selected_actors is not None else []
        self.active_actor = active_actor
        self.active_entity = active_entity
