from copy import deepcopy
from typing import Any, List
from orcalab.actor import BaseActor, GroupActor
from orcalab.actor_property import ActorPropertyKey
from orcalab.math import Transform
from orcalab.path import Path
from orcalab.scene_edit_types import AddActorRequest


# 不要存Actor对象，只存Path。
# Actor可能被删除和创建，前后的Actor是不相等的。
# DeleteActorCommand中存的Actor不会再次放到LocalScene中，
# 而是作为模板使用。


class BaseCommand:
    def __init__(self):
        raise NotImplementedError


class CommandGroup(BaseCommand):
    def __init__(self):
        self.commands = []

    def __repr__(self):
        return f"CommandGroup(commands={self.commands})"


class SelectionCommand(BaseCommand):
    def __init__(self, old_selection: list[Path], new_selection: list[Path]):
        self.old_selection = old_selection
        self.new_selection = new_selection

    def __repr__(self):
        return f"SelectionCommand(old_selection={self.old_selection}, new_selection={self.new_selection})"


class AddActorCommand(BaseCommand):
    def __init__(self, requests: List[AddActorRequest]):
        self.requests = requests

    def __repr__(self):
        return f"AddActorCommand({len(self.requests)} requests)"


class DeleteActorCommand(BaseCommand):
    def __init__(self, actors: List[BaseActor], paths: List[Path], rows: List[int]):
        self.actors = actors
        self.parent_paths = paths
        self.rows = rows

    def __repr__(self):
        return f"DeleteActorCommand(paths={self.parent_paths})"


class RenameActorCommand(BaseCommand):
    def __init__(self):
        self.old_path: Path = Path()
        self.new_path: Path = Path()

    def __repr__(self):
        return f"RenameActorCommand(old_path={self.old_path}, new_path={self.new_path})"


class ReparentActorCommand(BaseCommand):
    def __init__(self):
        self.old_path = Path()
        self.old_row = -1
        self.new_path = Path()
        self.new_row = -1

    def __repr__(self):
        return f"ReparentActorCommand(old_path={self.old_path}, old_row={self.old_row}, new_path={self.new_path}, new_row={self.new_row})"


class TransformCommand(BaseCommand):
    def __init__(
        self,
        actor_paths: List[Path],
        old_transforms: List[Transform],
        new_transforms: List[Transform],
        local: bool,
    ):
        self.actor_paths: List[Path] = actor_paths
        self.old_transforms: List[Transform] = old_transforms
        self.new_transforms: List[Transform] = new_transforms
        self.local = local

    def __repr__(self):
        return f"TransformCommand(actor_paths={self.actor_paths})"


class PropertyChangeCommand(BaseCommand):
    def __init__(self, property_key: ActorPropertyKey, old_value: Any, new_value: Any):
        self.property_key = property_key
        self.old_value = old_value
        self.new_value = new_value

    def __repr__(self):
        return f"PropertyChangeCommand(property_key={self.property_key})"


class DuplicateActorCommand(BaseCommand):
    def __init__(self, source_path: Path = Path(), new_path: Path = Path()):
        self.source_path = source_path
        self.new_path = new_path

    def __repr__(self):
        return f"DuplicateActorCommand(source_path={self.source_path}, new_path={self.new_path})"
