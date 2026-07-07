import asyncio
import logging
from collections import OrderedDict
from typing_extensions import override

from PySide6 import QtCore, QtWidgets

from orcalab.actor import BaseActor, AssetActor, GroupActor
from orcalab.actor_property import (
    ActorEntities,
    ActorProperty,
    ActorPropertyGroup,
    ActorPropertyKey,
)
from orcalab.application_util import get_local_scene, get_remote_scene
from orcalab.entity_info import EntityInfo
from orcalab.path import Path
from orcalab.perf_log import perf_timer, perf_log
from orcalab.selection_data import SelectionData
from orcalab.ui.filter_bar import FilterBar
from orcalab.ui.fonts.font_service import FontService
from orcalab.ui.property_data_store import PropertyDataStore
from orcalab.ui.property_edit.property_group_edit import PropertyGroupEdit

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

        self._cancel_pending_render()
        self._actor = None
        self._entity = None
        self._actor_path = None
        self._data_store.clear()
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

    def _clear_property_layout(self):
        for edit in self._property_edits:
            edit.disconnect_buses()
        self._property_edits.clear()

        while self._property_layout.count():
            item = self._property_layout.takeAt(self._property_layout.count() - 1)
            if item.widget():
                w = item.widget()
                self._property_layout.removeWidget(w)
                w.hide()
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

    def _load_properties(self):
        self._cancel_pending_render()
        self._clear_property_layout()

        if self._entity is not None:
            self._load_entity_properties()
        else:
            self._load_actor_properties()

    def _load_actor_properties(self):
        assert self._actor is not None
        assert self._actor_path is not None

        coro = self._fetch_and_render_actor_async(self._actor, self._actor_path)
        self._pending_render_task = asyncio.create_task(coro)

    def _load_entity_properties(self):
        assert self._entity is not None
        assert self._actor is not None

        if self._actor_path is None:
            return

        coro = self._fetch_and_render_entity_async(
            self._actor_path, self._entity.entity_id
        )
        self._pending_render_task = asyncio.create_task(coro)

    async def _fetch_and_render_actor_async(self, actor: BaseActor, actor_path: Path):
        remote_scene = get_remote_scene()

        groups = await remote_scene.get_actor_property_groups(actor_path)
        if not groups:
            logger.info(f"[Actor] no property groups for {actor_path}")
            return

        self._data_store.set_data_from_groups(groups)
        self._filter_bar.set_available_types(
            self._data_store.get_component_type_items()
        )

        self._render_from_data_store()

    async def _fetch_and_render_entity_async(self, actor_path: Path, entity_id: int):
        entity_root = get_local_scene().get_entity_root(actor_path)
        if entity_root is None:
            return

        remote_scene = get_remote_scene()

        entity_info = entity_root.find_entity_info(entity_id)
        assert entity_info is not None

        entity_ids = [entity_id]
        if self._recursive:
            entity_ids = entity_info.collect_entity_ids()

        results = await remote_scene.get_entity_property_groups(
            ActorEntities(actor_path, entity_ids)
        )

        all_groups: list[ActorPropertyGroup] = []
        for entity_idx, groups in enumerate(results):
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
        for group in all_groups:
            for prop in group.properties:
                key = ActorPropertyKey(
                    actor_path=actor_path,
                    entity_id=group.entity_id,
                    entity_path=entity_info.entity_path,
                    component_type_id=group.component_type_id,
                    component_type_index=group.component_type_index,
                    property_name=prop.name(),
                    property_type=prop.value_type(),
                )
                keys.append(key)
                props.append(prop)

        infos = await remote_scene.get_properties(keys, refill_entity_id=False)
        for prop, info in zip(props, infos):
            if info is not None:
                prop.set_value(info.value)
                prop.set_base_value(info.base_value)
                prop.set_read_only(info.read_only)

        self._data_store.set_data_from_groups(all_groups)
        self._filter_bar.set_available_types(
            self._data_store.get_component_type_items()
        )

        self._render_from_data_store()

    def _render_from_data_store(self):
        self._clear_property_layout()

        search_text = self._filter_bar.get_search_text()
        selected_types = self._filter_bar.get_selected_component_types()

        if not self._show_transform:
            all_types = set(self._data_store.available_component_types)
            transform_types = {t for t in all_types if "transform" in t.lower()}
            if selected_types is not None:
                selected_types = selected_types - transform_types
            else:
                selected_types = all_types - transform_types

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

        if not self._data_store.items:
            return

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
