from copy import deepcopy
from typing import Any
from orcalab.actor import BaseActor, GroupActor
from orcalab.actor_property import ActorPropertyKey
from orcalab.math import Transform
from orcalab.path import Path


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
    def __init__(self):
        self.old_selection = []
        self.new_selection = []

    def __repr__(self):
        return f"SelectionCommand(old_selection={self.old_selection}, new_selection={self.new_selection})"


class CreateGroupCommand(BaseCommand):
    def __init__(self, path: Path):
        self.path = path

    def __repr__(self):
        return f"CreateGroupCommand(path={self.path})"


class CreateActorCommand(BaseCommand):
    def __init__(self, actor: BaseActor, path: Path, row: int):
        self.actor = actor
        self.path = path
        self.row = row

    def __repr__(self):
        return f"CreteActorCommand(path={self.path})"


class DeleteActorCommand(BaseCommand):
    def __init__(self, actor: BaseActor, path: Path, row: int):
        self.actor = actor
        self.path = path
        self.row = row

    def __repr__(self):
        return f"DeleteActorCommand(path={self.path})"


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
    def __init__(self):
        self.actor_path: Path = Path()
        self.old_transform = Transform()
        self.new_transform = Transform()
        self.local = True

    def __repr__(self):
        return f"TransformCommand(actor_path={self.actor_path})"


class PropertyChangeCommand(BaseCommand):
    def __init__(self, property_key: ActorPropertyKey, old_value: Any, new_value: Any):
        self.property_key = property_key
        self.old_value = old_value
        self.new_value = new_value

    def __repr__(self):
        return f"PropertyChangeCommand(property_key={self.property_key})"
