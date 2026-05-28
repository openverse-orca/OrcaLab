import logging
from typing import Dict, List, Set

from orcalab.actor_property import (
    ActorPropertyGroup,
    EntityPropertyGroupEntry,
    FlatPropertyItem,
)
from orcalab.perf_log import perf_timer, perf_log

logger = logging.getLogger(__name__)


class PropertyDataStore:
    def __init__(self):
        self._items: List[FlatPropertyItem] = []
        self._available_component_types: List[str] = []
        self._component_display_names: Dict[str, str] = {}
        self._available_entity_paths: List[str] = []

    def clear(self):
        self._items.clear()
        self._available_component_types.clear()
        self._component_display_names.clear()
        self._available_entity_paths.clear()

    def set_data_from_entries(self, entries: List[EntityPropertyGroupEntry]):
        with perf_timer("data_store.set_data_from_entries", feature="PARSE"):
            self.clear()
            seen_types: Set[str] = set()
            seen_paths: Set[str] = set()

            for entry_idx, entry in enumerate(entries):
                component_type = entry.component_type
                if component_type not in seen_types:
                    seen_types.add(component_type)
                    self._available_component_types.append(component_type)
                    self._component_display_names[component_type] = entry.component_display_name

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
                            component_type_id=entry.property_group.component_type_id,
                            group_id=entry_idx,
                            enum_values=prop.enum_values(),
                        )
                    )

            perf_log(f"data_store.set_data_from_entries: {len(entries)} entries, {len(self._items)} items", feature="PARSE")

    @property
    def items(self) -> List[FlatPropertyItem]:
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

    @property
    def available_entity_paths(self) -> List[str]:
        return self._available_entity_paths

    def set_data_from_groups(
        self,
        groups: List[ActorPropertyGroup],
        entity_id: int,
        entity_path: str,
    ):
        """直接从 ActorPropertyGroup 列表填充数据（用于 entity 路径）"""
        self.clear()
        seen_types: Set[str] = set()

        for group_idx, group in enumerate(groups):
            component_type = group.name
            component_display_name = group.display_name
            if component_type not in seen_types:
                seen_types.add(component_type)
                self._available_component_types.append(component_type)
                self._component_display_names[component_type] = component_display_name

            group_entity_path = group.hint or entity_path
            group_entity_id = group.entity_id or entity_id

            for prop in group.properties:
                self._items.append(
                    FlatPropertyItem(
                        entity_id=group_entity_id,
                        entity_path=group_entity_path,
                        component_type=component_type,
                        component_display_name=component_display_name,
                        property_name=prop.name(),
                        property_display_name=prop.display_name(),
                        property_type=prop.value_type(),
                        value=prop.value(),
                        is_readonly=prop.is_read_only(),
                        group_prefix=group.prefix,
                        component_type_id=group.component_type_id,
                        group_id=group_idx,
                        enum_values=prop.enum_values(),
                    )
                )

        stored_ids = set(item.entity_id for item in self._items)
        stored_paths = set(item.entity_path for item in self._items)
        stored_types = set(item.component_type for item in self._items)
        perf_log(
            f"data_store.set_data_from_groups: {len(groups)} groups, "
            f"{len(self._items)} items, "
            f"unique_entity_ids={stored_ids}, "
            f"unique_entity_paths={stored_paths}, "
            f"component_types={stored_types}",
            feature="PROPERTY"
        )

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
                if text_lower in i.entity_path.lower()
            ]

        if entity_paths is not None:
            perf_log(
                f"data_store.filter_items: total={len(self._items)}, "
                f"filtered={len(result)}, "
                f"entity_paths={entity_paths}, "
                f"component_types={component_types}, "
                f"search_text='{search_text}'",
                feature="PROPERTY"
            )

        if component_types is not None:
            result_types = set(i.component_type for i in result)
            perf_log(
                f"data_store.filter_items: component_types filter active, "
                f"requested={component_types}, "
                f"matched_types={result_types}, "
                f"total={len(self._items)}, filtered={len(result)}",
                feature="PROPERTY"
            )

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
    def _strip_component_suffix(name: str) -> str:
        suffix = "Component"
        if len(name) > len(suffix) and name.endswith(suffix):
            return name[:-len(suffix)]
        return name

    @staticmethod
    def _items_to_property_groups(
        items: List[FlatPropertyItem],
    ) -> List[ActorPropertyGroup]:
        from orcalab.actor_property import ActorProperty

        group_map: dict[tuple[str, str, str, int, int], ActorPropertyGroup] = {}
        group_order: list[tuple[str, str, str, int, int]] = []

        for item in items:
            key = (item.entity_path, item.component_type, item.group_prefix, item.entity_id, item.group_id)
            if key not in group_map:
                group = ActorPropertyGroup(
                    prefix=item.group_prefix,
                    name=PropertyDataStore._strip_component_suffix(item.component_type),
                    hint=item.entity_path,
                )
                group.display_name = item.component_display_name
                group.entity_id = item.entity_id
                group.component_type_id = item.component_type_id
                group_map[key] = group
                group_order.append(key)

            prop = ActorProperty(
                name=item.property_name,
                display_name=item.property_display_name,
                type=item.property_type,
                value=item.value,
            )
            prop.set_read_only(item.is_readonly)
            if item.enum_values:
                prop.set_enum_values(item.enum_values)
            group_map[key].properties.append(prop)

        perf_log(
            f"data_store._items_to_property_groups: {len(items)} items -> {len(group_order)} groups, "
            f"keys={[(k[1], k[2], k[4]) for k in group_order]}",
            feature="PARSE"
        )

        return [group_map[key] for key in group_order]
