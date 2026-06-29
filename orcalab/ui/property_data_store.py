import logging
from typing import Dict, List, Set

from orcalab.actor_property import (
    ActorPropertyGroup,
)

logger = logging.getLogger(__name__)


class PropertyDataStore:
    def __init__(self):
        self._items: List[ActorPropertyGroup] = []
        self._available_component_types: List[str] = []
        self._component_display_names: Dict[str, str] = {}

    def clear(self):
        self._items.clear()
        self._available_component_types.clear()
        self._component_display_names.clear()

    @property
    def items(self) -> List[ActorPropertyGroup]:
        return self._items

    @property
    def available_component_types(self) -> List[str]:
        return self._available_component_types

    def get_component_type_items(self) -> List[tuple[str, str]]:
        """返回 [(内部名, 显示名), ...] 列表"""
        return [
            (t, self._component_display_names.get(t, t))
            for t in self._available_component_types
        ]

    def set_data_from_groups(
        self,
        groups: List[ActorPropertyGroup],
    ):
        self.clear()
        seen_types: Set[str] = set()

        for group in groups:
            component_type = group.name
            if component_type not in seen_types:
                seen_types.add(component_type)
                self._available_component_types.append(component_type)
                self._component_display_names[component_type] = group.name

        self._items = groups

    def get_property_groups_for_display(
        self,
        component_types: Set[str] | None = None,
        search_text: str = "",
    ) -> List[ActorPropertyGroup]:
        result = self._items
        if component_types is not None:
            result = [g for g in result if g.name in component_types]
        if search_text:
            text_lower = search_text.lower()
            result = [g for g in result if text_lower in str(g.hint).lower()]

        return result
