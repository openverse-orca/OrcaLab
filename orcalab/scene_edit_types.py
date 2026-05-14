from orcalab.actor import BaseActor

from orcalab.path import Path

class AddActorRequest:
    def __init__(
        self,
        actor: BaseActor,
        parent_path: Path,
        child_pos: int = -1,
        actor_template: BaseActor | None = None,
    ):
        self.actor = actor
        self.parent_path = parent_path
        # Optional: position to insert the new actor among siblings. -1 for append.
        self.child_pos = child_pos
        # Optional: if set, the new actor will be initialized with the same properties as this template actor.
        self.actor_template = actor_template
