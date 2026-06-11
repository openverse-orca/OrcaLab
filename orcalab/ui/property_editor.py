import asyncio
import logging
from collections import OrderedDict
from typing import override

from PySide6 import QtCore, QtWidgets

from orcalab.actor import BaseActor, AssetActor
from orcalab.actor_property import (
    ActorProperty,
    ActorPropertyGroup,
    ActorPropertyKey,
    EntityPropertyGroupEntry,
)
from orcalab.actor_util import collect_properties
from orcalab.application_util import get_local_scene, get_remote_scene
from orcalab.entity_info import EntityInfo
from orcalab.path import Path
from orcalab.perf_log import perf_timer, perf_log
from orcalab.selection_data import SelectionData
from orcalab.ui.filter_bar import FilterBar
from orcalab.ui.fonts.font_service import FontService
from orcalab.ui.property_data_store import PropertyDataStore
from orcalab.ui.property_edit.property_group_edit import PropertyGroupEdit
from orcalab.ui.property_edit.transform_edit import TransformEdit

from orcalab.scene_edit_bus import (
    SceneEditNotification,
    SceneEditNotificationBus,
)

logger = logging.getLogger(__name__)

_MAX_CACHE_SIZE = 10
_RENDER_BATCH_SIZE = 5


class PropertyEditor(QtWidgets.QScrollArea, SceneEditNotification):

    def __init__(self, parent=None):
        super().__init__(parent)

        self._data_store = PropertyDataStore()
        self._actor: BaseActor | None = None
        self._entity: EntityInfo | None = None
        self._actor_path: Path | None = None
        self._property_edits: list[PropertyGroupEdit] = []
        self._raw_entries: list[EntityPropertyGroupEntry] = []
        self._transform_edit: TransformEdit | None = None

        self._section_cache: OrderedDict[tuple, list[PropertyGroupEdit]] = OrderedDict()
        self._active_cache_key: tuple | None = None
        self._pending_render_task: asyncio.Task | None = None

        self._recursive = False
        self._show_transform = False

        self._container = QtWidgets.QWidget()
        self._main_layout = QtWidgets.QVBoxLayout(self._container)
        self._main_layout.setContentsMargins(4, 4, 4, 4)
        self._main_layout.setSpacing(4)

        self._filter_bar = FilterBar()
        self._filter_bar.filter_changed.connect(self._apply_filter)
        self._filter_bar.show_transform_changed.connect(self._on_show_transform_changed)
        self._main_layout.addWidget(self._filter_bar)

        self._property_layout = QtWidgets.QVBoxLayout()
        self._property_layout.setContentsMargins(0, 0, 0, 0)
        self._property_layout.setSpacing(2)
        self._main_layout.addLayout(self._property_layout)

        self._main_layout.addStretch()

        self.setWidget(self._container)
        self.setWidgetResizable(True)

        self._show_empty()

    def _cache_key(self) -> tuple | None:
        if self._actor_path is None:
            return None
        if self._entity is not None:
            return (
                str(self._actor_path),
                self._entity.entity_id,
                self._recursive,
                self._show_transform,
            )
        return (str(self._actor_path), None, self._recursive, self._show_transform)

    def connect_bus(self):
        SceneEditNotificationBus.connect(self)

    def disconnect_bus(self):
        SceneEditNotificationBus.disconnect(self)

    def get_actor(self) -> BaseActor | None:
        return self._actor

    def set_actor(self, actor: BaseActor | None):
        if self._actor == actor and self._entity is None:
            return

        self._actor = actor
        self._entity = None
        self._actor_path = None

        if actor is not None:
            local_scene = get_local_scene()
            self._actor_path = local_scene.get_actor_path(actor)

        self._load_properties()

    def set_entity(self, actor: BaseActor, entity: EntityInfo, actor_path: Path):
        if self._actor == actor and self._entity is entity:
            return

        perf_log(
            f"property_editor.set_entity: actor={actor.name}, entity={entity.name}, entity_id={entity.entity_id}",
            feature="PROPERTY",
        )

        self._actor = actor
        self._entity = entity
        self._actor_path = actor_path
        with perf_timer("property_editor._load_properties", feature="PROPERTY"):
            self._load_properties()

    def clear_selection(self):
        if self._actor is None and self._entity is None:
            return

        self._actor = None
        self._entity = None
        self._actor_path = None
        self._data_store.clear()
        self._raw_entries.clear()
        self._clear_cache()
        self._show_empty()

    def set_recursive_display(self, enabled: bool):
        self._recursive = enabled
        if (
            self._entity is not None
            and self._actor is not None
            and self._actor_path is not None
        ):
            self._load_properties()

    def _on_show_transform_changed(self, visible: bool):
        self._show_transform = visible
        if self._actor is not None:
            self._apply_filter()

    def _cancel_pending_render(self):
        if self._pending_render_task is not None:
            self._pending_render_task.cancel()
            self._pending_render_task = None

    def _clear_cache(self):
        for cached_edits in self._section_cache.values():
            for edit in cached_edits:
                edit.disconnect_buses()
                edit.deleteLater()
        self._section_cache.clear()
        self._active_cache_key = None

    def _evict_cache_if_needed(self):
        while len(self._section_cache) > _MAX_CACHE_SIZE:
            oldest_key, oldest_edits = next(iter(self._section_cache.items()))
            if oldest_key == self._active_cache_key:
                self._section_cache.move_to_end(oldest_key)
                if len(self._section_cache) <= _MAX_CACHE_SIZE:
                    break
                oldest_key, oldest_edits = next(iter(self._section_cache.items()))
            for edit in oldest_edits:
                edit.disconnect_buses()
                edit.deleteLater()
            del self._section_cache[oldest_key]

    def _cached_widget_ids(self) -> set[int]:
        ids = set()
        for edits in self._section_cache.values():
            for edit in edits:
                ids.add(id(edit))
        return ids

    def _hide_active_sections(self):
        if self._active_cache_key is not None:
            cached = self._section_cache.get(self._active_cache_key)
            if cached is not None:
                for edit in cached:
                    edit.hide()

        for edit in self._property_edits:
            edit.hide()
        self._property_edits.clear()

        if self._transform_edit is not None:
            perf_log(
                f"_hide_active_sections: disconnect_buses and setting _transform_edit=None, actor={self._transform_edit._actor_path}, id={id(self._transform_edit)}",
                feature="TRACE_LIFECYCLE",
            )
            self._transform_edit.disconnect_buses()
        self._transform_edit = None

        cached_ids = self._cached_widget_ids()
        while self._property_layout.count():
            item = self._property_layout.takeAt(0)
            if item.widget():
                w = item.widget()
                self._property_layout.removeWidget(w)
                w.hide()
                if id(w) not in cached_ids:
                    w.deleteLater()
            elif item.layout():
                self._property_layout.removeItem(item)

    def _clear_property_layout(self):
        for edit in self._property_edits:
            edit.disconnect_buses()
        self._property_edits.clear()

        if self._transform_edit is not None:
            perf_log(
                f"_clear_property_layout: disconnect_buses and setting _transform_edit=None, actor={self._transform_edit._actor_path}, id={id(self._transform_edit)}",
                feature="TRACE_LIFECYCLE",
            )
            self._transform_edit.disconnect_buses()
        self._transform_edit = None

        cached_ids = self._cached_widget_ids()
        while self._property_layout.count():
            item = self._property_layout.takeAt(0)
            if item.widget():
                w = item.widget()
                self._property_layout.removeWidget(w)
                w.hide()
                if id(w) not in cached_ids:
                    w.deleteLater()
            elif item.layout():
                self._property_layout.removeItem(item)

    def _show_empty(self):
        self._clear_property_layout()
        label = QtWidgets.QLabel("没有选中任何对象")
        label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        FontService().bind_widget_font(label, "body")
        self._property_layout.addWidget(label)

    def _add_transform_edit(self):
        if self._transform_edit is not None:
            perf_log(
                f"_add_transform_edit: replacing existing _transform_edit, actor={self._transform_edit._actor_path}, id={id(self._transform_edit)}",
                feature="TRACE_LIFECYCLE",
            )
            self._transform_edit.disconnect_buses()
            self._transform_edit.deleteLater()
            self._transform_edit = None

        if self._actor is None:
            return

        self._transform_edit = TransformEdit(self, self._actor, 160)
        perf_log(
            f"_add_transform_edit: created new _transform_edit, actor={self._actor_path}, id={id(self._transform_edit)}",
            feature="TRACE_LIFECYCLE",
        )
        self._transform_edit.connect_buses()
        self._property_layout.addWidget(self._transform_edit)
        self._transform_edit.show()

    def _load_properties(self):
        self._cancel_pending_render()
        self._hide_active_sections()

        if self._actor is None:
            self._active_cache_key = None
            self._show_empty()
            return

        cache_key = self._cache_key()
        self._active_cache_key = cache_key

        if cache_key is not None and cache_key in self._section_cache:
            perf_log(
                f"property_editor._load_properties: cache hit for {cache_key}",
                feature="PROPERTY",
            )
            self._show_cached_sections(cache_key)
            return

        self._clear_property_layout()

        perf_log(
            f"property_editor._load_properties: actor={self._actor.name}, "
            f"entity={self._entity.name if self._entity else None}, "
            f"entity_id={self._entity.entity_id if self._entity else None}, "
            f"cache_key={cache_key}",
            feature="PROPERTY",
        )

        if self._entity is not None:
            self._load_entity_properties()
        else:
            self._load_actor_properties()

    def _show_cached_sections(self, cache_key: tuple):
        self._clear_property_layout()

        cached = self._section_cache.get(cache_key)
        if cached is None:
            return

        if cache_key[1] is None:
            self._add_transform_edit()

        self._property_edits = list(cached)

        for edit in cached:
            self._property_layout.addWidget(edit)
            edit.show()

        self._section_cache.move_to_end(cache_key)

        if isinstance(self._actor, AssetActor) and cached:
            cached_groups = [edit._group for edit in cached]
            self._actor.property_groups = cached_groups

    def _load_actor_properties(self):
        assert self._actor is not None

        if self._actor_path is None:
            return

        if isinstance(self._actor, AssetActor) and self._actor.property_groups:
            # logger.info(
            #     f"[PropertyEditor] _load_actor_properties: actor={self._actor.name}, "
            #     f"has_raw_entries={bool(self._raw_entries)}, "
            #     f"raw_entries_count={len(self._raw_entries)}, "
            #     f"property_groups_count={len(self._actor.property_groups)}"
            # )
            if self._raw_entries:
                self._data_store.set_data_from_entries(self._raw_entries)
                self._filter_bar.set_available_types(
                    self._data_store.get_component_type_items()
                )
            self._render_from_data_store()
            return

        self._fetch_and_render_all(self._actor_path)

    def _load_entity_properties(self):
        assert self._entity is not None
        assert self._actor is not None

        if self._actor_path is None:
            return

        self._fetch_and_render_entity(self._actor_path, self._entity.entity_id)

    def _fetch_and_render_all(self, actor_path: Path):
        async def _fetch():
            try:
                with perf_timer(
                    "property_editor._fetch_and_render_all.total", feature="PROPERTY"
                ):
                    remote_scene = get_remote_scene()

                    with perf_timer(
                        "property_editor._fetch_and_render_all.grpc_get_all",
                        feature="PROPERTY",
                    ):
                        entries = await remote_scene.get_all_entity_property_groups(
                            actor_path
                        )

                    if not entries:
                        logger.info(f"[Actor] no entries for {actor_path}")
                        return

                    perf_log(
                        f"property_editor._fetch_and_render_all: got {len(entries)} entries",
                        feature="PROPERTY",
                    )

                    groups = [e.property_group for e in entries]
                    for e in entries:
                        e.property_group.entity_id = e.entity_id
                    keys: list[ActorPropertyKey] = []
                    props: list[ActorProperty] = []
                    collect_properties(keys, props, groups, actor_path)
                    if keys:
                        with perf_timer(
                            "property_editor._fetch_and_render_all.grpc_get_values",
                            feature="PROPERTY",
                        ):
                            values = await remote_scene.get_properties(keys)
                        for prop, value in zip(props, values):
                            if value is not None:
                                prop.set_value(value)
                                prop.set_original_value(value)

                    self._raw_entries = entries

                    with perf_timer(
                        "property_editor._fetch_and_render_all.data_store_set",
                        feature="PROPERTY",
                    ):
                        self._data_store.set_data_from_entries(entries)

                    if isinstance(self._actor, AssetActor):
                        self._actor.property_groups = self._sort_property_groups(groups)

                    self._filter_bar.set_available_types(
                        self._data_store.get_component_type_items()
                    )

                    with perf_timer(
                        "property_editor._fetch_and_render_all.render",
                        feature="PROPERTY",
                    ):
                        self._render_from_data_store()
            except Exception as e:
                logger.warning(f"Failed to load actor components: {e}")

        self._pending_render_task = asyncio.create_task(_fetch())

    async def _fetch_and_render_entity_async(self, actor_path: Path, entity_id: int):
        with perf_timer(
            "property_editor._fetch_and_render_entity.total", feature="PROPERTY"
        ):
            entity_root = get_local_scene().get_entity_root(actor_path)
            if entity_root is None:
                return

            entity_info = entity_root.find_entity_info(entity_id)

            entity_ids = [entity_id]
            if entity_info and self._recursive:
                entity_ids = entity_info.collect_entity_ids()

            batch_results = await get_remote_scene().get_entity_property_groups_batch(
                actor_path, entity_ids
            )

            all_groups: list[ActorPropertyGroup] = []
            for entity_idx, groups in enumerate(batch_results):
                if groups:
                    sorted_groups = self._sort_property_groups(groups)
                    child_entity_id = entity_ids[entity_idx]
                    for g in sorted_groups:
                        g.entity_id = child_entity_id
                    all_groups.extend(sorted_groups)

            if not all_groups:
                return

            keys: list[ActorPropertyKey] = []
            props: list[ActorProperty] = []
            collect_properties(keys, props, all_groups, actor_path)
            if keys:
                with perf_timer(
                    "property_editor._fetch_and_render_entity.grpc_get_values_batch",
                    feature="PROPERTY",
                ):
                    values = await get_remote_scene().get_properties(keys)
                for prop, value in zip(props, values):
                    if value is not None:
                        prop.set_value(value)
                        prop.set_original_value(value)

            if isinstance(self._actor, AssetActor):
                self._actor.property_groups = all_groups

            self._set_transform_read_only(all_groups)

            self._data_store.set_data_from_groups(
                all_groups, entity_id, str(actor_path)
            )
            self._filter_bar.set_available_types(
                self._data_store.get_component_type_items()
            )

            with perf_timer(
                "property_editor._fetch_and_render_entity.render",
                feature="PROPERTY",
            ):
                self._render_from_data_store()

    def _fetch_and_render_entity(self, actor_path: Path, entity_id: int):
        self._pending_render_task = asyncio.create_task(
            self._fetch_and_render_entity_async(actor_path, entity_id)
        )

    def _clear_property_groups_only(self):
        for edit in self._property_edits:
            edit.disconnect_buses()
        self._property_edits.clear()

        cached_ids = self._cached_widget_ids()
        i = self._property_layout.count() - 1
        while i >= 0:
            item = self._property_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), PropertyGroupEdit):
                w = item.widget()
                self._property_layout.removeWidget(w)
                w.hide()
                if id(w) not in cached_ids:
                    w.deleteLater()
            i -= 1

    def _render_from_data_store(self):
        self._clear_property_groups_only()

        if self._actor is None:
            return

        if self._entity is None:
            self._add_transform_edit()
            perf_log(
                f"property_editor._render_from_data_store: entity=None (actor selected), "
                f"data_store has {len(self._data_store.items)} items, skipping component groups",
                feature="PROPERTY",
            )
            return

        search_text = self._filter_bar.get_search_text()
        selected_types = self._filter_bar.get_selected_component_types()

        if not self._show_transform:
            all_types = set(self._data_store.available_component_types)
            transform_types = {t for t in all_types if "transform" in t.lower()}
            if selected_types is not None:
                selected_types = selected_types - transform_types
            else:
                selected_types = all_types - transform_types

        # Log data store contents before filtering
        all_ids = set(item.entity_id for item in self._data_store.items)
        all_paths = set(item.entity_path for item in self._data_store.items)
        all_component_types = set(
            item.component_type for item in self._data_store.items
        )
        perf_log(
            f"property_editor._render_from_data_store: "
            f"entity={self._entity.entity_id if self._entity else 'None'}, "
            f"data_store_items={len(self._data_store.items)}, "
            f"unique_entity_ids={all_ids}, "
            f"unique_entity_paths={all_paths}, "
            f"component_types={all_component_types}, "
            f"selected_types={selected_types}",
            feature="PROPERTY",
        )

        groups = self._data_store.get_property_groups_for_display(
            component_types=selected_types,
            search_text=search_text,
        )

        perf_log(
            f"property_editor._render_from_data_store: after filter, "
            f"groups={len(groups)}, "
            f"group_names=[{', '.join(g.name for g in groups)}]",
            feature="PROPERTY",
        )

        if not groups:
            return

        sorted_groups = self._sort_property_groups(groups)
        self._render_property_groups(sorted_groups, 160)

    def _apply_filter(self):
        if self._actor is None:
            return

        if not self._data_store.items:
            return

        cache_key = self._cache_key()
        if cache_key is not None and cache_key in self._section_cache:
            del self._section_cache[cache_key]

        self._render_from_data_store()

    @staticmethod
    def _sort_property_groups(
        groups: list[ActorPropertyGroup],
    ) -> list[ActorPropertyGroup]:
        def _sort_key(g: ActorPropertyGroup):
            name_lower = g.name.lower()
            if "transform" in name_lower:
                return 0
            return 1

        return sorted(groups, key=_sort_key)

    @staticmethod
    def _set_transform_read_only(groups: list[ActorPropertyGroup]):
        for group in groups:
            if "transform" in group.name.lower():
                for prop in group.properties:
                    prop.set_read_only(True)

    def _render_property_groups(
        self,
        groups: list[ActorPropertyGroup],
        label_width: int,
        read_only: bool = False,
    ):
        if self._actor is None:
            return

        cache_key = self._cache_key()

        perf_log(
            f"property_editor._render_property_groups: rendering {len(groups)} groups",
            feature="PROPERTY",
        )

        self._cancel_pending_render()

        actor = self._actor

        async def _render_batched():
            new_edits: list[PropertyGroupEdit] = []
            batch_count = 0

            for i, group in enumerate(groups):
                if self._pending_render_task is None:
                    return

                with perf_timer(
                    f"property_editor._render_property_groups.group[{i}]({group.name})",
                    feature="PROPERTY",
                ):
                    collapsed = self._recursive
                    edit = PropertyGroupEdit(
                        self, actor, group, label_width, collapsed=collapsed
                    )
                    edit.connect_buses()

                    if read_only:
                        edit.set_read_only(True)

                    new_edits.append(edit)
                    self._property_edits.append(edit)
                    self._property_layout.addWidget(edit)

                batch_count += 1
                if batch_count >= _RENDER_BATCH_SIZE:
                    batch_count = 0
                    await asyncio.sleep(0)

            if cache_key is not None:
                self._section_cache[cache_key] = new_edits
                self._active_cache_key = cache_key
                self._evict_cache_if_needed()

            perf_log(
                f"property_editor._render_property_groups: {len(new_edits)} groups rendered",
                feature="PROPERTY",
            )

        self._pending_render_task = asyncio.create_task(_render_batched())

    @override
    async def on_active_actor_changed(
        self,
        old_active_actor: Path | None,
        new_active_actor: Path | None,
        source: str = "",
    ) -> None:
        if new_active_actor is None:
            if self._actor is not None:
                self.clear_selection()
        else:
            local_scene = get_local_scene()
            actor = local_scene.find_actor_by_path(new_active_actor)
            if actor is not None and actor != self._actor:
                self.set_actor(actor)

    @override
    async def on_selection_changed(
        self,
        old_selection: SelectionData,
        new_selection: SelectionData,
        source: str = "",
    ) -> None:
        with perf_timer("property_editor.on_selection_changed", feature="PROPERTY"):
            active_actor_path = new_selection.active_actor_path
            active_entity_path = new_selection.active_entity_path

            if active_actor_path is None and active_entity_path.empty():
                self.clear_selection()
                return

            if active_actor_path is None:
                logger.error(
                    "[Coding Error] on_selection_changed: active_entity is set but active_actor is None. This should not happen."
                )
                self.clear_selection()
                return

            local_scene = get_local_scene()
            actor = local_scene.find_actor_by_path(active_actor_path)

            if active_entity_path.empty():
                self.set_actor(actor)
                return

            if not isinstance(actor, AssetActor):
                logger.error(
                    f"[Coding Error] on_selection_changed: active_entity is set but active_actor {active_actor_path} is not an AssetActor. This should not happen."
                )
                self.clear_selection()
                return

            entity_info = actor.entity_root.find_entity_info_by_path(active_entity_path)
            if entity_info is None:
                logger.error(
                    f"Cannot find entity for path {active_entity_path} under actor {active_actor_path}."
                )
                self.set_actor(actor)
                return

            self.set_entity(actor, entity_info, active_actor_path)
