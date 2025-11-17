from PySide6 import QtCore, QtWidgets, QtGui

from enum import Enum, auto


class StringEditState(Enum):
    Idle = auto()
    Typing = auto()


class StringEdit(QtWidgets.QLineEdit):
    value_changed = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

        self.installEventFilter(self)

        self._state = StringEditState.Idle

        self._real_time_type = False

        self._value = ""
        self.setText("")
        self._original_value: str | None = None

        self.textChanged.connect(self._text_changed)

    def set_state(self, state: StringEditState):
        if state == StringEditState.Idle:
            assert self._state == StringEditState.Typing
        elif state == StringEditState.Typing:
            assert self._state == StringEditState.Idle
        else:
            raise Exception(f"Invalid state transition: {self._state} -> {state}")

        self._state = state

    def eventFilter(self, watched, event: QtCore.QEvent) -> bool:

        if event.type() == QtCore.QEvent.Type.KeyPress:
            assert isinstance(event, QtGui.QKeyEvent)
            self._handle_key_press(event)

        if event.type() == QtCore.QEvent.Type.FocusOut:
            if self._state == StringEditState.Typing:
                self.set_state(StringEditState.Idle)
                self._original_value = None

        if event.type() == QtCore.QEvent.Type.MouseButtonPress:
            if self._state == StringEditState.Idle:
                assert isinstance(event, QtGui.QMouseEvent)
                self.setFocus()
                self.set_state(StringEditState.Typing)
                self._original_value = self.value()

        return super().eventFilter(watched, event)

    def _handle_key_press(self, event: QtGui.QKeyEvent):
        if not self._state == StringEditState.Typing:
            return

        keys = [
            QtCore.Qt.Key.Key_Return,
            QtCore.Qt.Key.Key_Enter,
            QtCore.Qt.Key.Key_Escape,
        ]
        if self.hasFocus() and event.key() in keys:

            if not self._real_time_type:
                value = self.value()
                assert self._original_value is not None
                self._set_value_only(self._original_value)
                if self._set_value_only(value):
                    self.value_changed.emit()

            # clearFocus will trigger FocusOut event, which will set state to Idle
            self.clearFocus()
            assert self._state == StringEditState.Idle

            return

    def _text_changed(self, text: str):
        if self._state != StringEditState.Typing:
            return

        if self._set_value_only(text) and self._real_time_type:
            self.value_changed.emit()

    def _set_value_and_text(self, value: str):
        if self._set_value_only(value):
            self.setText(value)
            return True
        return False

    def value(self):
        return self._value

    def set_value(self, value):
        self._set_value_and_text(value)

    def _set_value_only(self, value: str) -> bool:
        if value == self._value:
            return False
        self._value = value
        return True
