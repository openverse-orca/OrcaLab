import asyncio

from PySide6 import QtCore, QtWidgets, QtGui

from enum import Enum, auto
from typing import TypeVar, Generic, Union

_T_num = TypeVar("_T_num", int, float)


class BaseNumberEditState(Enum):
    Idle = auto()
    MouseDown = auto()
    Typing = auto()
    Dragging = auto()


async def on_start_drag_default():
    pass


async def on_stop_drag_default():
    pass


async def on_value_changed_default():
    pass


class BaseNumberEdit(Generic[_T_num], QtWidgets.QLineEdit):
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

        self._original_value: _T_num | None = None

        self._dragging = False

        self.on_start_drag = on_start_drag_default
        self.on_stop_drag = on_stop_drag_default
        self.on_value_changed = on_value_changed_default

        self._mouse_down_pos: QtCore.QPointF | None = None

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
                if value != self._original_value:
                    self._notify_value_changed()
                self.set_state(BaseNumberEditState.Idle)
                self._original_value = None

        if event.type() == QtCore.QEvent.Type.MouseButtonPress:
            if self._state == BaseNumberEditState.Idle and not self.isReadOnly():
                assert isinstance(event, QtGui.QMouseEvent)
                self.grabMouse()
                self.set_state(BaseNumberEditState.MouseDown)
                self._last_mouse_pos = event.globalPosition()
                self._mouse_down_pos = event.globalPosition()

        if event.type() == QtCore.QEvent.Type.MouseButtonRelease:
            if self._state == BaseNumberEditState.MouseDown:
                self.releaseMouse()
                self.setFocus()
                self.set_state(BaseNumberEditState.Typing)
                self._original_value = self.value()

            if self._state == BaseNumberEditState.Dragging:
                self.releaseMouse()
                self.set_state(BaseNumberEditState.Idle)
                self.setProperty("dragging", False)
                self.style().unpolish(self)
                self.style().polish(self)

                if not self._real_time_drag:
                    self._notify_value_changed()

                self._notify_stop_drag()

            self._mouse_down_pos = None

        if event.type() == QtCore.QEvent.Type.MouseMove:
            if self._state == BaseNumberEditState.MouseDown:
                assert isinstance(event, QtGui.QMouseEvent)

                if self._mouse_down_pos is None:
                    return False

                delta = (
                    event.globalPosition() - self._mouse_down_pos
                ).manhattanLength()
                if delta < 3.0:
                    return False

                self.set_state(BaseNumberEditState.Dragging)
                self.setProperty("dragging", True)
                self.style().unpolish(self)
                self.style().polish(self)
                self._notify_start_drag()

            if self._state == BaseNumberEditState.Dragging:
                assert isinstance(event, QtGui.QMouseEvent)
                delta = event.globalPosition().x() - self._last_mouse_pos.x()
                self._on_drag(delta)
                self._last_mouse_pos = event.globalPosition()

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
            if self._state == BaseNumberEditState.Typing:
                if not self._real_time_type:
                    value = self.value()
                    assert self._original_value is not None
                    if value != self._original_value:
                        self._notify_value_changed()
                self.set_state(BaseNumberEditState.Idle)
                self._original_value = None

            # clearFocus will trigger FocusOut event
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
            self._notify_value_changed()

    def _set_value_and_text(self, value: _T_num) -> bool:
        if self._set_value_only(value):
            text = self._value_to_text(value)
            self.setText(text)
            return True
        return False

    def _increase(self, emit_signal: bool):
        new_value = self.value() + self.step()
        if self._set_value_and_text(new_value):
            if emit_signal:
                self._notify_value_changed()

    def _decrease(self, emit_signal: bool):
        new_value = self.value() - self.step()
        if self._set_value_and_text(new_value):
            if emit_signal:
                self._notify_value_changed()

    def _on_drag(self, delta_x: float):
        if abs(delta_x) < 1e-3:
            return

        if delta_x > 0:
            self._increase(self._real_time_drag)
        else:
            self._decrease(self._real_time_drag)

    def _text_to_value(self, text: str) -> _T_num | None:
        raise NotImplementedError()

    def _value_to_text(self, value: _T_num) -> str:
        raise NotImplementedError()

    def value(self) -> _T_num:
        raise NotImplementedError()

    def set_value(self, value: _T_num):
        self._set_value_and_text(value)

    def _set_value_only(self, value: _T_num) -> bool:
        raise NotImplementedError()

    def step(self) -> _T_num:
        raise NotImplementedError()

    def paintEvent(self, event):
        if self._state != BaseNumberEditState.Typing:
            self.setCursorPosition(0)
        super().paintEvent(event)

    def setReadOnly(self, ro: bool):
        super().setReadOnly(ro)
        if ro:
            self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
        else:
            self.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)

    def _notify_value_changed(self):
        asyncio.create_task(self.on_value_changed())

    def _notify_start_drag(self):
        asyncio.create_task(self.on_start_drag())

    def _notify_stop_drag(self):
        asyncio.create_task(self.on_stop_drag())
