from orcalab.ui.user_event import KeyCode
from PySide6 import QtGui
from PySide6.QtCore import Qt


_key_mapping: dict[Qt.Key, KeyCode] = {
    #
    # number keys
    #
    Qt.Key.Key_0: KeyCode.Digit0,
    Qt.Key.Key_1: KeyCode.Digit1,
    Qt.Key.Key_2: KeyCode.Digit2,
    Qt.Key.Key_3: KeyCode.Digit3,
    Qt.Key.Key_4: KeyCode.Digit4,
    Qt.Key.Key_5: KeyCode.Digit5,
    Qt.Key.Key_6: KeyCode.Digit6,
    Qt.Key.Key_7: KeyCode.Digit7,
    Qt.Key.Key_8: KeyCode.Digit8,
    Qt.Key.Key_9: KeyCode.Digit9,
    #
    # number keys with shift
    #
    Qt.Key.Key_Exclam: KeyCode.Digit1,
    Qt.Key.Key_At: KeyCode.Digit2,
    Qt.Key.Key_NumberSign: KeyCode.Digit3,
    Qt.Key.Key_Dollar: KeyCode.Digit4,
    Qt.Key.Key_Percent: KeyCode.Digit5,
    Qt.Key.Key_AsciiCircum: KeyCode.Digit6,
    Qt.Key.Key_Ampersand: KeyCode.Digit7,
    Qt.Key.Key_Asterisk: KeyCode.Digit8,
    Qt.Key.Key_ParenLeft: KeyCode.Digit9,
    Qt.Key.Key_ParenRight: KeyCode.Digit0,
    #
    # letter keys
    #
    Qt.Key.Key_A: KeyCode.KeyA,
    Qt.Key.Key_B: KeyCode.KeyB,
    Qt.Key.Key_C: KeyCode.KeyC,
    Qt.Key.Key_D: KeyCode.KeyD,
    Qt.Key.Key_E: KeyCode.KeyE,
    Qt.Key.Key_F: KeyCode.KeyF,
    Qt.Key.Key_G: KeyCode.KeyG,
    Qt.Key.Key_H: KeyCode.KeyH,
    Qt.Key.Key_I: KeyCode.KeyI,
    Qt.Key.Key_J: KeyCode.KeyJ,
    Qt.Key.Key_K: KeyCode.KeyK,
    Qt.Key.Key_L: KeyCode.KeyL,
    Qt.Key.Key_M: KeyCode.KeyM,
    Qt.Key.Key_N: KeyCode.KeyN,
    Qt.Key.Key_O: KeyCode.KeyO,
    Qt.Key.Key_P: KeyCode.KeyP,
    Qt.Key.Key_Q: KeyCode.KeyQ,
    Qt.Key.Key_R: KeyCode.KeyR,
    Qt.Key.Key_S: KeyCode.KeyS,
    Qt.Key.Key_T: KeyCode.KeyT,
    Qt.Key.Key_U: KeyCode.KeyU,
    Qt.Key.Key_V: KeyCode.KeyV,
    Qt.Key.Key_W: KeyCode.KeyW,
    Qt.Key.Key_X: KeyCode.KeyX,
    Qt.Key.Key_Y: KeyCode.KeyY,
    Qt.Key.Key_Z: KeyCode.KeyZ,
    #
    # function keys
    #
    Qt.Key.Key_F1: KeyCode.F1,
    Qt.Key.Key_F2: KeyCode.F2,
    Qt.Key.Key_F3: KeyCode.F3,
    Qt.Key.Key_F4: KeyCode.F4,
    Qt.Key.Key_F5: KeyCode.F5,
    Qt.Key.Key_F6: KeyCode.F6,
    Qt.Key.Key_F7: KeyCode.F7,
    Qt.Key.Key_F8: KeyCode.F8,
    Qt.Key.Key_F9: KeyCode.F9,
    Qt.Key.Key_F10: KeyCode.F10,
    Qt.Key.Key_F11: KeyCode.F11,
    Qt.Key.Key_F12: KeyCode.F12,
    Qt.Key.Key_F13: KeyCode.F13,
    Qt.Key.Key_F14: KeyCode.F14,
    Qt.Key.Key_F15: KeyCode.F15,
    Qt.Key.Key_F16: KeyCode.F16,
    Qt.Key.Key_F17: KeyCode.F17,
    Qt.Key.Key_F18: KeyCode.F18,
    #
    # symbol keys
    #
    Qt.Key.Key_Comma: KeyCode.Comma,
    Qt.Key.Key_Period: KeyCode.Period,
    Qt.Key.Key_Slash: KeyCode.Slash,
    Qt.Key.Key_Semicolon: KeyCode.Semicolon,
    Qt.Key.Key_Apostrophe: KeyCode.Quote,
    Qt.Key.Key_BracketLeft: KeyCode.BracketLeft,
    Qt.Key.Key_BracketRight: KeyCode.BracketRight,
    Qt.Key.Key_Backslash: KeyCode.Backslash,
    Qt.Key.Key_QuoteLeft: KeyCode.Backquote,
    Qt.Key.Key_Minus: KeyCode.Minus,
    Qt.Key.Key_Equal: KeyCode.Equal,
    Qt.Key.Key_Backspace: KeyCode.Backspace,
    Qt.Key.Key_Tab: KeyCode.Tab,
    Qt.Key.Key_Return: KeyCode.Enter,
    Qt.Key.Key_Enter: KeyCode.Enter,
    Qt.Key.Key_Space: KeyCode.Space,
    Qt.Key.Key_Shift: KeyCode.ShiftLeft,
    Qt.Key.Key_Control: KeyCode.ControlLeft,
    Qt.Key.Key_Alt: KeyCode.AltLeft,
    Qt.Key.Key_Escape: KeyCode.Escape,
    Qt.Key.Key_PageUp: KeyCode.PageUp,
    Qt.Key.Key_PageDown: KeyCode.PageDown,
    Qt.Key.Key_End: KeyCode.End,
    Qt.Key.Key_Home: KeyCode.Home,
    Qt.Key.Key_Left: KeyCode.ArrowLeft,
    Qt.Key.Key_Up: KeyCode.ArrowUp,
    Qt.Key.Key_Right: KeyCode.ArrowRight,
    Qt.Key.Key_Down: KeyCode.ArrowDown,
    Qt.Key.Key_CapsLock: KeyCode.CapsLock,
    Qt.Key.Key_Insert: KeyCode.Insert,
    Qt.Key.Key_Delete: KeyCode.Delete,
    #
    # symbol keys with shift
    #
    Qt.Key.Key_AsciiTilde: KeyCode.Backquote,
    Qt.Key.Key_BraceLeft: KeyCode.BracketLeft,
    Qt.Key.Key_BraceRight: KeyCode.BracketRight,
    Qt.Key.Key_Bar: KeyCode.Backslash,
    Qt.Key.Key_Colon: KeyCode.Semicolon,
    Qt.Key.Key_QuoteDbl: KeyCode.Quote,
    Qt.Key.Key_Less: KeyCode.Comma,
    Qt.Key.Key_Greater: KeyCode.Period,
    Qt.Key.Key_Question: KeyCode.Slash,
}

_number_pad_mapping: dict[Qt.Key, KeyCode] = {
    Qt.Key.Key_0: KeyCode.Numpad0,
    Qt.Key.Key_1: KeyCode.Numpad1,
    Qt.Key.Key_2: KeyCode.Numpad2,
    Qt.Key.Key_3: KeyCode.Numpad3,
    Qt.Key.Key_4: KeyCode.Numpad4,
    Qt.Key.Key_5: KeyCode.Numpad5,
    Qt.Key.Key_6: KeyCode.Numpad6,
    Qt.Key.Key_7: KeyCode.Numpad7,
    Qt.Key.Key_8: KeyCode.Numpad8,
    Qt.Key.Key_9: KeyCode.Numpad9,
    Qt.Key.Key_NumLock: KeyCode.NumLock,
    Qt.Key.Key_Slash: KeyCode.NumpadDivide,
    Qt.Key.Key_Asterisk: KeyCode.NumpadMultiply,
    Qt.Key.Key_Minus: KeyCode.NumpadSubtract,
    Qt.Key.Key_Plus: KeyCode.NumpadAdd,
    Qt.Key.Key_Enter: KeyCode.NumpadEnter,
    Qt.Key.Key_Period: KeyCode.NumpadDecimal,
    Qt.Key.Key_Enter: KeyCode.NumpadEnter,
    Qt.Key.Key_Enter: KeyCode.NumpadEnter,
}


def convert_key_code(qt_key_event: QtGui.QKeyEvent) -> KeyCode:

    qt_key_code = Qt.Key(qt_key_event.key())
    if qt_key_event.modifiers() & Qt.KeyboardModifier.KeypadModifier:
        if qt_key_code in _number_pad_mapping:
            return _number_pad_mapping[qt_key_code]
    else:
        if qt_key_code in _key_mapping:
            return _key_mapping[qt_key_code]

    raise ValueError(f"Unsupported Qt key code: {qt_key_code}")
