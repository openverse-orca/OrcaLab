from typing import List
import logging

from PySide6 import QtWidgets

from orcalab.actor import BaseActor
from orcalab.actor_property import (
    ActorProperty,
    ActorPropertyGroup,
    ActorPropertyKey,
    ActorPropertyType,
    StructPropertyGroup,
)
from orcalab.path import Path
from orcalab.perf_log import perf_log
from orcalab.ui.collapsible.collapsible_section import CollapsibleSection
from orcalab.ui.fonts.font_service import FontService
from orcalab.ui.property_edit.base_property_edit import (
    BasePropertyEdit,
    PropertyEditContext,
)
from orcalab.ui.property_edit.bool_property_edit import BooleanPropertyEdit
from orcalab.ui.property_edit.combo_property_edit import ComboBoxPropertyEdit
from orcalab.ui.property_edit.float_property_edit import FloatPropertyEdit
from orcalab.ui.property_edit.float_slide_property_edit import FloatSlidePropertyEdit
from orcalab.ui.property_edit.int_property_edit import IntegerPropertyEdit
from orcalab.ui.property_edit.color_property_edit import ColorPropertyEdit
from orcalab.ui.property_edit.string_property_edit import StringPropertyEdit
from orcalab.ui.property_edit.texture_picker_property_edit import (
    TexturePickerPropertyEdit,
)
from orcalab.ui.styled_widget import StyledWidget
from orcalab.texture_asset_cache import get_texture_asset_cache

_COLOR_CHANNEL_NAMES = {"r", "g", "b", "a"}


def _is_color_struct(sg: StructPropertyGroup) -> bool:
    if sg.children:
        return False
    if not sg.properties:
        return False
    has_r = False
    for p in sg.properties:
        if p.value_type() != ActorPropertyType.FLOAT:
            return False
        last_seg = p.name().rsplit(".", 1)[-1] if "." in p.name() else p.name()
        if last_seg not in _COLOR_CHANNEL_NAMES:
            return False
        if last_seg == "r":
            has_r = True
    return has_r


def _indent_unit() -> int:
    return FontService().indent_unit_px(20)


def _create_property_edit(
    parent: QtWidgets.QWidget,
    actor: BaseActor,
    actor_path: Path,
    group: ActorPropertyGroup,
    prop: ActorProperty,
    label_width: int,
) -> BasePropertyEdit:
    key = ActorPropertyKey(
        actor_path=actor_path,
        entity_id=group.entity_id,
        entity_path=group.entity_path,
        component_type_id=group.component_type_id,
        component_type_index=group.component_type_index,
        property_name=prop.name(),
        property_type=prop.value_type(),
    )
    context = PropertyEditContext(
        actor=actor, actor_path=actor_path, group=group, prop=prop, key=key
    )

    match prop.value_type():
        case ActorPropertyType.BOOL:
            return BooleanPropertyEdit(parent, context, label_width)
        case ActorPropertyType.INTEGER:
            if prop.enum_values():
                return ComboBoxPropertyEdit(parent, context, label_width)
            return IntegerPropertyEdit(parent, context, label_width)
        case ActorPropertyType.FLOAT:
            if prop.is_slide() == True:
                if prop.has_range() == True:
                    return FloatSlidePropertyEdit(parent, context, label_width, prop.range_min(), prop.range_max())
                else:
                    return FloatSlidePropertyEdit(parent, context, label_width)
            return FloatPropertyEdit(parent, context, label_width)
        case ActorPropertyType.STRING:
            return StringPropertyEdit(parent, context, label_width)
        case ActorPropertyType.ENUM:
            return ComboBoxPropertyEdit(parent, context, label_width)
        case ActorPropertyType.ASSET:
            return TexturePickerPropertyEdit(
                parent, context, label_width, get_texture_asset_cache()
            )
        case _:
            raise NotImplementedError("Unsupported property type")


def _build_struct_tree(
    group: ActorPropertyGroup,
) -> List[ActorProperty | StructPropertyGroup]:
    """V2: 从属性名的点号分隔符自动推断 struct 分组关系。

    C++ 侧 FlattenField 跳过 "Config" 前缀后，属性名如 "axis.x"、"axis.y"、"axis.z"
    仍然保留了父结构名和子字段名的点号分隔关系。由此可自动推断：
    - 父结构名: 点号前的部分 (如 "axis")
    - 子字段名: 点号后的部分 (如 "x", "y", "z")
    - 横排判定: 子字段名均为单字符且类型为 Float → Vector2/3/4 横排绘制
    """
    struct_groups: dict[str, List[ActorProperty]] = {}
    ordered_entries: List[ActorProperty | str] = []
    ordered_struct_roots: set[str] = set()

    for prop in group.properties:
        name = prop.name()
        dot_pos = name.find(".")
        if dot_pos != -1:
            parent_name = name[:dot_pos]
            struct_groups.setdefault(parent_name, []).append(prop)
            if parent_name not in ordered_struct_roots:
                ordered_struct_roots.add(parent_name)
                ordered_entries.append(parent_name)
        else:
            ordered_entries.append(prop)

    if not struct_groups:
        return [entry for entry in ordered_entries if isinstance(entry, ActorProperty)]

    perf_log(
        f"_build_struct_tree: group={group.name}, total_props={len(group.properties)}, "
        f"prop_names={[p.name() for p in group.properties[:10]]}, "
        f"struct_group_keys={list(struct_groups.keys())}, "
        f"ordered_entries={[e if isinstance(e, str) else e.name() for e in ordered_entries[:10]]}",
        feature="PROPERTY",
    )

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
            sub = name[dot_pos + 1 :] if dot_pos != -1 else name
            if len(sub) != 1:
                return False
        return True

    def _split_at_depth(name: str, depth: int) -> tuple[str, str] | None:
        """Split a dotted name at the given depth (0-based).

        Returns (prefix_up_to_depth, remaining_after_depth) or None if
        the name doesn't have enough segments.

        E.g. _split_at_depth("Configs.0.type", 1) -> ("Configs.0", "type")
             _split_at_depth("Configs.0.actuatorMap.joint", 1) -> ("Configs.0", "actuatorMap.joint")
             _split_at_depth("Configs.0.type", 2) -> None (only 3 segments, depth=2 requires 3+ segments)
        """
        pos = -1
        for _ in range(depth + 1):
            pos = name.find(".", pos + 1)
            if pos == -1:
                return None
        return (name[:pos], name[pos + 1 :])

    def _build(
        name: str,
        props: List[ActorProperty],
        display_override: str | None = None,
        prefix_depth: int = 0,
    ) -> StructPropertyGroup:
        display = display_override or name.capitalize()
        direct_props: List[ActorProperty] = []
        child_groups: dict[str, List[ActorProperty]] = {}

        for p in props:
            result = _split_at_depth(p.name(), prefix_depth)
            if result is None:
                direct_props.append(p)
            else:
                _, remaining = result
                next_dot = remaining.find(".")
                if next_dot != -1:
                    child_name = remaining[:next_dot]
                    child_groups.setdefault(child_name, []).append(p)
                else:
                    direct_props.append(p)

        perf_log(
            f"_build_struct_tree._build: name={name}, prefix_depth={prefix_depth}, "
            f"direct_props={len(direct_props)}, "
            f"child_groups={list(child_groups.keys())[:10]}{'...' if len(child_groups) > 10 else ''}, "
            f"child_counts={{k: len(v) for k, v in list(child_groups.items())[:5]}}",
            feature="PROPERTY",
        )

        if prefix_depth > 10:
            perf_log(
                f"_build_struct_tree._build: DEPTH EXCEEDED! name={name}, prefix_depth={prefix_depth}, "
                f"prop_names={[p.name() for p in props[:3]]}",
                feature="PROPERTY",
            )
            return StructPropertyGroup(name, display, direct_props, [])

        children = [
            _build(cn, cp, cn.capitalize(), prefix_depth + 1)
            for cn, cp in child_groups.items()
        ]
        sg = StructPropertyGroup(name, display, direct_props, children)
        if _is_tuple_group(sg):
            sg.layout = "horizontal"
        return sg

    struct_root_map: dict[str, StructPropertyGroup] = {}
    for struct_name, props in struct_groups.items():
        struct_root_map[struct_name] = _build(struct_name, props)

    ordered_nodes: List[ActorProperty | StructPropertyGroup] = []
    for entry in ordered_entries:
        if isinstance(entry, ActorProperty):
            ordered_nodes.append(entry)
        else:
            ordered_nodes.append(struct_root_map[entry])

    return ordered_nodes


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
    try:
        if _is_color_struct(struct_group):
            content_factory = lambda: ColorPropertyEdit(
                parent, struct_group, actor, actor_path, group, label_width, property_edits
                )
        else:
            content_factory = lambda sg=struct_group: _create_struct_content(
                parent,
                actor,
                actor_path,
                group,
                sg,
                label_width,
                property_edits,
                indent_level=indent_level,
                collapsed=collapsed,
            )

        section = CollapsibleSection(
            parent=parent,
            title=struct_group.display_name,
            collapsed=collapsed,
            indent_level=indent_level,
            content_factory=content_factory
        )
        layout.addWidget(section)

    except Exception as e:
        logging.getLogger(__name__).error(
            f"_render_struct_group failed: name={struct_group.display_name} "
            f"type={type(e).__name__} msg={e}",
            exc_info=True,
        )
        err_label = QtWidgets.QLabel(f"⚠ {struct_group.display_name}: {e}")
        layout.addWidget(err_label)


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
    from orcalab.ui.property_edit.float_property_edit import FloatPropertyEdit

    row = QtWidgets.QWidget()
    row_layout = QtWidgets.QHBoxLayout(row)
    row_layout.setContentsMargins(indent, 0, 0, 0)
    row_layout.setSpacing(8)

    fs = FontService()
    compact_label_width = fs.indent_unit_px(14)

    for prop in struct_group.properties:
        editor = _create_property_edit(
            parent, actor, actor_path, group, prop, compact_label_width
        )
        if prop.is_read_only():
            editor.set_read_only(True)
        property_edits.append(editor)
        row_layout.addWidget(editor)

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
            parent,
            actor,
            actor_path,
            group,
            struct_group,
            property_edits,
            prop_indent,
        )
        content_layout.addWidget(row)
    else:
        prop_indent = (indent_level + 1) * _indent_unit()
        for prop in struct_group.properties:
            editor = _create_property_edit(
                parent, actor, actor_path, group, prop, label_width
            )
            if prop.is_read_only():
                editor.set_read_only(True)
            property_edits.append(editor)

            row = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row)
            row_layout.setContentsMargins(prop_indent, 0, 0, 0)
            row_layout.setSpacing(0)
            row_layout.addWidget(editor)
            content_layout.addWidget(row)

    for child in struct_group.children:
        _render_struct_group(
            parent,
            actor,
            actor_path,
            group,
            child,
            label_width,
            property_edits,
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
    perf_log(
        f"create_property_group_content: group={group.name}, "
        f"props={len(group.properties)}, "
        f"prop_names=[{', '.join(p.name() for p in group.properties[:5])}{'...' if len(group.properties) > 5 else ''}]",
        feature="PROPERTY",
    )

    content = StyledWidget()
    content_layout = QtWidgets.QVBoxLayout(content)
    content_layout.setContentsMargins(0, 0, 0, 0)
    content_layout.setSpacing(2)

    # 重建结构体树并按原始属性顺序渲染
    ordered_nodes = _build_struct_tree(group)

    for idx, node in enumerate(ordered_nodes):
        if isinstance(node, ActorProperty):
            prop = node
            try:
                if prop.editor_hint() in ("container", "struct"):
                    editor = _create_property_edit(
                        parent, actor, actor_path, group, prop, label_width
                    )
                    editor.set_read_only(True)
                    property_edits.append(editor)
                    content_layout.addWidget(editor)
                else:
                    editor = _create_property_edit(
                        parent, actor, actor_path, group, prop, label_width
                    )
                    if prop.is_read_only():
                        editor.set_read_only(True)
                    property_edits.append(editor)
                    content_layout.addWidget(editor)
            except Exception as e:
                logging.getLogger(__name__).error(
                    f"render prop name={prop.name()} failed: "
                    f"type={type(e).__name__} msg={e}",
                    exc_info=True,
                )
                err_label = QtWidgets.QLabel(f"⚠ {prop.name()}: {e}")
                content_layout.addWidget(err_label)
            continue

        struct_root = node
        try:
            _render_struct_group(
                parent,
                actor,
                actor_path,
                group,
                struct_root,
                label_width,
                property_edits,
                content_layout,
                collapsed=collapsed,
            )
        except Exception as e:
            logging.getLogger(__name__).error(
                f"render struct[{idx}] name={struct_root.name} failed: "
                f"type={type(e).__name__} msg={e}",
                exc_info=True,
            )
            err_label = QtWidgets.QLabel(f"⚠ {struct_root.display_name}: {e}")
            content_layout.addWidget(err_label)

    return content
