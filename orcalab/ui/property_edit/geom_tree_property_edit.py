from typing import Any, Set
import asyncio
from PySide6 import QtWidgets

from orcalab.actor_property import TreePropertyNode
from orcalab.ui.property_edit.base_property_edit import BasePropertyEdit, PropertyEditContext
from orcalab.ui.property_edit.tree_property_edit import (
    TreeLeafButton,
    _build_nodes,
    _send_highlight,
)

# 与 Joint/Site 高亮隔离的独立存储
_geom_highlight_store: dict[str, Set[int]] = {}


class GeomButton(TreeLeafButton):
    """碰撞体叶节点按钮。"""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        node: TreePropertyNode,
        context: PropertyEditContext,
        label_width: int,
        initially_highlighted: bool = False,
    ):
        super().__init__(
            parent, node, context, label_width, initially_highlighted,
            highlight_store=_geom_highlight_store,
        )

    def _dialog_title(self) -> str:
        return f"编辑碰撞体 - {self._node.display_name}"


class GeomTreePropertyEdit(BasePropertyEdit):
    """Geom 碰撞体树属性编辑器：左键高亮线框，右键属性对话框。"""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        context: PropertyEditContext,
        label_width: int,
    ):
        super().__init__(parent, context)
        self._label_width = label_width
        self._actor_path_str = str(context.actor_path)
        self._leaf_buttons: dict[str, GeomButton] = {}
        self._init_ui()
        asyncio.ensure_future(self._restore_highlights())

    async def _restore_highlights(self):
        for eid in _geom_highlight_store.get(self._actor_path_str, set()):
            await _send_highlight(eid, True)

    async def _clear_highlights(self):
        for eid in _geom_highlight_store.get(self._actor_path_str, set()):
            await _send_highlight(eid, False)

    def hideEvent(self, event):
        super().hideEvent(event)
        asyncio.ensure_future(self._clear_highlights())

    def _init_ui(self):
        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(2)
        tree_data = self.context.group.tree_data
        if tree_data:
            highlight_set = _geom_highlight_store.setdefault(self._actor_path_str, set())
            _build_nodes(
                tree_data, root_layout, self.context, self._label_width,
                indent=0, highlight_set=highlight_set,
                button_registry=self._leaf_buttons,
                button_cls=GeomButton, skip_unnamed=False,
            )

    def set_value(self, value: Any):
        pass

    def set_read_only(self, read_only: bool):
        pass

    def set_child_value(self, property_name: str, value: Any):
        dot_pos = property_name.rfind(".")
        if dot_pos == -1:
            return
        node_key = property_name[:dot_pos]
        if property_name[dot_pos + 1:] != "Name":
            return
        btn = self._leaf_buttons.get(node_key)
        if btn is not None and isinstance(value, str):
            btn.setText(value)

    def set_child_read_only(self, property_name: str, read_only: bool):
        pass
