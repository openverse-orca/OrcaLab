from __future__ import annotations

import os
from importlib import import_module
from typing import Any, Callable


_DEFAULT_LANGUAGE = "zh_CN"
_language = _DEFAULT_LANGUAGE
_translations: dict[str, str] = {}
_qt_hooks_installed = False


def normalize_language(language: str | None) -> str:
    value = (language or "").strip().replace("-", "_").lower()
    if value in {"en", "en_us", "english"}:
        return "en_US"
    if value in {"zh", "zh_cn", "cn", "chinese", "simpchinese", "simplified_chinese"}:
        return "zh_CN"
    return _DEFAULT_LANGUAGE


def _load_translations(language: str) -> dict[str, str]:
    if language != "en_US":
        return {}
    module = import_module("orcalab.translations.en_us")
    return getattr(module, "TRANSLATIONS", {})


def set_language(language: str | None) -> str:
    global _language, _translations
    _language = normalize_language(language)
    _translations = _load_translations(_language)
    os.environ["ORCALAB_LANG"] = _language
    return _language


def configure_from_environment() -> str:
    return set_language(os.environ.get("ORCALAB_LANG"))


def get_language() -> str:
    return _language


def is_english() -> bool:
    return _language == "en_US"


def tr(text: Any, **kwargs: Any) -> Any:
    if not isinstance(text, str):
        return text
    translated = _translations.get(text, text)
    if kwargs:
        try:
            return translated.format(**kwargs)
        except Exception:
            return translated
    return translated


def _wrap_text_arg(func: Callable[..., Any], indexes: tuple[int, ...]) -> Callable[..., Any]:
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        mutable = list(args)
        for index in indexes:
            if index >= len(mutable):
                continue
            value = mutable[index]
            if isinstance(value, str):
                mutable[index] = tr(value)
            elif isinstance(value, list):
                mutable[index] = [tr(item) for item in value]
            elif isinstance(value, tuple):
                mutable[index] = tuple(tr(item) for item in value)
        return func(*mutable, **kwargs)

    return wrapper


def _patch_method(cls: type, name: str, indexes: tuple[int, ...] = (1,)) -> None:
    marker = f"__orcalab_i18n_original_{name}"
    if hasattr(cls, marker):
        return
    try:
        original = getattr(cls, name)
        setattr(cls, marker, original)
        setattr(cls, name, _wrap_text_arg(original, indexes))
    except (AttributeError, TypeError):
        return


def _patch_constructor(cls: type, indexes: tuple[int, ...] = (1,)) -> None:
    _patch_method(cls, "__init__", indexes)


def _patch_message_box_static(QtWidgets: Any, name: str) -> None:
    cls = QtWidgets.QMessageBox
    marker = f"__orcalab_i18n_original_static_{name}"
    if hasattr(cls, marker):
        return
    original = getattr(cls, name)
    try:
        setattr(cls, marker, original)
    except (AttributeError, TypeError):
        return

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        mutable = list(args)
        if len(mutable) > 1 and isinstance(mutable[1], str):
            mutable[1] = tr(mutable[1])
        if len(mutable) > 2 and isinstance(mutable[2], str):
            mutable[2] = tr(mutable[2])
        return original(*mutable, **kwargs)

    try:
        setattr(cls, name, staticmethod(wrapper))
    except (AttributeError, TypeError):
        return


def _patch_file_dialog_static(QtWidgets: Any, name: str) -> None:
    cls = QtWidgets.QFileDialog
    marker = f"__orcalab_i18n_original_static_{name}"
    if hasattr(cls, marker):
        return
    original = getattr(cls, name)
    try:
        setattr(cls, marker, original)
    except (AttributeError, TypeError):
        return

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        mutable = list(args)
        if len(mutable) > 1 and isinstance(mutable[1], str):
            mutable[1] = tr(mutable[1])
        if len(mutable) > 3 and isinstance(mutable[3], str):
            mutable[3] = tr(mutable[3])
        return original(*mutable, **kwargs)

    try:
        setattr(cls, name, staticmethod(wrapper))
    except (AttributeError, TypeError):
        return


def install_qt_translation_hooks() -> None:
    """Translate known UI strings as widgets are created or updated."""
    global _qt_hooks_installed
    if _qt_hooks_installed:
        return

    from PySide6 import QtGui, QtWidgets

    for cls in (
        QtWidgets.QLabel,
        QtWidgets.QPushButton,
        QtWidgets.QRadioButton,
        QtWidgets.QCheckBox,
        QtWidgets.QGroupBox,
        QtWidgets.QMenu,
    ):
        _patch_constructor(cls)

    _patch_constructor(QtGui.QAction, (1, 2))

    for cls in (
        QtWidgets.QWidget,
        QtWidgets.QDialog,
        QtWidgets.QMessageBox,
    ):
        _patch_method(cls, "setWindowTitle")
        _patch_method(cls, "setToolTip")

    for cls in (
        QtWidgets.QLabel,
        QtWidgets.QAbstractButton,
        QtWidgets.QMessageBox,
    ):
        _patch_method(cls, "setText")

    _patch_method(QtWidgets.QGroupBox, "setTitle")
    _patch_method(QtWidgets.QMenu, "setTitle")
    _patch_method(QtWidgets.QMenuBar, "addMenu")
    _patch_method(QtGui.QAction, "setText")
    _patch_method(QtGui.QAction, "setToolTip")
    _patch_method(QtWidgets.QLineEdit, "setPlaceholderText")
    _patch_method(QtWidgets.QTextEdit, "setPlaceholderText")
    _patch_method(QtWidgets.QPlainTextEdit, "setPlaceholderText")
    _patch_method(QtWidgets.QMessageBox, "setInformativeText")
    _patch_method(QtWidgets.QMessageBox, "setDetailedText")
    _patch_method(QtWidgets.QMessageBox, "addButton")
    _patch_method(QtWidgets.QComboBox, "addItem")
    _patch_method(QtWidgets.QTableWidget, "setHorizontalHeaderLabels")
    _patch_method(QtWidgets.QTableWidget, "setVerticalHeaderLabels")
    _patch_method(QtWidgets.QTreeWidget, "setHeaderLabel")
    _patch_method(QtWidgets.QTreeWidget, "setHeaderLabels")
    _patch_method(QtWidgets.QMenu, "addAction")
    _patch_method(QtWidgets.QDialogButtonBox, "addButton")

    for name in ("information", "warning", "critical", "question"):
        _patch_message_box_static(QtWidgets, name)

    for name in ("getOpenFileName", "getSaveFileName", "getExistingDirectory"):
        _patch_file_dialog_static(QtWidgets, name)

    _qt_hooks_installed = True


configure_from_environment()
