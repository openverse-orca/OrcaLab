import logging
from typing import Any, List, Set

from orcalab.actor_property import (
    ActorPropertyGroup,
    ActorPropertyType,
    EntityPropertyGroupEntry,
    FlatPropertyItem,
)

logger = logging.getLogger(__name__)


class PropertyDataStore:
    def __init__(self):
        self._items: List[FlatPropertyItem] = []
        self._available_component_types: List[str] = []
        self._available_entity_paths: List[str] = []

    def clear(self):
        self._items.clear()
        self._available_component_types.clear()
        self._available_entity_paths.clear()

    def set_data_from_entries(self, entries: List[EntityPropertyGroupEntry]):
        self.clear()
        seen_types: Set[str] = set()
        seen_paths: Set[str] = set()

        for entry in entries:
            component_type = entry.component_type
            if component_type not in seen_types:
                seen_types.add(component_type)
                self._available_component_types.append(component_type)

            entity_path = entry.entity_path
            if entity_path not in seen_paths:
                seen_paths.add(entity_path)
                self._available_entity_paths.append(entity_path)

            for prop in entry.property_group.properties:
                self._items.append(
                    FlatPropertyItem(
                        entity_id=entry.entity_id,
                        entity_path=entity_path,
                        component_type=component_type,
                        component_display_name=entry.component_display_name,
                        property_name=prop.name(),
                        property_display_name=prop.display_name(),
                        property_type=prop.value_type(),
                        value=prop.value(),
                        is_readonly=prop.is_read_only(),
                        group_prefix=entry.property_group.prefix,
                    )
                )

    @property
    def items(self) -> List[FlatPropertyItem]:
        return self._items

    @property
    def available_component_types(self) -> List[str]:
        return self._available_component_types

    @property
    def available_entity_paths(self) -> List[str]:
        return self._available_entity_paths

    def filter_items(
        self,
        component_types: Set[str] | None = None,
        entity_paths: Set[str] | None = None,
        search_text: str = "",
    ) -> List[FlatPropertyItem]:
        result = self._items
        if component_types is not None:
            result = [i for i in result if i.component_type in component_types]
        if entity_paths is not None:
            result = [i for i in result if i.entity_path in entity_paths]
        if search_text:
            text_lower = search_text.lower()
            result = [
                i
                for i in result
                if text_lower in i.property_display_name.lower()
                or text_lower in i.component_display_name.lower()
                or text_lower in i.property_name.lower()
                or text_lower in i.component_type.lower()
            ]
        return result

    def get_property_groups_for_display(
        self,
        component_types: Set[str] | None = None,
        entity_paths: Set[str] | None = None,
        search_text: str = "",
    ) -> List[ActorPropertyGroup]:
        filtered = self.filter_items(component_types, entity_paths, search_text)
        return self._items_to_property_groups(filtered)

    @staticmethod
    def _items_to_property_groups(
        items: List[FlatPropertyItem],
    ) -> List[ActorPropertyGroup]:
        from orcalab.actor_property import ActorProperty

        group_map: dict[tuple[str, str, str, int], ActorPropertyGroup] = {}
        group_order: list[tuple[str, str, str, int]] = []

        for item in items:
            key = (item.entity_path, item.component_type, item.group_prefix, item.entity_id)
            if key not in group_map:
                group = ActorPropertyGroup(
                    prefix=item.group_prefix,
                    name=item.component_type,
                    hint=item.entity_path,
                )
                group.display_name = item.component_display_name
                group_map[key] = group
                group_order.append(key)

            prop = ActorProperty(
                name=item.property_name,
                display_name=item.property_display_name,
                type=item.property_type,
                value=item.value,
            )
            prop.set_read_only(item.is_readonly)
            group_map[key].properties.append(prop)

        return [group_map[key] for key in group_order]
