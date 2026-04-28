import asyncio
import logging
from typing import override

from PySide6 import QtCore, QtWidgets

from orcalab.actor import BaseActor, AssetActor
from orcalab.actor_property import ActorPropertyGroup, EntityPropertyGroupEntry
from orcalab.application_util import get_local_scene, get_remote_scene
from orcalab.entity_info import EntityInfo
from orcalab.path import Path
from orcalab.ui.filter_bar import FilterBar
from orcalab.ui.property_data_store import PropertyDataStore
from orcalab.ui.property_edit.property_group_edit import PropertyGroupEdit
from orcalab.ui.property_edit.transform_edit import TransformEdit

from orcalab.scene_edit_bus import (
    SceneEditNotification,
    SceneEditNotificationBus,
)

logger = logging.getLogger(__name__)


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

        self._actor = actor
        self._entity = entity
        self._actor_path = actor_path
        self._load_properties()

    def clear_selection(self):
        if self._actor is None and self._entity is None:
            return

        self._actor = None
        self._entity = None
        self._actor_path = None
        self._data_store.clear()
        self._raw_entries.clear()
        self._show_empty()

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
        self._clear_property_layout()

        if self._actor is None:
            self._show_empty()
            return

        if self._entity is not None:
            self._load_entity_properties()
        else:
            self._load_actor_properties()

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

    def _add_entity_transform_display(self, entity: EntityInfo):
        group_box = QtWidgets.QGroupBox("Transform (只读)")
        group_box.setStyleSheet("QGroupBox { font-weight: bold; }")
        form = QtWidgets.QFormLayout()
        form.setContentsMargins(4, 8, 4, 4)
        form.setSpacing(4)

        label_style = "color: gray; font-style: italic;"

        for field_name in ("Position:", "Rotation:", "Scale:"):
            lbl = QtWidgets.QLabel("(由引擎驱动)")
            lbl.setStyleSheet(label_style)
            form.addRow(field_name, lbl)

        group_box.setLayout(form)
        self._property_layout.addWidget(group_box)

    def _fetch_and_render_all(self, actor_path: Path):
        async def _fetch():
            try:
                remote_scene = get_remote_scene()
                entries = await remote_scene.get_all_entity_property_groups(
                    actor_path
                )

                if not entries:
                    logger.info(f"[Actor] no entries for {actor_path}")
                    return

                self._raw_entries = entries
                self._data_store.set_data_from_entries(entries)

                if isinstance(self._actor, AssetActor):
                    groups = [e.property_group for e in entries]
                    self._actor.property_groups = self._sort_property_groups(groups)

                self._filter_bar.set_available_types(
                    self._data_store.available_component_types
                )
                self._render_from_data_store()
            except Exception as e:
                logger.warning(f"Failed to load actor components: {e}")

        asyncio.create_task(_fetch())

    def _fetch_and_render_entity(self, actor_path: Path, entity_id: int):
        async def _fetch():
            try:
                remote_scene = get_remote_scene()
                groups = await remote_scene.get_entity_property_groups(
                    actor_path, entity_id
                )

                if not groups:
                    logger.info(
                        f"[Entity] no groups for entity_id={entity_id}, "
                        f"falling back to actor-level groups"
                    )
                    self._fetch_and_render_all(actor_path)
                    return

                sorted_groups = self._sort_property_groups(groups)

                if isinstance(self._actor, AssetActor):
                    self._actor.property_groups = sorted_groups

                self._render_property_groups(sorted_groups, 160)
            except Exception as e:
                logger.warning(f"Failed to load entity components: {e}", exc_info=True)

        asyncio.create_task(_fetch())

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
        for group in groups:
            edit = PropertyGroupEdit(self, self._actor, group, label_width)
            edit.connect_buses()
            self._property_edits.append(edit)
            self._property_layout.addWidget(edit)

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
            local_scene = get_local_scene()
            actor = local_scene.find_actor_by_path(actor_path)
            if actor is None:
                logger.warning(
                    f"[on_active_entity_changed] actor not found for path={actor_path}"
                )
                return

            entity_info = local_scene.find_entity_info_by_id(actor_path, entity_id)
            if entity_info is None:
                logger.warning(
                    f"[on_active_entity_changed] entity_info not found for "
                    f"actor_path={actor_path}, entity_id={entity_id}"
                )
                return

            self.set_entity(actor, entity_info, actor_path)
