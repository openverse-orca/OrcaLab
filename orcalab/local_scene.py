from typing import List, Tuple, Dict

from orcalab.actor import AssetActor, BaseActor, GroupActor
from orcalab.actor_property import ActorProperty, ActorPropertyGroup, ActorPropertyKey
from orcalab.path import Path


class LocalScene:
    def __init__(self):
        # 作为根节点，不可见， 路径是"/"。下面挂着所有的顶层Actor。
        self.root_actor = GroupActor(name="root", parent=None)
        self._actors: Dict[Path, BaseActor] = {}
        self._actors[Path.root_path()] = self.root_actor
        self._selection: List[Path] = []

    def __contains__(self, path: Path) -> bool:
        return path in self._actors

    def __getitem__(self, path: Path) -> BaseActor:
        if path not in self._actors:
            raise KeyError(f"No actor at path {path}")
        return self._actors[path]

    @property
    def pseudo_root_actor(self):
        return self.root_actor

    @property
    def selection(self) -> List[Path]:
        return self._selection.copy()

    @selection.setter
    def selection(self, actors: List[Path]):
        paths = []
        for actor in actors:
            actor, path = self.get_actor_and_path(actor)
            paths.append(path)
        self._selection = paths

    def find_actor_by_path(self, path: Path) -> BaseActor | None:
        if path in self._actors:
            return self._actors[path]
        return None

    def get_actor_path(self, actor) -> Path | None:
        for path, a in self._actors.items():
            if a == actor:
                return path
        return None

    def get_actor_and_path(self, actor: BaseActor | Path) -> Tuple[BaseActor, Path]:
        if isinstance(actor, BaseActor):
            actor_path = self.get_actor_path(actor)
            if actor_path is None:
                raise Exception("Invalid actor.")

            return actor, actor_path

        elif isinstance(actor, Path):
            actor_path = actor
            _actor = self.find_actor_by_path(actor)
            if _actor is None:
                raise Exception("Actor does not exist.")

            return _actor, actor_path
        else:
            raise Exception("Invalid actor.")

    def get_actor_and_path_list(
        self, actors: list[BaseActor | Path]
    ) -> Tuple[list[BaseActor], list[Path]]:
        actor_list = []
        path_list = []
        for actor in actors:
            a, p = self.get_actor_and_path(actor)
            actor_list.append(a)
            path_list.append(p)
        return actor_list, path_list

    def _replace_path(self, old_prefix: Path, new_prefix: Path):
        paths_to_update = [old_prefix]
        for p in self._actors.keys():
            if p.is_descendant_of(old_prefix):
                paths_to_update.append(p)

        prefix = old_prefix.string()
        for p in paths_to_update:
            relative_path = p.string()[len(prefix) :]
            updated_path = Path(new_prefix.string() + relative_path)
            self._actors[updated_path] = self._actors[p]
            del self._actors[p]

    def _remove_path(self, prefix: Path):
        paths_to_delete = [prefix]
        for p in self._actors.keys():
            if p.is_descendant_of(prefix):
                paths_to_delete.append(p)

        for p in paths_to_delete:
            del self._actors[p]

    def can_add_actor(
        self, actor: BaseActor, parent_path: GroupActor | Path
    ) -> Tuple[bool, str]:
        if not isinstance(actor, BaseActor):
            return False, "Invalid actor."

        parent_actor, parent_actor_path = self.get_actor_and_path(parent_path)

        if not isinstance(parent_actor, GroupActor):
            return False, "Parent must be a GroupActor."

        for child in parent_actor.children:
            if child.name == actor.name:
                return False, "Name already exists under parent."
        return True, ""

    def add_actor(self, actor: BaseActor, parent_path: Path):
        ok, err = self.can_add_actor(actor, parent_path)
        if not ok:
            raise Exception(err)

        parent_actor, parent_path = self.get_actor_and_path(parent_path)
        assert isinstance(parent_actor, GroupActor)

        # TODO: add group actor.

        actor.parent = parent_actor
        actor_path = parent_path / actor.name
        self._actors[actor_path] = actor

    def can_delete_actor(self, actor: BaseActor | Path) -> Tuple[bool, str]:
        _, _actor_path = self.get_actor_and_path(actor)

        if _actor_path == _actor_path.root_path():
            return False, "Cannot delete pseudo root actor."

        return True, ""

    def delete_actor(self, actor: BaseActor):
        ok, err = self.can_delete_actor(actor)
        if not ok:
            raise Exception(err)

        actor, actor_path = self.get_actor_and_path(actor)

        # Properly remove from parent's children list
        if actor.parent is not None:
            actor.parent.remove_child(actor)

        self._remove_path(actor_path)

    def can_rename_actor(
        self, actor: BaseActor | Path, new_name: str
    ) -> Tuple[bool, str]:
        actor, actor_path = self.get_actor_and_path(actor)

        if actor_path == actor_path.root_path():
            return False, "Cannot rename pseudo root actor."

        if Path.is_valid_name(new_name) == False:
            return False, "Invalid name."

        actor_parent = actor.parent
        if actor_parent is None:
            return False, "Invalid actor."

        for sibling in actor_parent.children:
            if sibling != actor and sibling.name == new_name:
                return False, "Name already exists."

        return True, ""

    def rename_actor(self, actor: BaseActor | Path, new_name):
        ok, err = self.can_rename_actor(actor, new_name)
        if not ok:
            raise Exception(err)

        actor, actor_path = self.get_actor_and_path(actor)

        actor.name = new_name
        new_actor_path = actor_path.parent() / new_name

        self._replace_path(actor_path, new_actor_path)

    def can_reparent_actor(
        self, actor: BaseActor | Path, new_parent: BaseActor | Path
    ) -> Tuple[bool, str]:
        actor, actor_path = self.get_actor_and_path(actor)
        new_parent, new_parent_path = self.get_actor_and_path(new_parent)

        if actor_path == actor_path.root_path():
            return False, "Cannot reparent pseudo root actor."

        if not isinstance(new_parent, GroupActor):
            return False, "New parent must be a GroupActor."

        if actor == new_parent:
            return False, "Cannot reparent to itself."

        if new_parent_path.is_descendant_of(actor_path):
            return False, "Cannot reparent to its descendant."

        for child in new_parent.children:
            if child.name == actor.name:
                return False, "Name already exists under new parent."

        return True, ""

    def reparent_actor(
        self, actor: BaseActor | Path, new_parent: GroupActor | Path, insert_index: int
    ):
        ok, err = self.can_reparent_actor(actor, new_parent)
        if not ok:
            raise Exception(err)

        actor, actor_path = self.get_actor_and_path(actor)
        _new_parent, _new_parent_path = self.get_actor_and_path(new_parent)
        assert isinstance(_new_parent, GroupActor)

        actor.parent = None
        _new_parent.insert_child(insert_index, actor)

        new_actor_path = _new_parent_path / actor.name

        self._replace_path(actor_path, new_actor_path)

    def parse_property_key(
        self, property_key: ActorPropertyKey
    ) -> Tuple[BaseActor, ActorPropertyGroup, ActorProperty]:
        actor = self.find_actor_by_path(property_key.actor_path)

        if actor is None:
            raise Exception("Actor does not exist.")

        assert isinstance(actor, AssetActor), "Only asset actor has properties."

        for group in actor.property_groups:
            if group.prefix == property_key.group_prefix:
                for prop in group.properties:
                    if prop.name() == property_key.property_name:
                        return actor, group, prop

        raise Exception("Property not found.")
