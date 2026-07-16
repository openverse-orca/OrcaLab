from __future__ import annotations

from typing import Dict, List

from orcalab.entity_path import EntityPath


class EntityInfo:
    __slots__ = ("entity_id", "name", "entity_path", "children", "parent")

    def __init__(
        self,
        entity_id: int,
        name: str,
        entity_path: EntityPath = EntityPath(),
        children: List[EntityInfo] = [],
        parent: EntityInfo | None = None,
    ):
        self.entity_id = entity_id
        self.name = name
        self.entity_path = entity_path
        self.children: List[EntityInfo] = children
        self.parent = parent

    def find_by_entity_id(self, entity_id: int) -> EntityInfo | None:
        if self.entity_id == entity_id:
            return self
        for child in self.children:
            result = child.find_by_entity_id(entity_id)
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

    def __repr__(self):
        return f"EntityInfo(id={self.entity_id}, name={self.name}, path={self.entity_path})"


class EntityRoot:
    def __init__(self, root_entity_info: EntityInfo):
        # Tree structure of entities
        # 这个根节点在大纲里是看不到的。AssetActor的子节点是这个根节点的子节点。
        self.root_entity_info = root_entity_info

        self._id_lookup_table: Dict[int, EntityInfo] = {}
        self._path_lookup_table: Dict[EntityPath, EntityInfo] = {}

    def build_lookup_table(self):
        self._id_lookup_table.clear()
        self._path_lookup_table.clear()
        self._build_id_table_recursive(self.root_entity_info)
        self._build_path_table_recursive(self.root_entity_info)

    def _build_id_table_recursive(self, entity_info: EntityInfo):
        if entity_info.entity_id != 0:
            self._id_lookup_table[entity_info.entity_id] = entity_info

        for child in entity_info.children:
            self._build_id_table_recursive(child)

    def _build_path_table_recursive(self, entity_info: EntityInfo):
        if not entity_info.entity_path.empty():
            self._path_lookup_table[entity_info.entity_path] = entity_info

        for child in entity_info.children:
            self._build_path_table_recursive(child)

    def find_entity_info(self, entity_id: int) -> EntityInfo | None:
        return self._id_lookup_table.get(entity_id, None)

    def find_entity_info_by_path(self, entity_path: EntityPath) -> EntityInfo | None:
        return self._path_lookup_table.get(entity_path, None)

    def find_entity_path_by_id(self, entity_id: int) -> EntityPath | None:
        entity_info = self.find_entity_info(entity_id)
        if entity_info is not None:
            return entity_info.entity_path
        return None

    def find_entity_id_by_path(self, entity_path: EntityPath) -> int:
        entity_info = self.find_entity_info_by_path(entity_path)
        if entity_info is not None:
            return entity_info.entity_id
        return 0

    def entity_ids(self) -> List[int]:
        return list(self._id_lookup_table.keys())
