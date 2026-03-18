from typing import List, override

from orcalab.actor_property import ActorPropertyGroup
from orcalab.path import Path
from orcalab.math import Transform

import copy

type ParentActor = GroupActor | None


class BaseActor:
    def __init__(self, name: str, parent: ParentActor):
        self._name = ""
        self._parent = None
        self._transform = Transform()
        self._world_transform = None
        self.name = name
        self.parent = parent
        self._is_visible = True
        self._is_locked = False
        self._is_parent_visible = True
        self._is_parent_locked = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "parent": self.parent.name if self.parent else None,
            "transform.position": self.transform.position.tolist(),
            "transform.rotation": self.transform.rotation.tolist(),
            "transform.scale": self.transform.scale,
            "world_transform.position": self.world_transform.position.tolist(),
            "world_transform.rotation": self.world_transform.rotation.tolist(),
            "world_transform.scale": self.world_transform.scale,
            "is_visible": self.is_visible,
            "is_locked": self.is_locked,
            "is_parent_visible": self.is_parent_visible,
            "is_parent_locked": self.is_parent_locked,
            "type": self.__class__.__name__,
        }

    def __repr__(self):
        return f"BaseActor(name={self._name})"

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        if not isinstance(value, str) or not Path.is_valid_name(value):
            raise ValueError(f"Invalid name: {value}")
        self._name = value

    @property
    def parent(self) -> ParentActor:
        return self._parent

    @parent.setter
    def parent(self, parent_actor):
        if parent_actor is not None and not isinstance(parent_actor, GroupActor):
            raise TypeError("parent must be an instance of GroupActor or None.")

        if parent_actor == self._parent:
            return

        if self._parent is not None:
            self._parent._children.remove(self)

        if parent_actor is not None:
            parent_actor._children.append(self)

        self._parent = parent_actor
        self._world_transform = None  # Invalidate world transform cache

    @property
    def is_visible(self) -> bool:
        return self._is_visible

    @is_visible.setter
    def is_visible(self, value: bool):
        if not isinstance(value, bool):
            raise TypeError("is_visible must be a bool.")
        self._is_visible = value

    @property
    def is_locked(self) -> bool:
        return self._is_locked

    @is_locked.setter
    def is_locked(self, value: bool):
        if not isinstance(value, bool):
            raise TypeError("is_locked must be a bool.")
        self._is_locked = value

    @property
    def is_parent_visible(self) -> bool:
        return self._is_parent_visible

    @is_parent_visible.setter
    def is_parent_visible(self, value: bool):
        if not isinstance(value, bool):
            raise TypeError("is_parent_visible must be a bool.")
        self._is_parent_visible = value

    @property
    def is_parent_locked(self) -> bool:
        return self._is_parent_locked

    @is_parent_locked.setter
    def is_parent_locked(self, value: bool):
        if not isinstance(value, bool):
            raise TypeError("is_parent_locked must be a bool.")
        self._is_parent_locked = value

    @property
    def transform(self):
        return copy.deepcopy(self._transform)

    @transform.setter
    def transform(self, value):
        if not isinstance(value, Transform):
            raise TypeError("transform must be an instance of Transform.")
        self._transform = copy.deepcopy(value)

        self._world_transform = None  # Invalidate world transform cache

    @property
    def world_transform(self) -> Transform:
        if self._world_transform is not None:
            return self._world_transform

        if self.parent is None:
            self._world_transform = self.transform
        else:
            self._world_transform = self.parent.world_transform * self.transform

        return self._world_transform

    @world_transform.setter
    def world_transform(self, value: Transform):
        if not isinstance(value, Transform):
            raise TypeError("world_transform must be an instance of Transform.")

        if self.parent is None:
            self.transform = value
        else:
            self.transform = self.parent.world_transform.inverse() * value

        self._world_transform = value


class GroupActor(BaseActor):
    def __init__(self, name: str, parent: ParentActor = None):
        self._children: List[BaseActor] = []
        super().__init__(name, parent)

    def __repr__(self):
        return f"GroupActor(name={self.name}, children_count={len(self._children)})"

    @property
    def children(self):
        return self._children.copy()

    def insert_child(self, index: int, child: BaseActor):
        if not isinstance(child, BaseActor):
            raise TypeError("Child must be an instance of GroupActor or AssetActor.")

        if child in self._children:
            raise ValueError(f"{child.name} is already a child of {self.name}")

        if child.parent is not None:
            child.parent.remove_child(child)

        if index < 0 or index > len(self._children):
            self._children.append(child)
        else:
            self._children.insert(index, child)

        child._parent = self

    def add_child(self, child: BaseActor):
        self.insert_child(-1, child)

    def remove_child(self, child: BaseActor):
        if child in self._children:
            self._children.remove(child)
            child._parent = None
        # Don't raise error if child is not in the list - this can happen during cleanup
        # TODO: Test this behavior?


class AssetActor(BaseActor):
    def __init__(self, name: str, asset_path: str, parent: GroupActor | None = None):
        super().__init__(name, parent)
        self._asset_path = asset_path
        self.property_groups: List[ActorPropertyGroup] = []

    def __repr__(self):
        return f"AssetActor(name={self.name})"

    @property
    def asset_path(self):
        return self._asset_path

    @asset_path.setter
    def asset_path(self, value):
        if not isinstance(value, str) or len(value) == 0:
            raise ValueError("asset_path name must be non-empty string")
        self._asset_path = value
