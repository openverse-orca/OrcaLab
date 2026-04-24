from __future__ import annotations

from typing import List


class EntityInfo:
    __slots__ = ("entity_id", "name", "entity_path", "children")

    def __init__(
        self,
        entity_id: int,
        name: str,
        entity_path: str,
        children: List[EntityInfo] | None = None,
    ):
        self.entity_id = entity_id
        self.name = name
        self.entity_path = entity_path
        self.children: List[EntityInfo] = children if children is not None else []

    def find_by_entity_id(self, entity_id: int) -> EntityInfo | None:
        if self.entity_id == entity_id:
            return self
        for child in self.children:
            result = child.find_by_entity_id(entity_id)
            if result is not None:
                return result
        return None

    def find_by_entity_path(self, entity_path: str) -> EntityInfo | None:
        if self.entity_path == entity_path:
            return self
        for child in self.children:
            result = child.find_by_entity_path(entity_path)
            if result is not None:
                return result
        return None

    def collect_entity_ids(self) -> List[int]:
        result = [self.entity_id]
        for child in self.children:
            result.extend(child.collect_entity_ids())
        return result

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "entity_path": self.entity_path,
            "children": [c.to_dict() for c in self.children],
        }

    @staticmethod
    def from_dict(data: dict) -> EntityInfo:
        children = [EntityInfo.from_dict(c) for c in data.get("children", [])]
        return EntityInfo(
            entity_id=data["entity_id"],
            name=data["name"],
            entity_path=data["entity_path"],
            children=children,
        )

    def __repr__(self):
        return f"EntityInfo(id={self.entity_id}, name={self.name}, path={self.entity_path})"
