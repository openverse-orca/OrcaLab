from PySide6 import QtCore, QtWidgets, QtGui

from enum import Enum, auto


class BaseNumberEditState(Enum):
    Idle = auto()
    MouseDown = auto()
    Typing = auto()
    Dragging = auto()


class BaseNumberEdit[T: (int, float)](QtWidgets.QLineEdit):
    value_changed = QtCore.Signal()
    start_drag = QtCore.Signal()
    stop_drag = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)

        self.installEventFilter(self)

        self._state = BaseNumberEditState.Idle
        self.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)

        self._real_time_type = False
        self._real_time_drag = True

        self._original_value: T | None = None

        self._dragging = False

        self.textChanged.connect(self._text_changed)

    def set_state(self, state: BaseNumberEditState):
        if state == BaseNumberEditState.Idle:
            assert self._state in [
                BaseNumberEditState.Typing,
                BaseNumberEditState.Dragging,
            ]
            self.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)
        elif state == BaseNumberEditState.MouseDown:
            assert self._state == BaseNumberEditState.Idle
        elif state == BaseNumberEditState.Typing:
            assert self._state == BaseNumberEditState.MouseDown
            self.setCursor(QtCore.Qt.CursorShape.IBeamCursor)
        elif state == BaseNumberEditState.Dragging:
            assert self._state == BaseNumberEditState.MouseDown
        else:
            raise Exception(f"Invalid state transition: {self._state} -> {state}")

        self._state = state

    def eventFilter(self, watched, event: QtCore.QEvent) -> bool:

        if event.type() == QtCore.QEvent.Type.KeyPress:
            assert isinstance(event, QtGui.QKeyEvent)
            if self._handle_key_press(event):
                return True

        if event.type() == QtCore.QEvent.Type.FocusOut:
            if self._state == BaseNumberEditState.Typing:
                value = self.value()
                assert self._original_value is not None
                self._set_value_only(self._original_value)
                if self._set_value_only(value):
                    self.value_changed.emit()
                self.set_state(BaseNumberEditState.Idle)
                self._original_value = self.value()

        if event.type() == QtCore.QEvent.Type.MouseButtonPress:
            if self._state == BaseNumberEditState.Idle:
                assert isinstance(event, QtGui.QMouseEvent)
                self.grabMouse()
                self.set_state(BaseNumberEditState.MouseDown)
                self.last_mouse_pos = event.globalPosition()
                self._original_value = self.value()

        if event.type() == QtCore.QEvent.Type.MouseButtonRelease:
            if self._state == BaseNumberEditState.MouseDown:
                self.releaseMouse()
                self.setFocus()
                self.set_state(BaseNumberEditState.Typing)

            if self._state == BaseNumberEditState.Dragging:
                self.releaseMouse()
                self.set_state(BaseNumberEditState.Idle)
                self.setProperty("dragging", False)
                self.style().unpolish(self)
                self.style().polish(self)

                if not self._real_time_drag:
                    self.value_changed.emit()

                self.stop_drag.emit()

        if event.type() == QtCore.QEvent.Type.MouseMove:
            if self._state == BaseNumberEditState.MouseDown:
                self.set_state(BaseNumberEditState.Dragging)
                self.setProperty("dragging", True)
                self.style().unpolish(self)
                self.style().polish(self)
                self.start_drag.emit()

            if self._state == BaseNumberEditState.Dragging:
                assert isinstance(event, QtGui.QMouseEvent)
                delta = event.globalPosition().x() - self.last_mouse_pos.x()
                self._on_drag(delta)
                self.last_mouse_pos = event.globalPosition()

                # prevent selecting text while dragging
                return True

        return super().eventFilter(watched, event)

    def _handle_key_press(self, event: QtGui.QKeyEvent) -> bool:
        if not self._state == BaseNumberEditState.Typing:
            return False

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
            assert self._state == BaseNumberEditState.Idle

            return True

        if event.key() == QtCore.Qt.Key.Key_Up:
            self._increase(self._real_time_type)
            return True
        if event.key() == QtCore.Qt.Key.Key_Down:
            self._decrease(self._real_time_type)
            return True

        return False

    def _text_changed(self, text: str):
        if self._state != BaseNumberEditState.Typing:
            return

        value = self._text_to_value(text)

        if value is None:
            return

        if self._set_value_only(value) and self._real_time_type:
            self.value_changed.emit()

    def _set_value_and_text(self, value: T) -> bool:
        if self._set_value_only(value):
            text = self._value_to_text(value)
            self.setText(text)
            return True
        return False

    def _increase(self, emit_signal: bool):
        new_value = self.value() + self.step()
        if self._set_value_and_text(new_value):
            if emit_signal:
                self.value_changed.emit()

    def _decrease(self, emit_signal: bool):
        new_value = self.value() - self.step()
        if self._set_value_and_text(new_value):
            if emit_signal:
                self.value_changed.emit()

    def _on_drag(self, delta_x: float):
        if abs(delta_x) < 1e-3:
            return

        if delta_x > 0:
            self._increase(self._real_time_drag)
        else:
            self._decrease(self._real_time_drag)

    def _text_to_value(self, text: str) -> T | None:
        raise NotImplementedError()

    def _value_to_text(self, value: T) -> str:
        raise NotImplementedError()

    def value(self) -> T:
        raise NotImplementedError()

    def set_value(self, value: T):
        self._set_value_and_text(value)

    def _set_value_only(self, value: T) -> bool:
        raise NotImplementedError()

    def step(self) -> T:
        raise NotImplementedError()
