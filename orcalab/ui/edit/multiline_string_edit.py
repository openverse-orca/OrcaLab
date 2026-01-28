from PySide6 import QtCore, QtWidgets, QtGui


class MultilineStringEdit(QtWidgets.QPlainTextEdit):
    """多行字符串编辑器"""
    value_changed = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.ClickFocus)
        
        # 设置合理的默认高度
        font_metrics = self.fontMetrics()
        line_height = font_metrics.lineSpacing()
        self.setMinimumHeight(line_height * 3 + 10)  # 默认显示3行
        
        self._block_signals = False
        self.textChanged.connect(self._on_text_changed)

    def _on_text_changed(self):
        if not self._block_signals:
            self.value_changed.emit()

    def setText(self, text: str):
        """设置文本"""
        self._block_signals = True
        self.setPlainText(text)
        self._block_signals = False

    def text(self) -> str:
        """获取文本"""
        return self.toPlainText()

    def value(self) -> str:
        """获取值（与text()相同，保持接口一致）"""
        return self.toPlainText()

    def set_value(self, value: str):
        """设置值"""
        self.setText(value)

