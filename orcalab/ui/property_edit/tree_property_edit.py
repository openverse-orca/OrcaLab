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

INDENT_WIDTH = 20
EDITOR_MIN_WIDTH = 300


def create_property_edit(
    parent: QtWidgets.QWidget,
    context: PropertyEditContext,
    label_width: int,
) -> BasePropertyEdit:
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
        case _:
            return StringPropertyEdit(parent, context, label_width)


def collect_all_names(nodes: List[TreePropertyNode]) -> List[str]:
    names = []
    for node in nodes:
        if not node.display_name.startswith("未命名"):
            names.append(node.display_name)
        names.extend(collect_all_names(node.children))
    return names


def calc_tree_max_depth(nodes: List[TreePropertyNode], depth: int = 0) -> int:
    if not nodes:
        return depth
    return max(calc_tree_max_depth(n.children, depth + 1) for n in nodes)


def calc_required_width(max_depth: int, label_width: int) -> int:
    return (max_depth + 1) * INDENT_WIDTH + label_width + EDITOR_MIN_WIDTH + 40


def create_spacer(width: int) -> QtWidgets.QWidget:
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

        # 标题区域
        title_widget = QtWidgets.QWidget()
        title_layout = QtWidgets.QHBoxLayout(title_widget)
        title_layout.setContentsMargins(0, 2, 4, 2)
        title_layout.setSpacing(4)

        if indent > 0:
            title_layout.addWidget(create_spacer(indent))

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

        # 内容区域
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
                row_layout.addWidget(create_spacer(prop_indent))

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


class TreePropertyDialog(QtWidgets.QDialog):

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        context: PropertyEditContext,
        label_width: int,
    ):
        super().__init__(parent)
        self._context = context
        self._label_width = label_width
        self._node_widgets: List[TreeNodeWidget] = []
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle(f"编辑 - {self._context.prop.display_name()}")
        self.setMinimumSize(500, 400)
        self.resize(800, 600)

        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)

        self._scroll_area = QtWidgets.QScrollArea()
        self._scroll_area.setWidgetResizable(False)

        self._content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(self._content_widget)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(8)

        tree_data = self._context.group.tree_data
        max_depth = calc_tree_max_depth(tree_data)
        self._content_widget.setMinimumWidth(
            calc_required_width(max_depth, self._label_width)
        )

        for node in tree_data:
            node_widget = TreeNodeWidget(
                self._content_widget, node, self._context, self._label_width
            )
            self._connect_collapsed_signals(node_widget)
            self._node_widgets.append(node_widget)
            content_layout.addWidget(node_widget)

        content_layout.addStretch()
        self._scroll_area.setWidget(self._content_widget)
        root_layout.addWidget(self._scroll_area, 1)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.setFixedWidth(80)
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        root_layout.addLayout(button_layout)

    def _connect_collapsed_signals(self, node: TreeNodeWidget):
        node.collapsed_changed.connect(self._update_content_size)
        for child in node._child_nodes:
            self._connect_collapsed_signals(child)

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

    def _find_edit(self, property_name: str) -> BasePropertyEdit | None:
        for node in self._node_widgets:
            for edit in node.get_property_edits():
                if edit.context.prop.name() == property_name:
                    return edit
        return None

    def set_child_value(self, property_name: str, value: Any):
        if edit := self._find_edit(property_name):
            edit.set_value(value)

    def set_child_read_only(self, property_name: str, read_only: bool):
        if edit := self._find_edit(property_name):
            edit.set_read_only(read_only)


class TreePropertyEdit(BasePropertyEdit):

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        context: PropertyEditContext,
        label_width: int,
    ):
        super().__init__(parent, context)
        self._label_width = label_width
        self._dialog: TreePropertyDialog | None = None
        self._init_ui()

    def _init_ui(self):
        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(4)

        theme = ThemeService()

        # # 标签和编辑按钮（暂时隐藏）
        # header_layout = QtWidgets.QHBoxLayout()
        # header_layout.setContentsMargins(0, 0, 0, 0)
        # header_layout.setSpacing(8)
        # header_layout.addWidget(self._create_label(self._label_width))
        # brand_color = theme.get_color_hex("brand")
        # edit_btn = QtWidgets.QPushButton("✎ 编辑属性")
        # edit_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        # edit_btn.setStyleSheet(f"""
        #     QPushButton {{
        #         background-color: {brand_color};
        #         color: white;
        #         border: none;
        #         border-radius: 4px;
        #         padding: 4px 12px;
        #         font-weight: bold;
        #     }}
        #     QPushButton:hover {{ background-color: {brand_color}dd; }}
        #     QPushButton:pressed {{ background-color: {brand_color}bb; }}
        # """)
        # edit_btn.clicked.connect(self._on_edit_clicked)
        # header_layout.addWidget(edit_btn)
        # header_layout.addStretch()
        # root_layout.addLayout(header_layout)

        names = collect_all_names(self.context.group.tree_data)
        if names:
            bg_color = theme.get_color_hex("property_group_bg")
            text_color = theme.get_color_hex("text")

            names_edit = QtWidgets.QPlainTextEdit(", ".join(names))
            names_edit.setReadOnly(True)
            names_edit.setMaximumHeight(80)
            names_edit.setStyleSheet(f"""
                QPlainTextEdit {{
                    background-color: {bg_color};
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 4px;
                    padding: 4px;
                    color: {text_color};
                }}
            """)
            root_layout.addWidget(names_edit)

    # # 编辑对话框（暂时隐藏）
    # def _on_edit_clicked(self):
    #     if self._dialog is None:
    #         self._dialog = TreePropertyDialog(
    #             self.window(), self.context, self._label_width
    #         )
    #     self._dialog.exec()

    def set_value(self, value: Any):
        pass

    def set_read_only(self, read_only: bool):
        pass
        # if self._dialog:
        #     for edit in self._dialog._node_widgets:
        #         for e in edit.get_property_edits():
        #             e.set_read_only(read_only)

    def set_child_value(self, property_name: str, value: Any):
        pass
        # if self._dialog:
        #     self._dialog.set_child_value(property_name, value)

    def set_child_read_only(self, property_name: str, read_only: bool):
        pass
        # if self._dialog:
        #     self._dialog.set_child_read_only(property_name, read_only)
