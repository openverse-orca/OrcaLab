from typing import override
from PySide6 import QtCore, QtWidgets, QtGui


from orcalab.ui.property_edit.base_property_edit import (
    BasePropertyEdit,
    PropertyEditContext,
)
from orcalab.ui.edit.string_edit import StringEdit
from orcalab.ui.edit.multiline_string_edit import MultilineStringEdit


class StringPropertyEdit(BasePropertyEdit[str]):

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        context: PropertyEditContext,
        label_width: int,
    ):
        super().__init__(parent, context)
        
        # 检查是否需要多行编辑器
        is_multiline = context.prop.editor_hint() == "multi_line"
        
        if is_multiline:
            # 使用垂直布局以便标签在上方
            root_layout = QtWidgets.QVBoxLayout(self)
            root_layout.setContentsMargins(0, 0, 0, 0)
            root_layout.setSpacing(4)
            
            label = self._create_label(label_width)
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
            
            editor = MultilineStringEdit()
            editor.setText(context.prop.value())
            editor.value_changed.connect(self._on_text_changed)
            
            root_layout.addWidget(label)
            root_layout.addWidget(editor)
        else:
            # 使用水平布局
            root_layout = QtWidgets.QHBoxLayout(self)
            root_layout.setContentsMargins(0, 0, 0, 0)
            root_layout.setSpacing(4)

            label = self._create_label(label_width)

            editor = StringEdit()
            editor.setText(context.prop.value())
            editor.value_changed.connect(self._on_text_changed)
            editor.setStyleSheet(self.base_style)
            editor.setFocusPolicy(QtCore.Qt.FocusPolicy.ClickFocus)

            root_layout.addWidget(label)
            root_layout.addWidget(editor)

        self._editor = editor
        self._block_events = False
        self._is_multiline = is_multiline

    def _on_text_changed(self):
        if self._block_events:
            return

        text = self._editor.text()
        self.context.prop.set_value(text)

        undo = not self.in_dragging
        self._do_set_value(text, undo)

    @override
    def set_value(self, value: str):
        self._block_events = True

        self.context.prop.set_value(value)
        self._editor.setText(value)

        self._block_events = False

    @override
    def set_read_only(self, read_only: bool):
        self._editor.setReadOnly(read_only)
        
        # 对于多行只读编辑器，设置更好的样式
        if self._is_multiline and read_only:
            from orcalab.ui.theme_service import ThemeService
            theme = ThemeService()
            bg_color = theme.get_color_hex("property_group_bg")
            text_color = theme.get_color_hex("text")
            
            self._editor.setStyleSheet(f"""
                QPlainTextEdit {{
                    background-color: {bg_color};
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 4px;
                    padding: 4px;
                    color: {text_color};
                }}
            """)
