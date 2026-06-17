from dataclasses import dataclass, field

from orcalab.actor import BaseActor

from orcalab.actor_property import PropertyOverride
from orcalab.path import Path


@dataclass
class AddActorRequest:
    actor: BaseActor
    parent_path: Path
    # Optional: position to insert the new actor among siblings. -1 for append.
    child_pos: int = -1
    # Optional: if set, the new actor will be initialized with the property overrides.
    property_overrides: list[PropertyOverride] = field(default_factory=list)
