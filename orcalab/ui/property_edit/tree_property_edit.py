from typing import Any, List
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


def create_property_edit(
    parent: QtWidgets.QWidget,
    context: PropertyEditContext,
    label_width: int,
) -> BasePropertyEdit:
    """统一的属性编辑器创建函数，避免循环导入"""
    from orcalab.ui.property_edit.bool_property_edit import BooleanPropertyEdit
    from orcalab.ui.property_edit.float_property_edit import FloatPropertyEdit
    from orcalab.ui.property_edit.int_property_edit import IntegerPropertyEdit
    from orcalab.ui.property_edit.string_property_edit import StringPropertyEdit

    match context.prop.value_type():
        case ActorPropertyType.BOOL:
            return BooleanPropertyEdit(parent, context, label_width)
        case ActorPropertyType.INTEGER:
            return IntegerPropertyEdit(parent, context, label_width)
        case ActorPropertyType.FLOAT:
            return FloatPropertyEdit(parent, context, label_width)
        case ActorPropertyType.STRING:
            return StringPropertyEdit(parent, context, label_width)
        case _:
            return StringPropertyEdit(parent, context, label_width)


class TreeNodeWidget(StyledWidget):
    """树节点组件，包含标题和可折叠的内容区"""

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
        
        # 计算最小宽度：缩进 + 标签宽度 + 编辑器最小宽度 + 边距
        indent = self._indent_level * 16
        min_width = indent + 24 + self._label_width + 200  # 200 是编辑器最小宽度
        self.setMinimumWidth(min_width)

        theme = ThemeService()
        text_color = theme.get_color("text")

        # 标题区域
        title_widget = QtWidgets.QWidget()
        title_layout = QtWidgets.QHBoxLayout(title_widget)
        title_layout.setContentsMargins(4 + self._indent_level * 16, 2, 4, 2)
        title_layout.setSpacing(4)

        self._expand_icon = make_color_svg(":/icons/chevron_down", text_color)
        self._collapse_icon = make_color_svg(":/icons/chevron_right", text_color)

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

        # 内容区域
        self._content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(self._content_widget)
        content_layout.setContentsMargins(4 + self._indent_level * 16 + 20, 0, 4, 4)
        content_layout.setSpacing(4)

        adjusted_label_width = max(80, self._label_width - self._indent_level * 16)

        # 添加属性编辑器
        for prop in self._node.properties:
            context = self._create_child_context(prop)
            editor = create_property_edit(self, context, adjusted_label_width)
            if prop.is_read_only():
                editor.set_read_only(True)
            self._property_edits.append(editor)
            content_layout.addWidget(editor)

        # 添加子节点
        for child_node in self._node.children:
            child_widget = TreeNodeWidget(
                self,
                child_node,
                self._base_context,
                self._label_width,
                self._indent_level + 1,
            )
            self._child_nodes.append(child_widget)
            content_layout.addWidget(child_widget)

        root_layout.addWidget(self._content_widget)
        
        # 更新最小宽度为自身和所有子节点的最大值
        max_child_width = max((c.minimumWidth() for c in self._child_nodes), default=0)
        if max_child_width > self.minimumWidth():
            self.setMinimumWidth(max_child_width)

    def _create_child_context(self, prop: ActorProperty) -> PropertyEditContext:
        """创建子属性的上下文，属性名使用 节点名.属性名 格式"""
        full_prop_name = f"{self._node.name}.{prop.name()}"
        # 使用 create_alias 共享值引用，修改别名时原属性也会更新
        alias_prop = prop.create_alias(full_prop_name)

        return PropertyEditContext(
            actor=self._base_context.actor,
            actor_path=self._base_context.actor_path,
            group=self._base_context.group,
            prop=alias_prop,
        )

    def _on_title_clicked(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._toggle()

    def _toggle(self):
        self._is_collapsed = not self._is_collapsed
        if self._is_collapsed:
            self._content_widget.hide()
            self._indicator.set_pixmap(self._collapse_icon)
        else:
            self._content_widget.show()
            self._indicator.set_pixmap(self._expand_icon)

    def get_property_edits(self) -> List[BasePropertyEdit]:
        """递归获取所有属性编辑器"""
        edits = list(self._property_edits)
        for child in self._child_nodes:
            edits.extend(child.get_property_edits())
        return edits


class TreePropertyEdit(BasePropertyEdit):
    """树形属性编辑器，继承自 BasePropertyEdit"""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        context: PropertyEditContext,
        label_width: int,
    ):
        super().__init__(parent, context)
        self._label_width = label_width
        self._node_widgets: List[TreeNodeWidget] = []

        self._init_ui()

    def _init_ui(self):
        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(4)

        tree_data = self.context.group.tree_data
        for node in tree_data:
            node_widget = TreeNodeWidget(
                self,
                node,
                self.context,
                self._label_width,
                indent_level=0,
            )
            self._node_widgets.append(node_widget)
            root_layout.addWidget(node_widget)

    def set_value(self, value: Any):
        """树形属性不直接设置值，而是设置子属性"""
        pass

    def set_read_only(self, read_only: bool):
        """设置所有子属性的只读状态"""
        for node_widget in self._node_widgets:
            for edit in node_widget.get_property_edits():
                edit.set_read_only(read_only)

    def set_child_value(self, property_name: str, value: Any):
        """根据属性名设置子属性值"""
        for node_widget in self._node_widgets:
            for edit in node_widget.get_property_edits():
                if edit.context.prop.name() == property_name:
                    edit.set_value(value)
                    return

    def set_child_read_only(self, property_name: str, read_only: bool):
        """根据属性名设置子属性只读状态"""
        for node_widget in self._node_widgets:
            for edit in node_widget.get_property_edits():
                if edit.context.prop.name() == property_name:
                    edit.set_read_only(read_only)
                    return
