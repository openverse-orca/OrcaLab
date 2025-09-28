
from copy import deepcopy
from orcalab.actor import BaseActor, GroupActor
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
    def __init__(self):
        self.path: Path = None

    def __repr__(self):
        return f"CreateGroupCommand(path={self.path})"


class CreateActorCommand(BaseCommand):
    def __init__(self):
        self.actor = None
        self.path: Path = None
        self.row = -1

    def __repr__(self):
        return f"CreteActorCommand(path={self.path})"


class DeleteActorCommand(BaseCommand):
    def __init__(self):
        self.actor: BaseActor = None
        self.path: Path = None
        self.row = -1

    def __repr__(self):
        return f"DeleteActorCommand(path={self.path})"


class RenameActorCommand(BaseCommand):
    def __init__(self):
        self.old_path: Path = None
        self.new_path: Path = None

    def __repr__(self):
        return f"RenameActorCommand(old_path={self.old_path}, new_path={self.new_path})"


class ReparentActorCommand(BaseCommand):
    def __init__(self):
        self.old_path = None
        self.old_row = -1
        self.new_path = None
        self.new_row = -1

    def __repr__(self):
        return f"ReparentActorCommand(old_path={self.old_path}, old_row={self.old_row}, new_path={self.new_path}, new_row={self.new_row})"


class TransformCommand(BaseCommand):
    def __init__(self):
        self.actor_path = None
        self.old_transform = None
        self.new_transform = None
        self.local = None

    def __repr__(self):
        return f"TransformCommand(actor_path={self.actor_path})"
