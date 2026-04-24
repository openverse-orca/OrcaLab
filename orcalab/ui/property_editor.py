import asyncio
import logging
from typing import override
from PySide6 import QtCore, QtWidgets

from orcalab.actor import BaseActor, AssetActor
from orcalab.actor_property import ActorPropertyGroup
from orcalab.application_util import get_local_scene
from orcalab.entity_info import EntityInfo
from orcalab.path import Path
from orcalab.ui.property_edit.property_group_edit import PropertyGroupEdit
from orcalab.ui.property_edit.transform_edit import TransformEdit

from orcalab.scene_edit_bus import (
    SceneEditNotification,
    SceneEditNotificationBus,
    SceneEditRequestBus,
)

logger = logging.getLogger(__name__)


class PropertyEditor(QtWidgets.QScrollArea, SceneEditNotification):

    def __init__(self, parent=None):
        super().__init__(parent)

        self._layout = QtWidgets.QVBoxLayout()
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(4)
        self._widget = QtWidgets.QWidget()
        self._widget.setLayout(self._layout)
        self._widget.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )

        self.setWidget(self._widget)
        self.setWidgetResizable(True)

        self._actor: BaseActor | None = None
        self._entity: EntityInfo | None = None
        self._actor_path: Path | None = None
        self._transform_edit: TransformEdit | None = None
        self._property_edits: list[PropertyGroupEdit] = []

        self._refresh()

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

        self._refresh()

    def set_entity(self, actor: BaseActor, entity: EntityInfo, actor_path: Path):
        if self._actor == actor and self._entity is entity:
            return

        self._actor = actor
        self._entity = entity
        self._actor_path = actor_path
        self._refresh()

    def clear_selection(self):
        if self._actor is None and self._entity is None:
            return

        self._actor = None
        self._entity = None
        self._actor_path = None
        self._refresh()

    def _clear_layout(self, layout=None):
        for edit in self._property_edits:
            edit.disconnect_buses()
        self._property_edits.clear()

        if self._transform_edit:
            self._transform_edit.disconnect_buses()
            self._transform_edit = None

        if layout is None:
            layout = self._layout
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                w = item.widget()
                layout.removeWidget(w)
                w.setParent(None)
            elif item.layout():
                self._clear_layout(item.layout())
                layout.removeItem(item)

    def _refresh(self):
        self._clear_layout()

        if self._actor is None:
            label = QtWidgets.QLabel("没有选中任何对象")
            label.setAlignment(
                QtCore.Qt.AlignmentFlag.AlignCenter
                | QtCore.Qt.AlignmentFlag.AlignVCenter
            )
            self._layout.addWidget(label)
            return

        label_width = 160

        if self._entity is not None:
            self._add_entity_mode_ui(label_width)
        else:
            self._add_actor_mode_ui(label_width)

    def _add_actor_mode_ui(self, label_width: int):
        assert self._actor is not None
        label = QtWidgets.QLabel(f"Actor: {self._actor.name}")
        label.setContentsMargins(4, 4, 4, 4)
        self._layout.addWidget(label)

        self._transform_edit = TransformEdit(self, self._actor, label_width)
        self._transform_edit.connect_buses()
        self._layout.addWidget(self._transform_edit)

    def _add_entity_mode_ui(self, label_width: int):
        assert self._entity is not None
        assert self._actor is not None
        label = QtWidgets.QLabel(f"Entity: {self._entity.name}")
        label.setContentsMargins(4, 4, 4, 4)
        self._layout.addWidget(label)

        self._add_entity_transform_display(self._entity)

        if isinstance(self._actor, AssetActor) and self._actor_path is not None:
            self._load_entity_components(self._actor_path, self._entity.entity_id, label_width)

    def _add_entity_transform_display(self, entity: EntityInfo):
        group_box = QtWidgets.QGroupBox("Transform (只读)")
        group_box.setStyleSheet(
            "QGroupBox { font-weight: bold; }"
        )
        form = QtWidgets.QFormLayout()
        form.setContentsMargins(4, 8, 4, 4)
        form.setSpacing(4)

        label_style = "color: gray; font-style: italic;"

        pos_label = QtWidgets.QLabel("(由引擎驱动)")
        pos_label.setStyleSheet(label_style)
        form.addRow("Position:", pos_label)

        rot_label = QtWidgets.QLabel("(由引擎驱动)")
        rot_label.setStyleSheet(label_style)
        form.addRow("Rotation:", rot_label)

        scale_label = QtWidgets.QLabel("(由引擎驱动)")
        scale_label.setStyleSheet(label_style)
        form.addRow("Scale:", scale_label)

        group_box.setLayout(form)
        self._layout.addWidget(group_box)

    def _load_entity_components(
        self, actor_path: Path, entity_id: int, label_width: int
    ):
        async def _fetch_and_render():
            try:
                groups = await SceneEditRequestBus().get_entity_property_groups(
                    actor_path, entity_id
                )

                def _sort_key(g: ActorPropertyGroup):
                    name_lower = g.name.lower()
                    if "transform" in name_lower:
                        return 0
                    return 1

                sorted_groups = sorted(groups, key=_sort_key)

                for group in sorted_groups:
                    if not isinstance(self._actor, AssetActor):
                        break
                    edit = PropertyGroupEdit(
                        self, self._actor, group, label_width
                    )
                    edit.connect_buses()
                    self._property_edits.append(edit)
                    self._layout.addWidget(edit)
            except Exception as e:
                logger.warning(f"Failed to load entity components: {e}")

        asyncio.create_task(_fetch_and_render())

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
                return

            entity_info = local_scene.find_entity_info_by_id(actor_path, entity_id)
            if entity_info is None:
                return

            self.set_entity(actor, entity_info, actor_path)
