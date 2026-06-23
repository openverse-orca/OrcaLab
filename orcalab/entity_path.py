from dataclasses import dataclass
from typing import List

from orcalab.path import Path


@dataclass()
class NameWithIndex:
    """
    用于解决同名Entity的问题。我们假设同一个Actor下的Entity结构保持不变。
    """

    name: str
    index: int  # 在父节点下的位置


class EntityPath:
    """
    Immutable path to an entity, represented as a list of NameWithIndex segments.
    The string representation is cached for performance.
    """

    __slots__ = ("_segments", "_string", "_hash")

    # 根节点的名称，用于表示Actor自己。
    root_name = "<root>"

    def __init__(self, segments: List[NameWithIndex] = []):
        self._segments = segments
        self._string = ""
        self._hash = 0
        for seg in segments:
            self._hash = hash((self._hash, seg.name, seg.index))
            if seg.index == 0:
                self._string += f"/{seg.name}"
            else:
                self._string += f"/{seg.name}:{seg.index}"

    def string(self) -> str:
        return self._string

    def __repr__(self):
        return self._string

    def __eq__(self, other):
        if not isinstance(other, EntityPath):
            return False

        if len(self._segments) != len(other._segments):
            return False

        for seg1, seg2 in zip(self._segments, other._segments):
            if seg1.index != seg2.index and seg1.name != seg2.name:
                return False

        return True

    def __hash__(self):
        return self._hash

    def clone(self) -> "EntityPath":
        new_path = EntityPath(segments=self._segments.copy())
        new_path._string = self._string
        return new_path

    def empty(self) -> bool:
        return len(self._segments) == 0

    def is_root(self) -> bool:
        if len(self._segments) != 1:
            return False

        return self._segments[0].name == EntityPath.root_name


class FullEntityPath:
    __slots__ = ("actor_path", "entity_path")

    def __init__(self, actor_path: Path, entity_path: EntityPath):
        self.actor_path = actor_path
        self.entity_path = entity_path
