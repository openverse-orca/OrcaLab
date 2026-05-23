from typing import List, Tuple

from PySide6 import QtWidgets

from orcalab.actor import BaseActor
from orcalab.actor_property import (
    ActorProperty,
    ActorPropertyGroup,
    ActorPropertyType,
    StructPropertyGroup,
    TreePropertyNode,
)
from orcalab.path import Path
from orcalab.ui.collapsible.collapsible_section import CollapsibleSection
from orcalab.ui.fonts.font_service import FontService
from orcalab.ui.icon_util import make_color_svg
from orcalab.ui.property_edit.base_property_edit import (
    BasePropertyEdit,
    PropertyEditContext,
)
from orcalab.ui.property_edit.bool_property_edit import BooleanPropertyEdit
from orcalab.ui.property_edit.combo_property_edit import ComboBoxPropertyEdit
from orcalab.ui.property_edit.float_property_edit import FloatPropertyEdit
from orcalab.ui.property_edit.int_property_edit import IntegerPropertyEdit
from orcalab.ui.property_edit.string_property_edit import StringPropertyEdit
from orcalab.ui.styled_widget import StyledWidget


def _indent_unit() -> int:
    return FontService().indent_unit_px(20)


def _create_property_edit(
    parent: QtWidgets.QWidget,
    actor: BaseActor,
    actor_path: Path,
    group: ActorPropertyGroup,
    prop: ActorProperty,
    label_width: int,
    name_prefix: str = "",
) -> BasePropertyEdit:
    context = PropertyEditContext(
        actor=actor,
        actor_path=actor_path,
        group=group,
        prop=prop.create_alias(f"{name_prefix}{prop.name()}") if name_prefix else prop,
    )

    match prop.value_type():
        case ActorPropertyType.BOOL:
            return BooleanPropertyEdit(parent, context, label_width)
        case ActorPropertyType.INTEGER:
            if prop.enum_values():
                return ComboBoxPropertyEdit(parent, context, label_width)
            return IntegerPropertyEdit(parent, context, label_width)
        case ActorPropertyType.FLOAT:
            return FloatPropertyEdit(parent, context, label_width)
        case ActorPropertyType.STRING:
            return StringPropertyEdit(parent, context, label_width)
        case _:
            raise NotImplementedError("Unsupported property type")


def _render_tree_data_flat(
    parent: QtWidgets.QWidget,
    actor: BaseActor,
    actor_path: Path,
    group: ActorPropertyGroup,
    nodes: List[TreePropertyNode],
    layout: QtWidgets.QVBoxLayout,
    label_width: int,
    property_edits: List[BasePropertyEdit],
    indent: int = 0,
    name_prefix: str = "",
):
    fs = FontService()
    indent_px = indent * _indent_unit()

    for node in nodes:
        header_row = QtWidgets.QWidget()
        header_layout = QtWidgets.QHBoxLayout(header_row)
        header_layout.setContentsMargins(indent_px, 2, 4, 2)
        header_layout.setSpacing(4)

        if node.children:
            indicator = QtWidgets.QLabel("▾")
            fs.bind_widget_font(indicator, 'group_title')
            header_layout.addWidget(indicator)

        name_label = QtWidgets.QLabel(node.display_name)
        fs.bind_widget_font(name_label, 'group_title')
        header_layout.addWidget(name_label)
        header_layout.addStretch()
        layout.addWidget(header_row)

        node_prefix = f"{name_prefix}{node.name}." if name_prefix else f"{node.name}."

        for prop in node.properties:
            editor = _create_property_edit(
                parent, actor, actor_path, group, prop, label_width, name_prefix=node_prefix
            )
            if prop.is_read_only():
                editor.set_read_only(True)

            prop_row = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(prop_row)
            row_layout.setContentsMargins((indent + 1) * _indent_unit(), 0, 0, 0)
            row_layout.setSpacing(0)
            row_layout.addWidget(editor)
            row_layout.addStretch()

            property_edits.append(editor)
            layout.addWidget(prop_row)

        if node.children:
            _render_tree_data_flat(
                parent, actor, actor_path, group,
                node.children, layout, label_width,
                property_edits,
                indent=indent + 1, name_prefix=node_prefix,
            )


def _build_struct_tree(
    group: ActorPropertyGroup,
) -> Tuple[List[StructPropertyGroup], List[ActorProperty]]:
    """V2: 从属性名的点号分隔符自动推断 struct 分组关系。

    C++ 侧 FlattenField 跳过 "Config" 前缀后，属性名如 "axis.x"、"axis.y"、"axis.z"
    仍然保留了父结构名和子字段名的点号分隔关系。由此可自动推断：
    - 父结构名: 点号前的部分 (如 "axis")
    - 子字段名: 点号后的部分 (如 "x", "y", "z")
    - 横排判定: 子字段名均为单字符且类型为 Float → Vector2/3/4 横排绘制
    """
    struct_groups: dict[str, List[ActorProperty]] = {}
    standalone_props: List[ActorProperty] = []

    for prop in group.properties:
        name = prop.name()
        dot_pos = name.find(".")
        if dot_pos != -1:
            parent_name = name[:dot_pos]
            struct_groups.setdefault(parent_name, []).append(prop)
        else:
            standalone_props.append(prop)

    if not struct_groups:
        return [], standalone_props

    def _is_tuple_group(g: StructPropertyGroup) -> bool:
        if g.children:
            return False
        if not g.properties:
            return False
        for p in g.properties:
            if p.value_type() != ActorPropertyType.FLOAT:
                return False
            name = p.name()
            dot_pos = name.rfind(".")
            sub = name[dot_pos + 1:] if dot_pos != -1 else name
            if len(sub) != 1:
                return False
        return True

    def _build(name: str, props: List[ActorProperty], display_override: str | None = None) -> StructPropertyGroup:
        display = display_override or name.capitalize()
        direct_props: List[ActorProperty] = []
        child_groups: dict[str, List[ActorProperty]] = {}

        for p in props:
            dot_pos = p.name().find(".")
            if dot_pos != -1:
                remaining = p.name()[dot_pos + 1:]
                next_dot = remaining.find(".")
                if next_dot != -1:
                    child_name = remaining[:next_dot]
                    child_groups.setdefault(child_name, []).append(p)
                else:
                    direct_props.append(p)
            else:
                direct_props.append(p)

        children = [_build(cn, cp, cn.capitalize()) for cn, cp in child_groups.items()]
        sg = StructPropertyGroup(name, display, direct_props, children)
        if _is_tuple_group(sg):
            sg.layout = "horizontal"
        return sg

    result = []
    for struct_name, props in struct_groups.items():
        result.append(_build(struct_name, props))

    return result, standalone_props


def _render_struct_group(
    parent: QtWidgets.QWidget,
    actor: BaseActor,
    actor_path: Path,
    group: ActorPropertyGroup,
    struct_group: StructPropertyGroup,
    label_width: int,
    property_edits: List[BasePropertyEdit],
    layout: QtWidgets.QVBoxLayout,
    indent_level: int = 0,
    collapsed: bool = True,
):
    """递归渲染结构体组为 CollapsibleSection"""
    section = CollapsibleSection(
        parent=parent,
        title=struct_group.display_name,
        collapsed=collapsed,
        indent_level=indent_level,
        content_factory=lambda sg=struct_group: _create_struct_content(
            parent, actor, actor_path, group,
            sg, label_width, property_edits,
            indent_level=indent_level,
            collapsed=collapsed,
        ),
    )
    layout.addWidget(section)


def _create_horizontal_tuple_content(
    parent: QtWidgets.QWidget,
    actor: BaseActor,
    actor_path: Path,
    group: ActorPropertyGroup,
    struct_group: StructPropertyGroup,
    property_edits: List[BasePropertyEdit],
    indent: int,
) -> QtWidgets.QWidget:
    """创建横向平铺的三元组/四元组内容行"""
    row = QtWidgets.QWidget()
    row_layout = QtWidgets.QHBoxLayout(row)
    row_layout.setContentsMargins(indent, 0, 0, 0)
    row_layout.setSpacing(8)

    fs = FontService()
    compact_label_width = fs.indent_unit_px(14)

    for prop in struct_group.properties:
        dot_pos = prop.name().rfind(".")
        sub_name = prop.name()[dot_pos + 1:] if dot_pos != -1 else prop.name()
        display_alias = prop.create_alias(prop.name())
        display_alias._display_name = sub_name.upper()
        editor = _create_property_edit(parent, actor, actor_path, group, display_alias, compact_label_width)
        if prop.is_read_only():
            editor.set_read_only(True)
        property_edits.append(editor)
        row_layout.addWidget(editor)

    row_layout.addStretch()
    return row


def _create_struct_content(
    parent: QtWidgets.QWidget,
    actor: BaseActor,
    actor_path: Path,
    group: ActorPropertyGroup,
    struct_group: StructPropertyGroup,
    label_width: int,
    property_edits: List[BasePropertyEdit],
    indent_level: int = 0,
    collapsed: bool = True,
) -> QtWidgets.QWidget:
    """创建结构体折叠区的内容（递归）"""
    content = StyledWidget()
    content_layout = QtWidgets.QVBoxLayout(content)
    content_layout.setContentsMargins(0, 0, 0, 0)
    content_layout.setSpacing(2)

    if struct_group.layout == "horizontal":
        prop_indent = (indent_level + 1) * _indent_unit()
        row = _create_horizontal_tuple_content(
            parent, actor, actor_path, group,
            struct_group, property_edits, prop_indent,
        )
        content_layout.addWidget(row)
    else:
        prop_indent = (indent_level + 1) * _indent_unit()
        for prop in struct_group.properties:
            editor = _create_property_edit(parent, actor, actor_path, group, prop, label_width)
            if prop.is_read_only():
                editor.set_read_only(True)
            property_edits.append(editor)

            row = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row)
            row_layout.setContentsMargins(prop_indent, 0, 0, 0)
            row_layout.setSpacing(0)
            row_layout.addWidget(editor)
            row_layout.addStretch()
            content_layout.addWidget(row)

    for child in struct_group.children:
        _render_struct_group(
            parent, actor, actor_path, group,
            child, label_width, property_edits,
            content_layout,
            indent_level=indent_level + 1,
            collapsed=collapsed,
        )

    return content


def create_property_group_content(
    parent: QtWidgets.QWidget,
    actor: BaseActor,
    actor_path: Path,
    group: ActorPropertyGroup,
    label_width: int,
    property_edits: List[BasePropertyEdit],
    collapsed: bool = True,
) -> QtWidgets.QWidget:
    content = StyledWidget()
    content_layout = QtWidgets.QVBoxLayout(content)
    content_layout.setContentsMargins(0, 0, 0, 0)
    content_layout.setSpacing(2)

    # 第一步：重建结构体树
    struct_roots, standalone_props = _build_struct_tree(group)

    # 第二步：渲染非结构体属性
    for prop in standalone_props:
        if prop.value_type() == ActorPropertyType.TREE:
            _render_tree_data_flat(
                parent, actor, actor_path, group,
                group.tree_data, content_layout, label_width,
                property_edits,
            )
        elif prop.editor_hint() in ("container", "struct"):
            editor = _create_property_edit(parent, actor, actor_path, group, prop, label_width)
            editor.set_read_only(True)
            property_edits.append(editor)
            content_layout.addWidget(editor)
        else:
            editor = _create_property_edit(parent, actor, actor_path, group, prop, label_width)
            if prop.is_read_only():
                editor.set_read_only(True)
            property_edits.append(editor)
            content_layout.addWidget(editor)

    # 第三步：递归渲染结构体树
    for struct_root in struct_roots:
        _render_struct_group(
            parent, actor, actor_path, group,
            struct_root, label_width, property_edits,
            content_layout,
            collapsed=collapsed,
        )

    return content