import asyncio
import logging
from collections import OrderedDict
from typing import override

from PySide6 import QtCore, QtWidgets

from orcalab.actor import BaseActor, AssetActor
from orcalab.actor_property import ActorProperty, ActorPropertyGroup, ActorPropertyKey, EntityPropertyGroupEntry
from orcalab.actor_util import collect_properties
from orcalab.application_util import get_local_scene, get_remote_scene
from orcalab.entity_info import EntityInfo
from orcalab.path import Path
from orcalab.perf_log import perf_timer, perf_log
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

        self._container = QtWidgets.QWidget()
        self._main_layout = QtWidgets.QVBoxLayout(self._container)
        self._main_layout.setContentsMargins(4, 4, 4, 4)
        self._main_layout.setSpacing(4)

        self._filter_bar = FilterBar()
        self._filter_bar.filter_changed.connect(self._apply_filter)
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
            return (str(self._actor_path), self._entity.entity_id, self._recursive)
        return (str(self._actor_path), None, self._recursive)

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

        perf_log(f"property_editor.set_entity: actor={actor.name}, entity={entity.name}, entity_id={entity.entity_id}", feature="PROPERTY")

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
        if self._entity is not None and self._actor is not None and self._actor_path is not None:
            self._load_properties()

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
            QtCore.Qt.AlignmentFlag.AlignCenter
            | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        FontService().bind_widget_font(label, 'body')
        self._property_layout.addWidget(label)

    def _add_transform_edit(self):
        if self._transform_edit is not None:
            self._transform_edit.deleteLater()
            self._transform_edit = None

        if self._actor is None:
            return

        self._transform_edit = TransformEdit(self, self._actor, 160)
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
            perf_log(f"property_editor._load_properties: cache hit for {cache_key}", feature="PROPERTY")
            self._show_cached_sections(cache_key)
            return

        self._clear_property_layout()

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

    def _load_actor_properties(self):
        assert self._actor is not None

        if self._actor_path is None:
            return

        if isinstance(self._actor, AssetActor) and self._actor.property_groups:
            self._data_store.set_data_from_entries(self._raw_entries) if self._raw_entries else None
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
                with perf_timer("property_editor._fetch_and_render_all.total", feature="PROPERTY"):
                    remote_scene = get_remote_scene()

                    with perf_timer("property_editor._fetch_and_render_all.grpc_get_all", feature="PROPERTY"):
                        entries = await remote_scene.get_all_entity_property_groups(
                            actor_path
                        )

                    if not entries:
                        logger.info(f"[Actor] no entries for {actor_path}")
                        return

                    perf_log(f"property_editor._fetch_and_render_all: got {len(entries)} entries", feature="PROPERTY")

                    groups = [e.property_group for e in entries]
                    keys: list[ActorPropertyKey] = []
                    props: list[ActorProperty] = []
                    collect_properties(keys, props, groups, actor_path)
                    if keys:
                        with perf_timer("property_editor._fetch_and_render_all.grpc_get_values", feature="PROPERTY"):
                            values = await remote_scene.get_properties(keys)
                        for prop, value in zip(props, values):
                            if value is not None:
                                prop.set_value(value)
                                prop.set_original_value(value)

                    self._raw_entries = entries

                    with perf_timer("property_editor._fetch_and_render_all.data_store_set", feature="PROPERTY"):
                        self._data_store.set_data_from_entries(entries)

                    if isinstance(self._actor, AssetActor):
                        self._actor.property_groups = self._sort_property_groups(groups)

                    self._filter_bar.set_available_types(
                        self._data_store.available_component_types
                    )

                    with perf_timer("property_editor._fetch_and_render_all.render", feature="PROPERTY"):
                        self._render_from_data_store()
            except Exception as e:
                logger.warning(f"Failed to load actor components: {e}")

        self._pending_render_task = asyncio.create_task(_fetch())

    def _fetch_and_render_entity(self, actor_path: Path, entity_id: int):
        async def _fetch():
            try:
                with perf_timer("property_editor._fetch_and_render_entity.total", feature="PROPERTY"):
                    entity_root = get_local_scene().get_entity_root(actor_path)
                    entity_info = entity_root.find_by_entity_id(entity_id) if entity_root else None

                    entity_ids = entity_info.collect_entity_ids() if (entity_info and self._recursive) else [entity_id]

                    if len(entity_ids) == 1:
                        with perf_timer("property_editor._fetch_and_render_entity.grpc_single", feature="PROPERTY"):
                            groups = await get_remote_scene().get_entity_property_groups(
                                actor_path, entity_id
                            )
                        if not groups:
                            logger.info(
                                f"[Entity] no groups for entity_id={entity_id}, "
                                f"skipping property display"
                            )
                            return

                        perf_log(f"property_editor._fetch_and_render_entity: got {len(groups)} groups for single entity", feature="PROPERTY")

                        keys: list[ActorPropertyKey] = []
                        props: list[ActorProperty] = []
                        collect_properties(keys, props, groups, actor_path)
                        if keys:
                            with perf_timer("property_editor._fetch_and_render_entity.grpc_get_values", feature="PROPERTY"):
                                values = await get_remote_scene().get_properties(keys)
                            for prop, value in zip(props, values):
                                if value is not None:
                                    prop.set_value(value)
                                    prop.set_original_value(value)

                        sorted_groups = self._sort_property_groups(groups)

                        if isinstance(self._actor, AssetActor):
                            self._actor.property_groups = sorted_groups

                        self._set_transform_read_only(sorted_groups)

                        with perf_timer("property_editor._fetch_and_render_entity.render", feature="PROPERTY"):
                            self._render_property_groups(sorted_groups, 160)
                    else:
                        with perf_timer("property_editor._fetch_and_render_entity.grpc_batch", feature="PROPERTY"):
                            batch_results = await get_remote_scene().get_entity_property_groups_batch(
                                actor_path, entity_ids
                            )

                        perf_log(f"property_editor._fetch_and_render_entity: batch got {len(batch_results)} results for {len(entity_ids)} entities", feature="PROPERTY")

                        all_groups: list[ActorPropertyGroup] = []
                        for groups in batch_results:
                            if groups:
                                sorted_groups = self._sort_property_groups(groups)
                                all_groups.extend(sorted_groups)

                        if not all_groups:
                            logger.info(
                                f"[Entity] no groups for entity_id={entity_id} and children, "
                                f"skipping property display"
                            )
                            return

                        keys: list[ActorPropertyKey] = []
                        props: list[ActorProperty] = []
                        collect_properties(keys, props, all_groups, actor_path)
                        if keys:
                            with perf_timer("property_editor._fetch_and_render_entity.grpc_get_values_batch", feature="PROPERTY"):
                                values = await get_remote_scene().get_properties(keys)
                            for prop, value in zip(props, values):
                                if value is not None:
                                    prop.set_value(value)
                                    prop.set_original_value(value)

                        if isinstance(self._actor, AssetActor):
                            self._actor.property_groups = all_groups

                        self._set_transform_read_only(all_groups)

                        with perf_timer("property_editor._fetch_and_render_entity.render", feature="PROPERTY"):
                            self._render_property_groups(all_groups, 160)
            except Exception as e:
                logger.warning(f"Failed to load entity components: {e}", exc_info=True)

        self._pending_render_task = asyncio.create_task(_fetch())

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

        self._add_transform_edit()

        search_text = self._filter_bar.get_search_text()
        selected_types = self._filter_bar.get_selected_component_types()

        groups = self._data_store.get_property_groups_for_display(
            component_types=selected_types,
            search_text=search_text,
        )

        if not groups:
            return

        sorted_groups = self._sort_property_groups(groups)
        self._render_property_groups(sorted_groups, 160)

    def _apply_filter(self):
        if self._actor is None:
            return

        if self._entity is not None:
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
        self, groups: list[ActorPropertyGroup], label_width: int, read_only: bool = False
    ):
        if self._actor is None:
            return

        cache_key = self._cache_key()

        perf_log(f"property_editor._render_property_groups: rendering {len(groups)} groups", feature="PROPERTY")

        self._cancel_pending_render()

        actor = self._actor

        async def _render_batched():
            new_edits: list[PropertyGroupEdit] = []
            batch_count = 0

            for i, group in enumerate(groups):
                if self._pending_render_task is None:
                    return

                with perf_timer(f"property_editor._render_property_groups.group[{i}]({group.name})", feature="PROPERTY"):
                    collapsed = self._recursive
                    edit = PropertyGroupEdit(self, actor, group, label_width, collapsed=collapsed)
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

            perf_log(f"property_editor._render_property_groups: {len(new_edits)} groups rendered", feature="PROPERTY")

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
    async def on_active_entity_changed(
        self,
        old_active_entity: tuple | None,
        new_active_entity: tuple | None,
        source: str = "",
    ) -> None:
        with perf_timer("property_editor.on_active_entity_changed", feature="PROPERTY"):
            if new_active_entity is None:
                if self._entity is not None:
                    if self._actor is not None:
                        self.set_actor(self._actor)
                    else:
                        self.clear_selection()
            else:
                actor_path, entity_id = new_active_entity
                local_scene = get_local_scene()
                actor = local_scene.find_actor_by_path(actor_path)
                if actor is not None:
                    entity_root = local_scene.get_entity_root(actor_path)
                    entity_info = entity_root.find_by_entity_id(entity_id) if entity_root else None
                    if entity_info is not None:
                        self.set_entity(actor, entity_info, actor_path)
