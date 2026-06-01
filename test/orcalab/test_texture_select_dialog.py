import sys
import unittest
from unittest.mock import MagicMock, patch

from PySide6 import QtWidgets, QtCore

from orcalab.texture_asset_cache import TextureAssetCache


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
        "{UUID-3}:0": "textures/metal.png.streamingimage",
    }
    cache._path_to_uuid = {
        "textures/rock.jpg.streamingimage": "{UUID-1}:0",
        "textures/wood.png.streamingimage": "{UUID-2}:0",
        "textures/metal.png.streamingimage": "{UUID-3}:0",
    }
    cache._ready = True
    return cache


def _make_empty_cache():
    cache = TextureAssetCache()
    cache._ready = True
    return cache


class TestTextureSelectDialog(unittest.TestCase):
    def setUp(self):
        from orcalab.ui.property_edit.texture_select_dialog import (
            TextureSelectDialog,
        )
        self.TextureSelectDialog = TextureSelectDialog

    def test_dialog_shows_all_items(self):
        cache = _make_populated_cache()
        dialog = self.TextureSelectDialog(cache)
        dialog.show()

        self.assertEqual(dialog._list_widget.count(), 3)
        paths = [
            dialog._list_widget.item(i).text()
            for i in range(dialog._list_widget.count())
        ]
        self.assertIn("textures/rock.jpg.streamingimage", paths)
        self.assertIn("textures/wood.png.streamingimage", paths)
        self.assertIn("textures/metal.png.streamingimage", paths)
        self.assertIn("共 3 个纹理", dialog._status_label.text())

        dialog.close()

    def test_dialog_empty_cache(self):
        cache = _make_empty_cache()
        dialog = self.TextureSelectDialog(cache)
        dialog.show()

        self.assertEqual(dialog._list_widget.count(), 0)
        self.assertIn("共 0 个纹理", dialog._status_label.text())

        dialog.close()

    def test_search_filters_items(self):
        cache = _make_populated_cache()
        dialog = self.TextureSelectDialog(cache)
        dialog.show()

        dialog._search_edit.setText("rock")
        self.assertEqual(dialog._list_widget.count(), 1)
        self.assertEqual(
            dialog._list_widget.item(0).text(),
            "textures/rock.jpg.streamingimage",
        )
        self.assertIn("显示 1 / 3 个纹理", dialog._status_label.text())

        dialog.close()

    def test_search_case_insensitive(self):
        cache = _make_populated_cache()
        dialog = self.TextureSelectDialog(cache)
        dialog.show()

        dialog._search_edit.setText("ROCK")
        self.assertEqual(dialog._list_widget.count(), 1)
        self.assertEqual(
            dialog._list_widget.item(0).text(),
            "textures/rock.jpg.streamingimage",
        )

        dialog.close()

    def test_search_no_match(self):
        cache = _make_populated_cache()
        dialog = self.TextureSelectDialog(cache)
        dialog.show()

        dialog._search_edit.setText("nonexistent")
        self.assertEqual(dialog._list_widget.count(), 0)
        self.assertIn("显示 0 / 3 个纹理", dialog._status_label.text())

        dialog.close()

    def test_clear_search_restores_all(self):
        cache = _make_populated_cache()
        dialog = self.TextureSelectDialog(cache)
        dialog.show()

        dialog._search_edit.setText("rock")
        self.assertEqual(dialog._list_widget.count(), 1)

        dialog._search_edit.setText("")
        self.assertEqual(dialog._list_widget.count(), 3)

        dialog.close()

    def test_selection_enables_ok_button(self):
        cache = _make_populated_cache()
        dialog = self.TextureSelectDialog(cache)
        dialog.show()

        self.assertFalse(dialog._ok_button.isEnabled())

        dialog._list_widget.setCurrentRow(0)
        self.assertTrue(dialog._ok_button.isEnabled())
        self.assertEqual(dialog._selected_uuid, "{UUID-1}:0")

        dialog.close()

    def test_accept_returns_selected_uuid(self):
        cache = _make_populated_cache()
        dialog = self.TextureSelectDialog(cache)
        dialog.show()

        dialog._list_widget.setCurrentRow(0)
        dialog._on_accept()

        self.assertEqual(dialog.result(), QtWidgets.QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.selected_uuid(), "{UUID-1}:0")

        dialog.close()

    def test_cancel_returns_rejected(self):
        cache = _make_populated_cache()
        dialog = self.TextureSelectDialog(cache)
        dialog.reject()

        self.assertEqual(dialog.result(), QtWidgets.QDialog.DialogCode.Rejected)

    def test_clear_sets_empty_uuid_and_accepts(self):
        cache = _make_populated_cache()
        dialog = self.TextureSelectDialog(cache)
        dialog.show()

        dialog._list_widget.setCurrentRow(0)
        dialog._on_clear()

        self.assertEqual(dialog.selected_uuid(), "")
        self.assertEqual(dialog.result(), QtWidgets.QDialog.DialogCode.Accepted)

        dialog.close()

    def test_item_data_stores_uuid(self):
        cache = _make_populated_cache()
        dialog = self.TextureSelectDialog(cache)
        dialog.show()

        item = dialog._list_widget.item(0)
        uuid = item.data(QtCore.Qt.ItemDataRole.UserRole)
        self.assertEqual(uuid, "{UUID-1}:0")

        dialog.close()

    def test_selection_changed_updates_selected_uuid(self):
        cache = _make_populated_cache()
        dialog = self.TextureSelectDialog(cache)
        dialog.show()

        dialog._list_widget.setCurrentRow(0)
        self.assertEqual(dialog._selected_uuid, "{UUID-1}:0")

        dialog._list_widget.setCurrentRow(1)
        self.assertEqual(dialog._selected_uuid, "{UUID-2}:0")

        dialog._list_widget.setCurrentRow(-1)
        self.assertIsNone(dialog._selected_uuid)
        self.assertFalse(dialog._ok_button.isEnabled())

        dialog.close()

    def test_dialog_is_modal(self):
        cache = _make_populated_cache()
        dialog = self.TextureSelectDialog(cache)
        self.assertTrue(dialog.isModal())

    def test_dialog_window_title(self):
        cache = _make_populated_cache()
        dialog = self.TextureSelectDialog(cache)
        self.assertEqual(dialog.windowTitle(), "选择纹理")


if __name__ == "__main__":
    unittest.main()