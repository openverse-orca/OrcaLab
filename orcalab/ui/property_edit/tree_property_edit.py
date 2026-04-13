from typing import Any, List, Set
import asyncio
from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.actor_property import (
    ActorProperty,
    ActorPropertyType,
    TreePropertyNode,
)
from orcalab.ui.icon import Icon
from orcalab.ui.icon_util import make_color_svg
from orcalab.ui.property_edit.base_property_edit import (
    BasePropertyEdit,
    PropertyEditContext,
)
from orcalab.ui.styled_widget import StyledWidget
from orcalab.ui.theme_service import ThemeService

INDENT_WIDTH = 20
EDITOR_MIN_WIDTH = 300

# 全局高亮状态存储: actor_path_str -> set of highlighted entity_ids
_highlight_store: dict[str, Set[int]] = {}


def _get_highlight_set(actor_path_str: str) -> Set[int]:
    return _highlight_store.setdefault(actor_path_str, set())


def _node_entity_id(node: TreePropertyNode) -> int | None:
    """从 node.name 提取 entityId。支持 'entityId:componentId' 和旧格式 'entityId'。"""
    try:
        return int(node.name.split(":")[0])
    except (ValueError, TypeError, AttributeError):
        return None


async def _send_highlight(entity_id: int, highlight: bool):
    try:
        from orcalab.application_util import get_remote_scene
        await get_remote_scene().set_highlight_entity(entity_id, highlight)
    except Exception:
        pass


def create_property_edit(
    parent: QtWidgets.QWidget,
    context: PropertyEditContext,
    label_width: int,
) -> BasePropertyEdit:
    from orcalab.ui.property_edit.bool_property_edit import BooleanPropertyEdit
    from orcalab.ui.property_edit.combo_property_edit import ComboBoxPropertyEdit
    from orcalab.ui.property_edit.float_property_edit import FloatPropertyEdit
    from orcalab.ui.property_edit.int_property_edit import IntegerPropertyEdit
    from orcalab.ui.property_edit.string_property_edit import StringPropertyEdit

    if (context.prop.value_type() == ActorPropertyType.INTEGER
            and context.prop.editor_hint().startswith("options:")):
        return ComboBoxPropertyEdit(parent, context, label_width)

    match context.prop.value_type():
        case ActorPropertyType.BOOL:
            return BooleanPropertyEdit(parent, context, label_width)
        case ActorPropertyType.INTEGER:
            return IntegerPropertyEdit(parent, context, label_width)
        case ActorPropertyType.FLOAT:
            return FloatPropertyEdit(parent, context, label_width)
        case _:
            return StringPropertyEdit(parent, context, label_width)


def calc_tree_max_depth(nodes: List[TreePropertyNode], depth: int = 0) -> int:
    if not nodes:
        return depth
    return max(calc_tree_max_depth(n.children, depth + 1) for n in nodes)


def calc_required_width(max_depth: int, label_width: int) -> int:
    return (max_depth + 1) * INDENT_WIDTH + label_width + EDITOR_MIN_WIDTH + 40


def _create_spacer(width: int) -> QtWidgets.QWidget:
    spacer = QtWidgets.QWidget()
    spacer.setFixedWidth(width)
    return spacer


class TreeNodeWidget(StyledWidget):

    collapsed_changed = QtCore.Signal()

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        node: TreePropertyNode,
        base_context: PropertyEditContext,
        label_width: int,
        indent_level: int = 0,
    ):
        super().__init__(parent)
        self._node = node
        self._base_context = base_context
        self._label_width = label_width
        self._indent_level = indent_level
        self._property_edits: List[BasePropertyEdit] = []
        self._child_nodes: List["TreeNodeWidget"] = []
        self._is_collapsed = False
        self._init_ui()

    def _init_ui(self):
        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(2)

        text_color = ThemeService().get_color("text")
        indent = self._indent_level * INDENT_WIDTH

        title_widget = QtWidgets.QWidget()
        title_layout = QtWidgets.QHBoxLayout(title_widget)
        title_layout.setContentsMargins(0, 2, 4, 2)
        title_layout.setSpacing(4)

        if indent > 0:
            title_layout.addWidget(_create_spacer(indent))

        self._expand_icon = make_color_svg(":/icons/chevron_down.svg", text_color)
        self._collapse_icon = make_color_svg(":/icons/chevron_right.svg", text_color)

        self._indicator = Icon()
        self._indicator.set_icon_size(16)
        self._indicator.set_pixmap(self._expand_icon)

        self._title_label = QtWidgets.QLabel(self._node.display_name)
        self._title_label.setStyleSheet("font-weight: bold;")

        title_layout.addWidget(self._indicator)
        title_layout.addWidget(self._title_label)
        title_layout.addStretch()

        title_widget.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        title_widget.mousePressEvent = self._on_title_clicked
        root_layout.addWidget(title_widget)

        self._content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(self._content_widget)
        content_layout.setContentsMargins(0, 0, 0, 4)
        content_layout.setSpacing(4)

        prop_indent = (self._indent_level + 1) * INDENT_WIDTH
        for prop in self._node.properties:
            prop_row = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(prop_row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(0)
            if prop_indent > 0:
                row_layout.addWidget(_create_spacer(prop_indent))
            context = PropertyEditContext(
                actor=self._base_context.actor,
                actor_path=self._base_context.actor_path,
                group=self._base_context.group,
                prop=prop.create_alias(f"{self._node.name}.{prop.name()}"),
            )
            editor = create_property_edit(prop_row, context, self._label_width)
            editor.setMinimumWidth(self._label_width + EDITOR_MIN_WIDTH)
            if prop.is_read_only():
                editor.set_read_only(True)
            self._property_edits.append(editor)
            row_layout.addWidget(editor)
            row_layout.addStretch()
            content_layout.addWidget(prop_row)

        for child_node in self._node.children:
            child = TreeNodeWidget(
                self, child_node, self._base_context,
                self._label_width, self._indent_level + 1
            )
            self._child_nodes.append(child)
            content_layout.addWidget(child)

        root_layout.addWidget(self._content_widget)

    def _on_title_clicked(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._is_collapsed = not self._is_collapsed
            self._content_widget.setVisible(not self._is_collapsed)
            self._indicator.set_pixmap(
                self._collapse_icon if self._is_collapsed else self._expand_icon
            )
            self.collapsed_changed.emit()

    def get_property_edits(self) -> List[BasePropertyEdit]:
        edits = list(self._property_edits)
        for child in self._child_nodes:
            edits.extend(child.get_property_edits())
        return edits


class TreeLeafNodeDialog(QtWidgets.QDialog):
    """显示单个树形叶节点属性的编辑对话框（通用，适用于 Joint / Geom / Site 等）"""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        node: TreePropertyNode,
        context: PropertyEditContext,
        label_width: int,
    ):
        super().__init__(parent)
        self._node = node
        self._context = context
        self._label_width = label_width
        self._node_widget: TreeNodeWidget | None = None
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle(f"编辑 - {self._node.display_name}")
        self.setMinimumSize(500, 300)
        self.resize(700, 450)

        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)

        self._scroll_area = QtWidgets.QScrollArea()
        self._scroll_area.setWidgetResizable(False)

        self._content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(self._content_widget)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(8)

        shallow_node = TreePropertyNode(self._node.name, self._node.display_name)
        shallow_node.properties = self._node.properties

        self._content_widget.setMinimumWidth(calc_required_width(1, self._label_width))
        self._node_widget = TreeNodeWidget(
            self._content_widget, shallow_node, self._context, self._label_width
        )
        self._node_widget.collapsed_changed.connect(self._update_content_size)
        content_layout.addWidget(self._node_widget)
        content_layout.addStretch()

        self._scroll_area.setWidget(self._content_widget)
        root_layout.addWidget(self._scroll_area, 1)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        save_btn = QtWidgets.QPushButton("保存并关闭")
        save_btn.setFixedWidth(100)
        save_btn.clicked.connect(self._on_save)
        button_layout.addWidget(save_btn)
        root_layout.addLayout(button_layout)

    def _on_save(self):
        """清除当前焦点以触发最后一个字段的 FocusOut 提交，然后关闭对话框。"""
        fw = QtWidgets.QApplication.focusWidget()
        if fw is not None:
            fw.clearFocus()
        self.accept()

    def _update_content_size(self):
        QtCore.QTimer.singleShot(0, self._do_update_content_size)

    def _do_update_content_size(self):
        hint = self._content_widget.sizeHint()
        width = max(self._content_widget.minimumWidth(),
                    self._scroll_area.viewport().width())
        self._content_widget.resize(width, hint.height())

    def resizeEvent(self, event: QtGui.QResizeEvent):
        super().resizeEvent(event)
        self._do_update_content_size()

    def get_property_edits(self) -> List[BasePropertyEdit]:
        return self._node_widget.get_property_edits() if self._node_widget else []


# 向后兼容别名
SingleJointDialog = TreeLeafNodeDialog


class TreeLeafButton(QtWidgets.QPushButton):
    """树形叶节点公共按钮基类：左键切换高亮线框，右键弹出属性编辑对话框。

    子类通过覆写 `_dialog_title()` 定制右键对话框标题，不应直接覆写 `_on_right_click`
    以外的公共逻辑。
    """

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        node: TreePropertyNode,
        context: PropertyEditContext,
        label_width: int,
        initially_highlighted: bool = False,
        *,
        highlight_store: "dict[str, Set[int]] | None" = None,
    ):
        super().__init__(node.display_name, parent)
        self._node = node
        self._context = context
        self._label_width = label_width
        self._dialog: TreeLeafNodeDialog | None = None
        self._highlighted = initially_highlighted
        self._actor_path_str = str(context.actor_path)
        self._highlight_store = highlight_store if highlight_store is not None else _highlight_store

        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_right_click)
        self.clicked.connect(self._on_left_click)
        self._apply_style()

    def _dialog_title(self) -> str:
        """子类覆写以返回右键编辑对话框的标题。"""
        return f"编辑 - {self._node.display_name}"

    def _apply_style(self):
        theme = ThemeService()
        text_color = theme.get_color_hex("text")
        bg_color = theme.get_color_hex("property_group_bg")
        brand_color = theme.get_color_hex("brand")

        if self._highlighted:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {brand_color}66;
                    color: {text_color};
                    border: 1px solid {brand_color};
                    border-radius: 3px;
                    padding: 3px 8px;
                    text-align: left;
                    font-weight: bold;
                }}
                QPushButton:hover {{ background-color: {brand_color}88; }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg_color};
                    color: {text_color};
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 3px;
                    padding: 3px 8px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background-color: {brand_color}44;
                    border-color: {brand_color}88;
                }}
            """)

    def _on_left_click(self):
        self._highlighted = not self._highlighted
        self._apply_style()

        eid = _node_entity_id(self._node)
        if eid is None:
            return
        highlight_set = self._highlight_store.setdefault(self._actor_path_str, set())
        if self._highlighted:
            highlight_set.add(eid)
        else:
            highlight_set.discard(eid)
        asyncio.ensure_future(_send_highlight(eid, self._highlighted))

    def setText(self, text: str):
        """重写以同步更新节点 display_name 并使缓存的编辑对话框失效。"""
        super().setText(text)
        self._node.display_name = text
        self._dialog = None

    def _on_right_click(self, pos: QtCore.QPoint):
        if self._dialog is None:
            self._dialog = TreeLeafNodeDialog(
                self.window(), self._node, self._context, self._label_width
            )
            self._dialog.setWindowTitle(self._dialog_title())
        self._dialog.exec()


class JointButton(TreeLeafButton):
    """关节叶节点按钮。"""

    def _dialog_title(self) -> str:
        return f"编辑关节 - {self._node.display_name}"


def _is_entity_node(node: TreePropertyNode) -> bool:
    """判断是否为实体容器节点（name 以 'e:' 开头）"""
    return isinstance(node.name, str) and node.name.startswith("e:")


def _build_nodes(
    nodes: List[TreePropertyNode],
    layout: QtWidgets.QVBoxLayout,
    context: PropertyEditContext,
    label_width: int,
    indent: int,
    highlight_set: Set[int],
    button_registry: "dict[str, TreeLeafButton] | None" = None,
    button_cls: type = None,
    skip_unnamed: bool = True,
):
    """递归构建叶节点树到 layout 中。"""
    if button_cls is None:
        button_cls = JointButton
    for node in nodes:
        if _is_entity_node(node):
            layout.addWidget(
                _EntityGroup(None, node, context, label_width, indent, button_registry,
                             button_cls=button_cls, skip_unnamed=skip_unnamed)
            )
        elif skip_unnamed and node.display_name.startswith("未命名"):
            continue
        else:
            eid = _node_entity_id(node)
            btn = button_cls(None, node, context, label_width, eid in highlight_set if eid else False)
            if button_registry is not None:
                button_registry[node.name] = btn
            row = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row)
            row_layout.setContentsMargins(indent * INDENT_WIDTH, 0, 0, 0)
            row_layout.setSpacing(0)
            row_layout.addWidget(btn)
            row_layout.addStretch()
            layout.addWidget(row)


class _EntityGroup(QtWidgets.QWidget):
    """可折叠的实体容器节点：头部显示实体名文本标签，子区域显示叶节点按钮或嵌套实体组"""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        node: TreePropertyNode,
        context: PropertyEditContext,
        label_width: int,
        indent: int,
        button_registry: "dict[str, TreeLeafButton] | None" = None,
        *,
        button_cls: type = None,
        skip_unnamed: bool = True,
    ):
        super().__init__(parent)
        self._node = node
        self._context = context
        self._label_width = label_width
        self._indent = indent
        self._collapsed = False
        self._children_widget: QtWidgets.QWidget | None = None
        self._toggle_btn: QtWidgets.QPushButton | None = None
        self._button_registry = button_registry
        self._button_cls = button_cls
        self._skip_unnamed = skip_unnamed
        self._init_ui()

    def _init_ui(self):
        text_color = ThemeService().get_color_hex("text")
        highlight_set = _get_highlight_set(str(self._context.actor_path))

        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(1)

        header_row = QtWidgets.QWidget()
        header_layout = QtWidgets.QHBoxLayout(header_row)
        header_layout.setContentsMargins(self._indent * INDENT_WIDTH, 0, 0, 0)
        header_layout.setSpacing(4)

        self._toggle_btn = QtWidgets.QPushButton("▾")
        self._toggle_btn.setFixedSize(18, 22)
        self._toggle_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {text_color};
                border: none; font-size: 11px; padding: 0;
            }}
            QPushButton:hover {{ color: white; }}
        """)
        self._toggle_btn.clicked.connect(self._toggle)
        header_layout.addWidget(self._toggle_btn)

        # 实体名：普通标签，不可高亮/右键编辑
        entity_label = QtWidgets.QLabel(self._node.display_name)
        entity_label.setStyleSheet(f"color: {text_color}; font-weight: bold;")
        header_layout.addWidget(entity_label)
        header_layout.addStretch()
        root_layout.addWidget(header_row)

        self._children_widget = QtWidgets.QWidget()
        children_layout = QtWidgets.QVBoxLayout(self._children_widget)
        children_layout.setContentsMargins(0, 0, 0, 0)
        children_layout.setSpacing(1)
        _build_nodes(self._node.children, children_layout, self._context,
                     self._label_width, self._indent + 1, highlight_set,
                     self._button_registry, button_cls=self._button_cls,
                     skip_unnamed=self._skip_unnamed)
        root_layout.addWidget(self._children_widget)

    def _toggle(self):
        self._collapsed = not self._collapsed
        if self._children_widget:
            self._children_widget.setVisible(not self._collapsed)
        if self._toggle_btn:
            self._toggle_btn.setText("▸" if self._collapsed else "▾")


class TreePropertyEdit(BasePropertyEdit):

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        context: PropertyEditContext,
        label_width: int,
    ):
        super().__init__(parent, context)
        self._label_width = label_width
        self._actor_path_str = str(context.actor_path)
        # node.name -> TreeLeafButton，用于名字变更后刷新按钮文字
        self._leaf_buttons: dict[str, "TreeLeafButton"] = {}
        self._init_ui()
        asyncio.ensure_future(self._restore_highlights())

    async def _restore_highlights(self):
        """重新选中物体时，恢复之前高亮的关节"""
        highlight_set = _get_highlight_set(self._actor_path_str)
        if not highlight_set:
            return
        for eid in highlight_set:
            await _send_highlight(eid, True)

    async def _clear_highlights(self):
        """取消选中物体时，清除引擎中的高亮（保留记录以便恢复）"""
        for eid in _get_highlight_set(self._actor_path_str):
            await _send_highlight(eid, False)

    def hideEvent(self, event: QtGui.QHideEvent):
        super().hideEvent(event)
        asyncio.ensure_future(self._clear_highlights())

    def _init_ui(self):
        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(2)
        tree_data = self.context.group.tree_data
        if tree_data:
            _build_nodes(tree_data, root_layout, self.context, self._label_width,
                         indent=0, highlight_set=_get_highlight_set(self._actor_path_str),
                         button_registry=self._leaf_buttons)

    def set_value(self, value: Any):
        pass

    def set_read_only(self, read_only: bool):
        pass

    def set_child_value(self, property_name: str, value: Any):
        """处理子属性变更通知，用于刷新 JointButton 显示的关节名字。
        property_name 格式: 'entityId:componentId.Name'
        """
        dot_pos = property_name.rfind(".")
        if dot_pos == -1:
            return
        node_key = property_name[:dot_pos]
        prop = property_name[dot_pos + 1:]
        if prop != "Name":
            return
        btn = self._leaf_buttons.get(node_key)
        if btn is not None and isinstance(value, str):
            btn.setText(value)

    def set_child_read_only(self, property_name: str, read_only: bool):
        pass
