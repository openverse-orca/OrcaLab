from typing import Any, List, override
from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.actor import BaseActor
from orcalab.actor_property import (
    ActorProperty,
    ActorPropertyGroup,
    ActorPropertyKey,
    ActorPropertyType,
    TreePropertyNode,
)
from orcalab.application_util import get_local_scene
from orcalab.path import Path
from orcalab.scene_edit_bus import (
    SceneEditNotification,
    SceneEditNotificationBus,
)
from orcalab.ui.icon import Icon
from orcalab.ui.icon_util import make_color_svg
from orcalab.ui.property_edit.base_property_edit import (
    BasePropertyEdit,
    PropertyEditContext,
)
from orcalab.ui.property_edit.bool_property_edit import BooleanPropertyEdit
from orcalab.ui.property_edit.float_property_edit import FloatPropertyEdit
from orcalab.ui.property_edit.int_property_edit import IntegerPropertyEdit
from orcalab.ui.property_edit.string_property_edit import StringPropertyEdit

from orcalab.ui.styled_widget import StyledWidget
from orcalab.ui.text_label import TextLabel
from orcalab.ui.theme_service import ThemeService


class PropertyGroupEditTitle(QtWidgets.QWidget):

    toggle_collapse = QtCore.Signal()

    def __init__(self, parent, name: str, hint: str):
        super().__init__(parent)
        root_layout = QtWidgets.QHBoxLayout(self)
        root_layout.setContentsMargins(4, 4, 4, 4)
        root_layout.setSpacing(0)

        self.l_indicator = Icon()
        self.l_indicator.set_icon_size(20)

        l_name = QtWidgets.QLabel(name)
        l_hint = TextLabel(hint)
        l_hint.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed
        )
        l_hint.text_color = QtGui.QColor("gray")
        font = l_hint.font()
        font.setPointSize(12)
        l_hint.setFont(font)
        l_hint.elide_mode = QtCore.Qt.TextElideMode.ElideLeft

        root_layout.addWidget(self.l_indicator)
        root_layout.addWidget(l_name)
        root_layout.addSpacing(10)
        root_layout.addStretch()
        root_layout.addWidget(l_hint)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.toggle_collapse.emit()


class PropertyGroupEdit(StyledWidget, SceneEditNotification):

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        actor: BaseActor,
        group: ActorPropertyGroup,
        label_width: int,
    ):
        super().__init__(parent)
        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(4, 4, 4, 4)
        root_layout.setSpacing(0)

        self._actor = actor
        self._group = group
        self._label_width = label_width

        scene = get_local_scene()
        actor_path = scene.get_actor_path(actor)
        assert actor_path is not None
        self._actor_path = actor_path

        self._property_edits: List[BasePropertyEdit] = []

        title_area = PropertyGroupEditTitle(self, group.name, group.hint)
        title_area.setFixedHeight(24)
        title_area.toggle_collapse.connect(self.toggle_collapse)

        content_area = QtWidgets.QWidget()
        root_layout.addWidget(title_area)
        root_layout.addWidget(content_area)

        content_layout = QtWidgets.QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)

        for prop in group.properties:
            if prop.value_type() == ActorPropertyType.TREE:
                self._render_tree_data_flat(group.tree_data, content_layout, label_width)
            else:
                editor = self._create_property_edit(prop, label_width)
                if prop.is_read_only():
                    editor.set_read_only(True)
                self._property_edits.append(editor)
                content_layout.addWidget(editor)

        self._title_area = title_area
        self._content_area = content_area

        theme = ThemeService()
        bg_color = theme.get_color_hex("property_group_bg")
        text_color = theme.get_color("text")
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {bg_color};
                border-radius: 4px;
            }}
            """
        )

        self._expand_icon = make_color_svg(":/icons/chevron_down.svg", text_color)
        self._collapse_icon = make_color_svg(":/icons/chevron_right.svg", text_color)

        self._title_area.l_indicator.set_pixmap(self._expand_icon)

    def connect_buses(self):
        SceneEditNotificationBus.connect(self)

    def disconnect_buses(self):
        SceneEditNotificationBus.disconnect(self)

    def _create_property_edit(
        self, prop: ActorProperty, label_width: int, name_prefix: str = ""
    ) -> BasePropertyEdit:
        context = PropertyEditContext(
            actor=self._actor,
            actor_path=self._actor_path,
            group=self._group,
            prop=prop.create_alias(f"{name_prefix}{prop.name()}") if name_prefix else prop,
        )

        match prop.value_type():
            case ActorPropertyType.BOOL:
                return BooleanPropertyEdit(self, context, label_width)
            case ActorPropertyType.INTEGER:
                return IntegerPropertyEdit(self, context, label_width)
            case ActorPropertyType.FLOAT:
                return FloatPropertyEdit(self, context, label_width)
            case ActorPropertyType.STRING:
                return StringPropertyEdit(self, context, label_width)
            case _:
                raise NotImplementedError("Unsupported property type")

    def _render_tree_data_flat(
        self,
        nodes: List[TreePropertyNode],
        layout: QtWidgets.QVBoxLayout,
        label_width: int,
        indent: int = 0,
        name_prefix: str = "",
    ):
        theme = ThemeService()
        text_color = theme.get_color_hex("text")
        indent_px = indent * 20

        for node in nodes:
            header_row = QtWidgets.QWidget()
            header_layout = QtWidgets.QHBoxLayout(header_row)
            header_layout.setContentsMargins(indent_px, 2, 4, 2)
            header_layout.setSpacing(4)

            if node.children:
                indicator = QtWidgets.QLabel("▾")
                indicator.setStyleSheet(f"color: {text_color}; font-weight: bold;")
                header_layout.addWidget(indicator)

            name_label = QtWidgets.QLabel(node.display_name)
            name_label.setStyleSheet(f"color: {text_color}; font-weight: bold;")
            header_layout.addWidget(name_label)
            header_layout.addStretch()
            layout.addWidget(header_row)

            node_prefix = f"{name_prefix}{node.name}." if name_prefix else f"{node.name}."

            for prop in node.properties:
                editor = self._create_property_edit(prop, label_width, name_prefix=node_prefix)
                if prop.is_read_only():
                    editor.set_read_only(True)

                prop_row = QtWidgets.QWidget()
                row_layout = QtWidgets.QHBoxLayout(prop_row)
                row_layout.setContentsMargins((indent + 1) * 20, 0, 0, 0)
                row_layout.setSpacing(0)
                row_layout.addWidget(editor)
                row_layout.addStretch()

                self._property_edits.append(editor)
                layout.addWidget(prop_row)

            if node.children:
                self._render_tree_data_flat(
                    node.children, layout, label_width,
                    indent=indent + 1, name_prefix=node_prefix,
                )

    #
    # SceneEditNotificationBus overrides
    #

    def _compute_new_path(self, renamed_path: Path, new_name: str) -> Path | None:
        """如果重命名操作影响了当前 actor 路径，返回更新后的路径，否则返回 None。"""
        new_renamed = renamed_path.parent() / new_name
        if self._actor_path == renamed_path:
            return new_renamed
        if self._actor_path.is_descendant_of(renamed_path):
            suffix = self._actor_path.string()[len(renamed_path.string()):]
            return Path(new_renamed.string() + suffix)
        return None

    @override
    async def on_actor_renamed(self, actor_path: Path, new_name: str, source: str):
        new_path = self._compute_new_path(actor_path, new_name)
        if new_path is None:
            return

        self._actor_path = new_path
        for edit in self._property_edits:
            edit.context.actor_path = new_path
            edit.context.key.actor_path = new_path

    @override
    async def on_property_changed(
        self,
        property_key: ActorPropertyKey,
        value: Any,
        source: str,
    ):
        if property_key.actor_path != self._actor_path:
            return

        if property_key.group_prefix != self._group.prefix:
            return

        if source == "ui":
            return

        for edit in self._property_edits:
            if edit.context.prop.name() == property_key.property_name:
                edit.set_value(value)
                return

    @override
    async def on_property_read_only_changed(
        self,
        actor_path,
        group_prefix: str,
        property_name: str,
        read_only: bool,
    ):
        if actor_path != self._actor_path:
            return

        if group_prefix != self._group.prefix:
            return

        for edit in self._property_edits:
            if edit.context.prop.name() == property_name:
                edit.set_read_only(read_only)
                return

    def expand(self):
        self._content_area.show()
        self._title_area.l_indicator.set_pixmap(self._expand_icon)

    def collapse(self):
        self._content_area.hide()
        self._title_area.l_indicator.set_pixmap(self._collapse_icon)

    def toggle_collapse(self):
        if self._content_area.isVisible():
            self.collapse()
        else:
            self.expand()
