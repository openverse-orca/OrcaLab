from typing import override
from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.ui.edit.base_number_edit import BaseNumberEdit


def is_close(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) < tol


class FloatEdit(BaseNumberEdit[float]):
    def __init__(self, parent: QtWidgets.QWidget | None = None, step: float = 0.01):
        super().__init__(parent)

        self.setValidator(QtGui.QDoubleValidator())
        self._value = 0.0
        self.setText("0.0")
        self._step = step

    @override
    def _text_to_value(self, text: str) -> float | None:
        try:
            value = float(text)
            return value
        except ValueError:
            pass

    @override
    def _value_to_text(self, value: float) -> str:
        return f"{value:.2f}"

    @override
    def value(self) -> float:
        return self._value

    @override
    def _set_value_only(self, value: float) -> bool:
        if is_close(value, self._value):
            return False

        self._value = value
        return True

    @override
    def step(self) -> float:
        return self._step
