import asyncio
import logging
from collections import OrderedDict
from typing import override

from PySide6 import QtCore, QtWidgets

from orcalab.actor import BaseActor, AssetActor
from orcalab.actor_property import ActorPropertyGroup, EntityPropertyGroupEntry
from orcalab.application_util import get_local_scene, get_remote_scene
from orcalab.entity_info import EntityInfo
from orcalab.path import Path
from orcalab.perf_log import perf_timer, perf_log
from orcalab.ui.collapsible.collapsible_section import CollapsibleSection
from orcalab.ui.filter_bar import FilterBar
from orcalab.ui.property_data_store import PropertyDataStore
from orcalab.ui.property_edit.property_group_edit import PropertyGroupEdit
from orcalab.ui.property_edit.transform_edit import TransformEdit
from orcalab.ui.theme_service import ThemeService

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
        self._transform_edit: TransformEdit | None = None
        self._property_edits: list[PropertyGroupEdit] = []
        self._raw_entries: list[EntityPropertyGroupEntry] = []

        self._section_cache: OrderedDict[tuple, tuple[TransformEdit | None, list[PropertyGroupEdit]]] = OrderedDict()
        self._active_cache_key: tuple | None = None
        self._pending_render_task: asyncio.Task | None = None

        self._container = QtWidgets.QWidget()
        self._main_layout = QtWidgets.QVBoxLayout(self._container)
        self._main_layout.setContentsMargins(4, 4, 4, 4)
        self._main_layout.setSpacing(4)

        self._filter_bar = FilterBar()
        self._filter_bar.filter_changed.connect(self._apply_filter)
        self._main_layout.addWidget(self._filter_bar)

        self._property_layout = QtWidgets.QVBoxLayout()
        self._property_layout.setContentsMargins(0, 0, 0, 0)
        self._property_layout.setSpacing(4)
        self._main_layout.addLayout(self._property_layout)

        self._main_layout.addStretch()

        self.setWidget(self._container)
        self.setWidgetResizable(True)

        self._show_empty()

    def _cache_key(self) -> tuple | None:
        if self._actor_path is None:
            return None
        if self._entity is not None:
            return (str(self._actor_path), self._entity.entity_id)
        return (str(self._actor_path), None)

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

        logger.info(
            f"[set_entity] actor={actor.name}, entity={entity.name} "
            f"(entity_id={entity.entity_id}), actor_path={actor_path}"
        )

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

    def _cancel_pending_render(self):
        if self._pending_render_task is not None:
            self._pending_render_task.cancel()
            self._pending_render_task = None

    def _clear_cache(self):
        for cached_transform, cached_edits in self._section_cache.values():
            if cached_transform is not None:
                cached_transform.disconnect_buses()
                cached_transform.deleteLater()
            for edit in cached_edits:
                edit.disconnect_buses()
                edit.deleteLater()
        self._section_cache.clear()
        self._active_cache_key = None

    def _evict_cache_if_needed(self):
        while len(self._section_cache) > _MAX_CACHE_SIZE:
            oldest_key, (oldest_transform, oldest_edits) = next(iter(self._section_cache.items()))
            if oldest_key == self._active_cache_key:
                self._section_cache.move_to_end(oldest_key)
                if len(self._section_cache) <= _MAX_CACHE_SIZE:
                    break
                oldest_key, (oldest_transform, oldest_edits) = next(iter(self._section_cache.items()))
            if oldest_transform is not None:
                oldest_transform.disconnect_buses()
                oldest_transform.deleteLater()
            for edit in oldest_edits:
                edit.disconnect_buses()
                edit.deleteLater()
            del self._section_cache[oldest_key]

    def _hide_active_sections(self):
        if self._active_cache_key is not None:
            cached = self._section_cache.get(self._active_cache_key)
            if cached is not None:
                cached_transform, cached_edits = cached
                if cached_transform is not None:
                    cached_transform.hide()
                for edit in cached_edits:
                    edit.hide()

        for edit in self._property_edits:
            edit.hide()
        self._property_edits.clear()

        if self._transform_edit is not None:
            self._transform_edit.hide()
            self._transform_edit = None

        while self._property_layout.count():
            item = self._property_layout.takeAt(0)
            if item.widget():
                w = item.widget()
                self._property_layout.removeWidget(w)
                w.setParent(None)
            elif item.layout():
                self._property_layout.removeItem(item)

    def _clear_property_layout(self):
        for edit in self._property_edits:
            edit.disconnect_buses()
        self._property_edits.clear()

        if self._transform_edit:
            self._transform_edit.disconnect_buses()
            self._transform_edit = None

        while self._property_layout.count():
            item = self._property_layout.takeAt(0)
            if item.widget():
                w = item.widget()
                self._property_layout.removeWidget(w)
                w.setParent(None)
            elif item.layout():
                self._property_layout.removeItem(item)

    def _show_empty(self):
        self._clear_property_layout()
        label = QtWidgets.QLabel("没有选中任何对象")
        label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter
            | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self._property_layout.addWidget(label)

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

        cached_transform, cached_edits = cached
        self._property_edits = list(cached_edits)

        if self._entity is not None:
            label = QtWidgets.QLabel(f"Entity: {self._entity.name}")
            label.setContentsMargins(4, 4, 4, 4)
            self._property_layout.addWidget(label)

            self._add_entity_transform_display(self._entity)
        elif self._actor is not None:
            label = QtWidgets.QLabel(f"Actor: {self._actor.name}")
            label.setContentsMargins(4, 4, 4, 4)
            self._property_layout.addWidget(label)

            if cached_transform is not None:
                self._transform_edit = cached_transform
                self._property_layout.addWidget(cached_transform)
                cached_transform.show()

        for edit in cached_edits:
            self._property_layout.addWidget(edit)
            edit.show()

        self._section_cache.move_to_end(cache_key)

    def _load_actor_properties(self):
        assert self._actor is not None

        label = QtWidgets.QLabel(f"Actor: {self._actor.name}")
        label.setContentsMargins(4, 4, 4, 4)
        self._property_layout.addWidget(label)

        self._transform_edit = TransformEdit(self, self._actor, 160)
        self._transform_edit.connect_buses()
        self._property_layout.addWidget(self._transform_edit)

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

        label = QtWidgets.QLabel(f"Entity: {self._entity.name}")
        label.setContentsMargins(4, 4, 4, 4)
        self._property_layout.addWidget(label)

        self._add_entity_transform_display(self._entity)

        if self._actor_path is None:
            return

        self._fetch_and_render_entity(self._actor_path, self._entity.entity_id)

    def _add_entity_transform_display(self, _entity: EntityInfo):
        theme = ThemeService()
        text_disable = theme.get_color_hex("text_disable")

        def _create_transform_readonly() -> QtWidgets.QWidget:
            content = QtWidgets.QWidget()
            form = QtWidgets.QFormLayout(content)
            form.setContentsMargins(4, 4, 4, 4)
            form.setSpacing(4)
            form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

            for field_name in ("Position:", "Rotation:", "Scale:"):
                lbl = QtWidgets.QLabel("(由引擎驱动)")
                lbl.setStyleSheet(f"color: {text_disable}; font-style: italic;")
                form.addRow(field_name, lbl)

            return content

        section = CollapsibleSection(
            parent=self,
            title="Transform",
            badge="只读",
            collapsed=False,
            content_factory=_create_transform_readonly,
        )
        self._property_layout.addWidget(section)

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

                    self._raw_entries = entries

                    with perf_timer("property_editor._fetch_and_render_all.data_store_set", feature="PROPERTY"):
                        self._data_store.set_data_from_entries(entries)

                    if isinstance(self._actor, AssetActor):
                        groups = [e.property_group for e in entries]
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

                    entity_ids = entity_info.collect_entity_ids() if entity_info else [entity_id]

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

                        sorted_groups = self._sort_property_groups(groups)

                        if isinstance(self._actor, AssetActor):
                            self._actor.property_groups = sorted_groups

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

                        if isinstance(self._actor, AssetActor):
                            self._actor.property_groups = all_groups

                        with perf_timer("property_editor._fetch_and_render_entity.render", feature="PROPERTY"):
                            self._render_property_groups(all_groups, 160)
            except Exception as e:
                logger.warning(f"Failed to load entity components: {e}", exc_info=True)

        self._pending_render_task = asyncio.create_task(_fetch())

    def _render_from_data_store(self):
        self._clear_property_layout()

        if self._actor is None:
            return

        search_text = self._filter_bar.get_search_text()
        selected_types = self._filter_bar.get_selected_component_types()

        groups = self._data_store.get_property_groups_for_display(
            component_types=selected_types,
            search_text=search_text,
        )

        if not groups:
            label = QtWidgets.QLabel("无匹配属性")
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self._property_layout.addWidget(label)
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

    def _render_property_groups(
        self, groups: list[ActorPropertyGroup], label_width: int
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
                    collapsed = i > 0
                    edit = PropertyGroupEdit(self, actor, group, label_width, collapsed=collapsed)
                    edit.connect_buses()
                    new_edits.append(edit)
                    self._property_edits.append(edit)
                    self._property_layout.addWidget(edit)

                batch_count += 1
                if batch_count >= _RENDER_BATCH_SIZE:
                    batch_count = 0
                    await asyncio.sleep(0)

            if cache_key is not None:
                self._section_cache[cache_key] = (self._transform_edit, new_edits)
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
            logger.info(
                f"[on_active_entity_changed] old={old_active_entity}, new={new_active_entity}, source={source}"
            )
            if new_active_entity is None:
                if self._entity is not None:
                    if self._actor is not None:
                        self.set_actor(self._actor)
                    else:
                        self.clear_selection()
            else:
                actor_path, entity_id = new_active_entity
                with perf_timer("property_editor.on_active_entity_changed.find_actor", feature="PROPERTY"):
                    local_scene = get_local_scene()
                    actor = local_scene.find_actor_by_path(actor_path)
                if actor is None:
                    logger.warning(
                        f"[on_active_entity_changed] actor not found for path={actor_path}"
                    )
                    return

                with perf_timer("property_editor.on_active_entity_changed.find_entity", feature="PROPERTY"):
                    entity_info = local_scene.find_entity_info_by_id(actor_path, entity_id)
                if entity_info is None:
                    logger.warning(
                        f"[on_active_entity_changed] entity_info not found for "
                        f"actor_path={actor_path}, entity_id={entity_id}"
                    )
                    return

                self.set_entity(actor, entity_info, actor_path)
