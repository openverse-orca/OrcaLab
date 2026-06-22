from dataclasses import dataclass
from typing import Any, Dict, List

from orcalab.actor import BaseActor, GroupActor
from orcalab.actor_property import ActorPropertyKey, PropertyOverride
from orcalab.transform import Transform
from orcalab.path import Path
from orcalab.scene_edit_types import AddActorRequest
from orcalab.selection_data import SelectionData

# 不要存Actor对象，只存Path。
# Actor可能被删除和创建，前后的Actor是不相等的。
# DeleteActorCommand中存的Actor不会再次放到LocalScene中，
# 而是作为模板使用。


@dataclass
class BaseCommand:
    pass


class CommandGroup(BaseCommand):
    def __init__(self):
        self.commands = []

    def __repr__(self):
        return f"CommandGroup(commands={self.commands})"


class SelectionCommand(BaseCommand):
    def __init__(self, old_selection: SelectionData, new_selection: SelectionData):
        self.old_selection = old_selection
        self.new_selection = new_selection

    def __repr__(self):
        return f"SelectionCommand(old_selection={self.old_selection}, new_selection={self.new_selection})"


class AddActorCommand(BaseCommand):
    def __init__(self, requests: List[AddActorRequest]):
        self.requests = requests

    def __repr__(self):
        return f"AddActorCommand({len(self.requests)} requests)"


@dataclass
class ActorReconstructInfo:
    actor: BaseActor
    actor_path: Path
    # 删除前在兄弟节点中的位置
    position: int
    # 包含actor和子Actor所有修改的属性
    actor_overrides_dict: Dict[Path, List[PropertyOverride]]


@dataclass
class DeleteActorCommand(BaseCommand):
    actor_reconstruct_info: List[ActorReconstructInfo]


@dataclass
class RenameActorCommand(BaseCommand):
    old_path: Path
    new_path: Path


@dataclass
class MoveActorCommand(BaseCommand):
    actor_paths: List[Path]
    old_rows: List[int]
    new_parent_paths: List[Path]
    new_rows: List[int]


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


@dataclass
class PropertyChangeCommand(BaseCommand):
    property_key: ActorPropertyKey
    old_value: Any
    new_value: Any


class DuplicateActorsCommand(BaseCommand):
    def __init__(self, source_paths: List[Path] = [], new_paths: List[Path] = []):
        self.source_paths = source_paths
        self.new_paths = new_paths

    def __repr__(self):
        return f"DuplicateActorsCommand(count={len(self.source_paths)})"
