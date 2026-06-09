from typing import List

from orcalab.path import Path


class NameWithIndex:
    """
    用于解决同名Entity的问题。我们假设同一个Actor下的Entity结构保持不变。
    """

    __slots__ = ("name", "index")

    def __init__(self, name: str, index: int):
        self.name = name
        self.index = index  # 在父节点下的位置


class EntityPath:
    """
    Immutable path to an entity, represented as a list of NameWithIndex segments.
    The string representation is cached for performance.
    """

    __slots__ = ("_segments", "_string_cache")

    def __init__(self, segments: List[NameWithIndex] = []):
        self._segments = segments
        self._string_cache: str | None = None

    def string(self) -> str:
        if self._string_cache is not None:
            return self._string_cache

        segments = []
        for seg in self._segments:
            segments.append(seg.name)
        segments_str = "/".join(segments)

        self._string_cache = segments_str
        return self._string_cache

    def __repr__(self):
        return self.string()

    def __eq__(self, other):
        if not isinstance(other, EntityPath):
            return False

        if len(self._segments) != len(other._segments):
            return False

        for seg1, seg2 in zip(self._segments, other._segments):
            if seg1.index != seg2.index:
                return False

        return True

    def __hash__(self):
        return hash(tuple(seg.index for seg in self._segments))

    def clone(self) -> "EntityPath":
        new_path = EntityPath(segments=self._segments.copy())
        new_path._string_cache = self._string_cache
        return new_path

    def empty(self) -> bool:
        return len(self._segments) == 0


class FullEntityPath:
    __slots__ = ("actor_path", "entity_path")

    def __init__(self, actor_path: Path, entity_path: EntityPath):
        self.actor_path = actor_path
        self.entity_path = entity_path
