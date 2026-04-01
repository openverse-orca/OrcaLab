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


class ActiveActorCommand(BaseCommand):
    def __init__(self, old_active_actor: Path | None, new_active_actor: Path | None):
        self.old_active_actor = old_active_actor
        self.new_active_actor = new_active_actor

    def __repr__(self):
        return f"ActiveActorCommand(old_active_actor={self.old_active_actor}, new_active_actor={self.new_active_actor})"


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


class MoveActorCommand(BaseCommand):
    def __init__(
        self,
        actor_paths: List[Path],
        old_rows: List[int],
        new_parent_paths: List[Path],
        new_rows: List[int],
    ):
        self.actor_paths = actor_paths
        self.old_rows = old_rows
        self.new_parent_paths = new_parent_paths
        self.new_rows = new_rows

    def __repr__(self):
        return f"MoveActorCommand(actor_paths={self.actor_paths}, old_rows={self.old_rows}, new_parent_paths={self.new_parent_paths}, new_rows={self.new_rows})"


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


class DuplicateActorsCommand(BaseCommand):
    def __init__(self, source_paths: List[Path] = [], new_paths: List[Path] = []):
        self.source_paths = source_paths
        self.new_paths = new_paths

    def __repr__(self):
        return f"DuplicateActorsCommand(count={len(self.source_paths)})"
