from typing import List, Sequence, Tuple, Dict

from orcalab.actor import AssetActor, BaseActor, GroupActor
from orcalab.actor_property import (
    ActorProperty,
    ActorPropertyGroup,
    ActorPropertyKey,
    ActorPropertyType,
    TreePropertyNode,
)
from orcalab.path import Path
from orcalab.scene_edit_types import AddActorRequest


class LocalScene:
    def __init__(self):
        # 作为根节点，不可见， 路径是"/"。下面挂着所有的顶层Actor。
        self.root_actor = GroupActor(name="root", parent=None)
        self._actors: Dict[Path, BaseActor] = {}
        self._actors[Path.root_path()] = self.root_actor
        self._selection: List[Path] = []
        self._active_actor: Path | None = None

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
    def actors(self) -> Dict[Path, BaseActor]:
        return self._actors.copy()

    @property
    def selection(self) -> List[Path]:
        """返回当前选中Actor的路径列表，路径列表是有序的，按照路径字符串的字典序排序"""
        return self._selection.copy()

    @selection.setter
    def selection(self, actors: List[Path]):
        paths = []
        for actor in actors:
            actor, path = self.get_actor_and_path(actor)
            paths.append(path)

        # 确保路径列表是有序的，按照路径字符串的字典序排序
        sorted_paths = sorted(paths)
        self._selection = sorted_paths

    @property
    def active_actor(self) -> Path | None:
        """返回当前激活Actor的路径，如果没有激活Actor则返回None"""
        return self._active_actor

    @active_actor.setter
    def active_actor(self, actor_path: Path | None):
        self._active_actor = actor_path

    def find_actor_by_path(self, path: Path) -> BaseActor | None:
        if path in self._actors:
            return self._actors[path]
        return None

    def get_actor_path(self, actor) -> Path | None:
        for path, a in self._actors.items():
            if a == actor:
                return path
        return None

    def normalize_actor(self, actor: BaseActor | Path) -> Tuple[BaseActor, Path]:
        """将输入的actor规范化为(BaseActor, Path)形式，输入可以是BaseActor对象或者Path对象"""
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

    def get_actor_and_path(self, actor: BaseActor | Path) -> Tuple[BaseActor, Path]:
        """Deprecated. Use normalize_actor instead"""
        return self.normalize_actor(actor)

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

    def normalize_actors(
        self, actors: Sequence[BaseActor | Path]
    ) -> Tuple[List[BaseActor], List[Path]]:
        """将输入的actor列表规范化为(BaseActor, Path)列表，输入可以是BaseActor对象或者Path对象的混合列表"""
        actor_list: List[BaseActor] = []
        path_list: List[Path] = []
        for actor in actors:
            a, p = self.normalize_actor(actor)
            actor_list.append(a)
            path_list.append(p)

        return actor_list, path_list

    def _replace_path(self, old_prefix: Path, new_prefix: Path):
        if old_prefix == new_prefix:
            return

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

    def _remove_paths(self, prefix: Path):
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

    def can_add_actors(self, requests: Sequence[AddActorRequest]) -> Tuple[bool, str]:
        """Simulate adding actors."""

        actor_list: List[Path] = []
        for path in self._actors.keys():
            actor_list.append(path)

        for request in requests:
            actor = request.actor
            parent_path = request.parent_path

            if not isinstance(actor, BaseActor):
                return False, "Invalid actor."

            if request.actor_template is not None:
                same_type = type(request.actor_template) is type(request.actor)
                if not same_type:
                    return False, "Actor template type does not match actor type."

            if parent_path not in actor_list:
                return False, f"Parent {parent_path} does not exist during add."

            # TODO: 这里没有考虑同一批次中多个Actor添加到同一个父节点导致的名字冲突问题，后续可以补充

            new_actor_path = parent_path / actor.name
            actor_list.append(new_actor_path)

        return True, ""

    def add_actor(self, actor: BaseActor, parent_path: Path):
        ok, err = self.can_add_actor(actor, parent_path)
        if not ok:
            raise Exception(err)

        parent_actor, parent_path = self.get_actor_and_path(parent_path)
        assert isinstance(parent_actor, GroupActor)

        actor.parent = parent_actor
        actor_path = parent_path / actor.name
        self._actors[actor_path] = actor

    def add_actor1(self, request: AddActorRequest) -> str:
        actor = request.actor
        parent_path = request.parent_path

        ok, err = self.can_add_actor(actor, parent_path)
        if not ok:
            return err

        parent_actor, parent_path = self.normalize_actor(parent_path)
        assert isinstance(parent_actor, GroupActor)
        parent_actor.insert_child(request.child_pos, actor)

        actor_path = parent_path / actor.name
        self._actors[actor_path] = actor

        return ""

    def add_actor_batch(self, requests: List[AddActorRequest]) -> str:
        ok, err = self.can_add_actors(requests)
        if not ok:
            return err

        for request in requests:
            result = self.add_actor1(request)
            if result != "":
                return result
        return ""

    def can_duplicate_actors(
        self, actors: Sequence[BaseActor | Path]
    ) -> Tuple[bool, str]:
        _, actor_paths = self.normalize_actors(actors)

        for actor_path in actor_paths:
            if actor_path == actor_path.root_path():
                return False, "Cannot duplicate pseudo root actor."

        return True, ""

    def can_delete_actors(self, actors: Sequence[BaseActor | Path]) -> Tuple[bool, str]:
        _, actor_paths = self.normalize_actors(actors)
        for actor_path in actor_paths:
            if actor_path.is_root():
                return False, f"Cannot delete root actor"
        return True, ""

    def delete_actors(self, actors: List[BaseActor]):
        _actors, _actor_paths = self.normalize_actors(actors)
        for actor, path in zip(_actors, _actor_paths):
            if actor.parent is not None:
                actor.parent.remove_child(actor)
            self._remove_paths(path)

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

    def can_move_actors(
        self,
        old_actors: Sequence[BaseActor | Path],
        new_parent_paths: List[Path],
        new_rows: List[int],
        undo: bool = True,
        source: str = "",
    ):
        if not old_actors:
            return False, "No actors to move."

        if len(old_actors) != len(new_parent_paths) != len(new_rows):
            return False, "Inconsistent lengths of input lists."

        _old_actors, _old_actor_paths = self.normalize_actors(old_actors)
        _new_parent_actors, _new_parent_paths = self.normalize_actors(new_parent_paths)
        for actor_path, new_parent_path, new_parent in zip(
            _old_actor_paths, _new_parent_paths, _new_parent_actors
        ):
            if not isinstance(new_parent, GroupActor):
                return False, "New parent must be a GroupActor."

            if actor_path == actor_path.root_path():
                return False, "Cannot reparent pseudo root actor."

            if actor_path == new_parent_path:
                return False, "Cannot reparent to itself."

            if new_parent_path.is_descendant_of(actor_path):
                return False, "Cannot reparent to its descendant."

            for child in new_parent.children:
                if child.name == actor_path.name:
                    return False, "Name already exists under new parent."

        # TODO: 检查多个移动操作不会导致冲突

        return True, ""

    def move_actors(
        self,
        old_actors: Sequence[BaseActor | Path],
        new_parent_paths: List[Path],
        new_rows: List[int],
        undo: bool = True,
        source: str = "",
    ):
        ok, err = self.can_move_actors(
            old_actors, new_parent_paths, new_rows, undo, source
        )
        if not ok:
            raise Exception(err)

        _old_actors, _old_actor_paths = self.normalize_actors(old_actors)
        _new_parent, _new_parent_path = self.normalize_actors(new_parent_paths)

        for actor, actor_path, new_parent, new_parent_path, new_row in zip(
            _old_actors, _old_actor_paths, _new_parent, _new_parent_path, new_rows
        ):
            assert isinstance(new_parent, GroupActor)
            actor.parent = None
            new_parent.insert_child(new_row, actor)
            new_actor_path = new_parent_path / actor.name
            self._replace_path(actor_path, new_actor_path)

    def _find_property_in_tree(
        self,
        node: TreePropertyNode,
        full_prop_name: str,
        prop_type: ActorPropertyType,
    ) -> ActorProperty | None:
        """在树节点中递归查找属性，使用完整属性名匹配"""
        for prop in node.properties:
            # 树形属性的完整名称格式: NodeName.PropertyName
            expected_name = f"{node.name}.{prop.name()}"
            if expected_name == full_prop_name and prop.value_type() == prop_type:
                return prop
        for child in node.children:
            result = self._find_property_in_tree(child, full_prop_name, prop_type)
            if result:
                return result
        return None

    def parse_property_key(
        self, property_key: ActorPropertyKey
    ) -> Tuple[BaseActor, ActorPropertyGroup, ActorProperty]:
        actor = self.find_actor_by_path(property_key.actor_path)

        if actor is None:
            raise Exception("Actor does not exist.")

        assert isinstance(actor, AssetActor), "Only asset actor has properties."

        for group in actor.property_groups:
            if group.prefix == property_key.group_prefix:
                # 先在 properties 中查找
                for prop in group.properties:
                    if (
                        prop.name() == property_key.property_name
                        and prop.value_type() == property_key.property_type
                    ):
                        return actor, group, prop

                # 再在 tree_data 中查找（遍历所有节点匹配完整属性名）
                for tree_node in group.tree_data:
                    prop = self._find_property_in_tree(
                        tree_node,
                        property_key.property_name,
                        property_key.property_type,
                    )
                    if prop:
                        return actor, group, prop

        raise Exception("Property not found.")

    def update_visible_recursive(
        self, actor: BaseActor, paths_to_update: List, visible: bool
    ):
        if not isinstance(actor, GroupActor):
            return

        for child in actor.children:
            child_actor, child_path = self.get_actor_and_path(child)
            if child_path is None:
                continue
            child_actor.is_parent_visible = visible

            if visible:
                if child_actor.is_visible:
                    if isinstance(child_actor, AssetActor):
                        paths_to_update.append(child_path)
                    self.update_visible_recursive(child_actor, paths_to_update, visible)
            else:
                if isinstance(child_actor, AssetActor):
                    paths_to_update.append(child_path)
                self.update_visible_recursive(child_actor, paths_to_update, visible)

    def update_locked_recursive(
        self, actor: BaseActor, paths_to_update: List, locked: bool
    ):
        if not isinstance(actor, GroupActor):
            return

        for child in actor.children:
            child_actor, child_path = self.get_actor_and_path(child)
            if child_path is None:
                continue
            child_actor.is_parent_locked = locked

            if locked:
                paths_to_update.append(child_path)
                self.update_locked_recursive(child_actor, paths_to_update, locked)
            else:
                if not child_actor.is_locked:
                    paths_to_update.append(child_path)
                    self.update_locked_recursive(child_actor, paths_to_update, locked)
