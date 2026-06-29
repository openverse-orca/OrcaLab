import sys
import unittest
from unittest.mock import MagicMock, patch

from PySide6 import QtWidgets, QtCore

from orcalab.texture_asset_cache import TextureAssetCache
from orcalab.actor_property import ActorProperty, ActorPropertyType


def setUpModule():
    app = QtWidgets.QApplication.instance()
    if app is None:
        global _qapp
        _qapp = QtWidgets.QApplication(sys.argv)


def tearDownModule():
    global _qapp
    if _qapp is not None:
        _qapp.quit()
        _qapp = None


_qapp = None


def _make_populated_cache():
    cache = TextureAssetCache()
    cache._uuid_to_path = {
        "{UUID-1}:0": "textures/rock.jpg.streamingimage",
        "{UUID-2}:0": "textures/wood.png.streamingimage",
    }
    cache._path_to_uuid = {
        "textures/rock.jpg.streamingimage": "{UUID-1}:0",
        "textures/wood.png.streamingimage": "{UUID-2}:0",
    }
    cache._ready = True
    return cache


def _make_empty_cache():
    cache = TextureAssetCache()
    cache._ready = True
    return cache


def _make_prop():
    return ActorProperty("baseColor.textureMap", "Base Color Texture", ActorPropertyType.ASSET, "")


def _make_mock_context(prop):
    from orcalab.ui.property_edit.base_property_edit import PropertyEditContext
    context = MagicMock(spec=PropertyEditContext)
    context.prop = prop
    context.actor = MagicMock()
    context.actor_path = MagicMock()
    context.group = MagicMock()
    context.key = MagicMock()
    return context


class TestTexturePickerPropertyEdit(unittest.TestCase):
    def setUp(self):
        from orcalab.ui.property_edit.texture_picker_property_edit import (
            TexturePickerPropertyEdit,
        )
        self.TexturePickerPropertyEdit = TexturePickerPropertyEdit

    def test_initial_display_empty_value(self):
        cache = _make_empty_cache()
        prop = _make_prop()
        context = _make_mock_context(prop)

        widget = self.TexturePickerPropertyEdit(
            parent=None,
            context=context,
            label_width=100,
            cache=cache,
        )

        self.assertEqual(widget._path_edit.text(), "")

    def test_display_with_valid_uuid(self):
        cache = _make_populated_cache()
        prop = _make_prop()
        prop.set_value("{UUID-1}:0")
        context = _make_mock_context(prop)

        widget = self.TexturePickerPropertyEdit(
            parent=None,
            context=context,
            label_width=100,
            cache=cache,
        )

        self.assertEqual(widget._path_edit.text(), "textures/rock.jpg.streamingimage")

    @patch("orcalab.ui.property_edit.texture_picker_property_edit.ThemeService")
    def test_display_with_unknown_uuid(self, mock_theme_cls):
        mock_theme = MagicMock()
        mock_theme.get_color_hex.return_value = "#888888"
        mock_theme_cls.return_value = mock_theme

        cache = _make_empty_cache()
        prop = _make_prop()
        prop.set_value("{UNKNOWN-UUID}:0")
        context = _make_mock_context(prop)

        widget = self.TexturePickerPropertyEdit(
            parent=None,
            context=context,
            label_width=100,
            cache=cache,
        )

        self.assertEqual(widget._path_edit.text(), "{UNKNOWN-UUID}:0")
        self.assertIn("color", widget._path_edit.styleSheet())

    def test_set_value_updates_display(self):
        cache = _make_populated_cache()
        prop = _make_prop()
        context = _make_mock_context(prop)

        widget = self.TexturePickerPropertyEdit(
            parent=None,
            context=context,
            label_width=100,
            cache=cache,
        )

        widget.set_value("{UUID-2}:0")

        self.assertEqual(prop.value(), "{UUID-2}:0")
        self.assertEqual(widget._path_edit.text(), "textures/wood.png.streamingimage")

    def test_set_value_clears_display(self):
        cache = _make_populated_cache()
        prop = _make_prop()
        prop.set_value("{UUID-1}:0")
        context = _make_mock_context(prop)

        widget = self.TexturePickerPropertyEdit(
            parent=None,
            context=context,
            label_width=100,
            cache=cache,
        )

        widget.set_value("")

        self.assertEqual(prop.value(), "")
        self.assertEqual(widget._path_edit.text(), "")

    def test_read_only_disables_pick_button(self):
        cache = _make_populated_cache()
        prop = _make_prop()
        context = _make_mock_context(prop)

        widget = self.TexturePickerPropertyEdit(
            parent=None,
            context=context,
            label_width=100,
            cache=cache,
        )

        self.assertTrue(widget._pick_button.isEnabled())

        widget.set_read_only(True)
        self.assertFalse(widget._pick_button.isEnabled())

        widget.set_read_only(False)
        self.assertTrue(widget._pick_button.isEnabled())

    def test_pick_button_exists(self):
        cache = _make_populated_cache()
        prop = _make_prop()
        context = _make_mock_context(prop)

        widget = self.TexturePickerPropertyEdit(
            parent=None,
            context=context,
            label_width=100,
            cache=cache,
        )

        self.assertIsNotNone(widget._pick_button)
        self.assertEqual(widget._pick_button.text(), "\u2022\u2022\u2022")

    def test_path_edit_is_read_only(self):
        cache = _make_populated_cache()
        prop = _make_prop()
        context = _make_mock_context(prop)

        widget = self.TexturePickerPropertyEdit(
            parent=None,
            context=context,
            label_width=100,
            cache=cache,
        )

        self.assertTrue(widget._path_edit.isReadOnly())
        self.assertEqual(
            widget._path_edit.alignment(),
            QtCore.Qt.AlignmentFlag.AlignRight,
        )

    def test_click_pick_opens_dialog(self):
        cache = _make_populated_cache()
        prop = _make_prop()
        context = _make_mock_context(prop)

        widget = self.TexturePickerPropertyEdit(
            parent=None,
            context=context,
            label_width=100,
            cache=cache,
        )

        with patch(
            "orcalab.ui.property_edit.texture_select_dialog.TextureSelectDialog"
        ) as mock_dialog_cls:
            mock_dialog = MagicMock()
            mock_dialog.exec.return_value = QtWidgets.QDialog.DialogCode.Rejected
            mock_dialog_cls.return_value = mock_dialog

            widget._pick_button.click()

            mock_dialog_cls.assert_called_once_with(cache, widget.window())
            mock_dialog.exec.assert_called_once()

    def test_click_pick_and_select_updates_property(self):
        cache = _make_populated_cache()
        prop = _make_prop()
        context = _make_mock_context(prop)

        widget = self.TexturePickerPropertyEdit(
            parent=None,
            context=context,
            label_width=100,
            cache=cache,
        )

        with patch(
            "orcalab.ui.property_edit.texture_select_dialog.TextureSelectDialog"
        ) as mock_dialog_cls:
            mock_dialog = MagicMock()
            mock_dialog.exec.return_value = QtWidgets.QDialog.DialogCode.Accepted
            mock_dialog.selected_uuid.return_value = "{UUID-2}:0"
            mock_dialog_cls.return_value = mock_dialog

            with patch.object(widget, "_do_set_value") as mock_do_set:
                widget._pick_button.click()
                mock_do_set.assert_called_once_with("{UUID-2}:0", undo=True)

            self.assertEqual(widget._path_edit.text(), "textures/wood.png.streamingimage")

    def test_click_pick_cancel_does_not_change_property(self):
        cache = _make_populated_cache()
        prop = _make_prop()
        prop.set_value("{UUID-1}:0")
        context = _make_mock_context(prop)

        widget = self.TexturePickerPropertyEdit(
            parent=None,
            context=context,
            label_width=100,
            cache=cache,
        )

        with patch(
            "orcalab.ui.property_edit.texture_select_dialog.TextureSelectDialog"
        ) as mock_dialog_cls:
            mock_dialog = MagicMock()
            mock_dialog.exec.return_value = QtWidgets.QDialog.DialogCode.Rejected
            mock_dialog_cls.return_value = mock_dialog

            widget._pick_button.click()

            self.assertEqual(prop.value(), "{UUID-1}:0")
            self.assertEqual(widget._path_edit.text(), "textures/rock.jpg.streamingimage")

    def test_label_shows_display_name(self):
        cache = _make_populated_cache()
        prop = _make_prop()
        context = _make_mock_context(prop)

        widget = self.TexturePickerPropertyEdit(
            parent=None,
            context=context,
            label_width=100,
            cache=cache,
        )

        labels = widget.findChildren(QtWidgets.QLabel)
        display_names = [lbl.text() for lbl in labels if lbl.text()]
        self.assertIn("Base Color Texture", display_names)


if __name__ == "__main__":
    unittest.main()