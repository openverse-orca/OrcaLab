from typing import override
from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.ui.edit.base_number_edit import BaseNumberEdit


class IntEdit(BaseNumberEdit[int]):
    def __init__(self, parent: QtWidgets.QWidget | None = None, step: int = 1):
        super().__init__(parent)

        self.setValidator(QtGui.QIntValidator())
        self._value: int = 0
        self.setText("0")
        self._step = step

    @override
    def _text_to_value(self, text: str) -> int | None:
        try:
            value = int(text)
            return value
        except ValueError:
            return None

    @override
    def _value_to_text(self, value) -> str:
        return f"{value}"

    @override
    def value(self) -> int:
        return int(self._value)

    @override
    def _set_value_only(self, value: int) -> bool:
        if value == self._value:
            return False
        self._value = value
        return True

    @override
    def step(self) -> int:
        return self._step
