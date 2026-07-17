import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets

from orcalab.actor_property import ActorProperty, ActorPropertyType
from orcalab.i18n import get_language, set_language
from orcalab.ui.property_edit.base_property_edit import PropertyEditContext
from orcalab.ui.property_edit.combo_property_edit import ComboBoxPropertyEdit
from orcalab.ui.property_edit.string_property_edit import StringPropertyEdit


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture(autouse=True)
def english_language():
    previous_language = get_language()
    set_language("en_US")
    try:
        yield
    finally:
        set_language(previous_language)


def _make_context(prop: ActorProperty) -> PropertyEditContext:
    return PropertyEditContext(
        actor=MagicMock(),
        actor_path=MagicMock(),
        group=MagicMock(),
        prop=prop,
        key=MagicMock(),
    )


def _make_enum_property(
    property_type: ActorPropertyType,
    value: str | int,
    options: list[str],
) -> ActorProperty:
    prop = ActorProperty(
        name="mode",
        display_name="Mode",
        type=property_type,
        value=value,
        original_value=value,
    )
    prop.set_enum_values(options)
    return prop


def test_enum_editor_translates_labels_but_writes_raw_value(qapp):
    prop = _make_enum_property(
        ActorPropertyType.ENUM,
        "自定义",
        ["自定义", "钢铁"],
    )
    context = _make_context(prop)
    request_bus = MagicMock()
    request = object()
    request_bus.set_property.return_value = request

    with (
        patch(
            "orcalab.ui.property_edit.combo_property_edit.SceneEditRequestBus",
            return_value=request_bus,
        ),
        patch(
            "orcalab.ui.property_edit.combo_property_edit.asyncio.create_task"
        ) as create_task,
    ):
        widget = ComboBoxPropertyEdit(None, context, 100)
        combo = widget.findChild(QtWidgets.QComboBox)

        assert combo is not None
        assert combo.currentText() == "Custom"
        assert combo.currentData() == "自定义"

        combo.setCurrentIndex(1)

        assert combo.currentText() == "Steel"
        assert combo.currentData() == "钢铁"
        assert prop.value() == "钢铁"
        request_bus.set_property.assert_called_once_with(
            property_key=context.key,
            value="钢铁",
            undo=True,
            old_value="自定义",
            source="ui",
        )
        create_task.assert_called_once_with(request)

        widget.deleteLater()


def test_enum_editor_programmatic_update_uses_raw_value(qapp):
    prop = _make_enum_property(
        ActorPropertyType.ENUM,
        "自定义",
        ["自定义", "钢铁"],
    )
    context = _make_context(prop)
    request_bus = MagicMock()

    with patch(
        "orcalab.ui.property_edit.combo_property_edit.SceneEditRequestBus",
        return_value=request_bus,
    ):
        widget = ComboBoxPropertyEdit(None, context, 100)
        combo = widget.findChild(QtWidgets.QComboBox)

        widget.set_value("钢铁")

        assert combo is not None
        assert combo.currentText() == "Steel"
        assert combo.currentData() == "钢铁"
        assert prop.value() == "钢铁"
        request_bus.set_property.assert_not_called()

        widget.deleteLater()


def test_integer_enum_editor_keeps_integer_raw_value(qapp):
    prop = _make_enum_property(
        ActorPropertyType.INTEGER,
        0,
        ["Low", "High"],
    )
    context = _make_context(prop)
    request_bus = MagicMock()
    request_bus.set_property.return_value = object()

    with (
        patch(
            "orcalab.ui.property_edit.combo_property_edit.SceneEditRequestBus",
            return_value=request_bus,
        ),
        patch(
            "orcalab.ui.property_edit.combo_property_edit.asyncio.create_task"
        ),
    ):
        widget = ComboBoxPropertyEdit(None, context, 100)
        combo = widget.findChild(QtWidgets.QComboBox)

        assert combo is not None
        assert combo.currentData() == 0

        combo.setCurrentIndex(1)

        assert combo.currentText() == "High"
        assert combo.currentData() == 1
        assert prop.value() == 1
        request_bus.set_property.assert_called_once_with(
            property_key=context.key,
            value=1,
            undo=True,
            old_value=0,
            source="ui",
        )

        widget.deleteLater()


def test_read_only_status_translates_display_but_keeps_raw_value(qapp):
    prop = ActorProperty(
        name="boundingBox",
        display_name="Bounding Box",
        type=ActorPropertyType.STRING,
        value="未加载",
        original_value="未加载",
    )
    prop.set_read_only(True)
    context = _make_context(prop)
    widget = StringPropertyEdit(None, context, 100)
    editor = widget.findChild(QtWidgets.QLineEdit)

    assert editor is not None
    assert editor.text() == "Not Loaded"
    assert prop.value() == "未加载"

    widget.set_value("未加载")

    assert editor.text() == "Not Loaded"
    assert prop.value() == "未加载"

    widget.deleteLater()


def test_editable_string_that_matches_status_is_not_translated(qapp):
    prop = ActorProperty(
        name="name",
        display_name="Name",
        type=ActorPropertyType.STRING,
        value="未加载",
        original_value="未加载",
    )
    context = _make_context(prop)
    widget = StringPropertyEdit(None, context, 100)
    editor = widget.findChild(QtWidgets.QLineEdit)

    assert editor is not None
    assert editor.text() == "未加载"
    assert prop.value() == "未加载"

    widget.deleteLater()
