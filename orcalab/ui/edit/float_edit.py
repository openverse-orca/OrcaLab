from typing_extensions import override
from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.ui.edit.base_number_edit import BaseNumberEdit, BaseNumberEditState


def is_close(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) < tol


class FloatEdit(BaseNumberEdit[float]):
    def __init__(self, parent: QtWidgets.QWidget | None = None, step: float = 0.01):
        super().__init__(parent)

        self.setValidator(QtGui.QDoubleValidator())
        self._value = 0.0
        self.setText("0.0")
        self._step = step
        self.max_float_before_precision_loss = 100000.0

    @override
    def _text_to_value(self, text: str) -> float | None:
        try:
            value = float(text)
            return value
        except ValueError:
            pass

    @override
    def _value_to_text(self, value: float) -> str:
        return f"{value:.3f}"

    @override
    def value(self) -> float:
        return self._value

    @override
    def _set_value_only(self, value: float) -> bool:
        clamped = max(
            -self.max_float_before_precision_loss,
            min(value, self.max_float_before_precision_loss),
        )

        is_clamped = False
        if clamped == self.max_float_before_precision_loss or clamped == -self.max_float_before_precision_loss:
            is_clamped = True

        if is_close(clamped, self._value) and not is_clamped:
            return False

        self._value = clamped
        return True

    @override
    def step(self) -> float:
        return self._step
