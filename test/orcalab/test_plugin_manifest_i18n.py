import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets

from orcalab.i18n import get_language, set_language
from orcalab.plugin_system.plugin_manager_dialog import PluginManagerDialog
from orcalab.plugin_system.plugin_manifest import PluginManifest


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture(autouse=True)
def restore_language():
    previous_language = get_language()
    try:
        yield
    finally:
        set_language(previous_language)


def _write_manifest(tmp_path, content: str) -> PluginManifest:
    manifest_path = tmp_path / "plugin.toml"
    manifest_path.write_text(content, encoding="utf-8")
    return PluginManifest.from_toml(manifest_path)


def test_legacy_description_remains_compatible(tmp_path):
    manifest = _write_manifest(
        tmp_path,
        """
[plugin]
name = "legacy"
version = "1.0.0"
entry = "legacy.plugin:LegacyPlugin"
description = "Legacy description"
""",
    )

    assert manifest.description == "Legacy description"
    assert manifest.localized_descriptions == {}
    assert manifest.get_description("en_US") == "Legacy description"
    assert manifest.get_description("zh_CN") == "Legacy description"


def test_new_locale_field_does_not_shift_legacy_positional_arguments(tmp_path):
    manifest = PluginManifest(
        "positional",
        "1.0.0",
        "positional.plugin:PositionalPlugin",
        "Author",
        "Legacy description",
        "26.1.0",
        ["dependency"],
        ["config.toml"],
        {"menu": ["entry"]},
        "init.sh",
        "uninstall.sh",
        tmp_path,
    )

    assert manifest.description == "Legacy description"
    assert manifest.plugin_dir == tmp_path
    assert manifest.localized_descriptions == {}


def test_legacy_description_can_be_the_english_fallback_for_new_locales(tmp_path):
    manifest = _write_manifest(
        tmp_path,
        """
[plugin]
name = "localized-with-legacy-fallback"
version = "1.0.0"
entry = "localized.plugin:LocalizedPlugin"
description = "English fallback"

[plugin.locales.zh_CN]
description = "中文描述"
""",
    )

    assert manifest.get_description("zh_CN") == "中文描述"
    assert manifest.get_description("en_US") == "English fallback"


def test_localized_description_uses_current_language_then_english(tmp_path):
    manifest = _write_manifest(
        tmp_path,
        """
[plugin]
name = "localized"
version = "1.0.0"
entry = "localized.plugin:LocalizedPlugin"
description = "Legacy English fallback"

[plugin.locales.en_US]
description = "English description"

[plugin.locales.zh_CN]
description = "中文描述"
""",
    )

    assert manifest.get_description("zh_CN") == "中文描述"
    assert manifest.get_description("en_US") == "English description"
    assert manifest.get_description("de_DE") == "English description"

    set_language("zh_CN")
    assert manifest.get_description() == "中文描述"


def test_locale_aliases_and_canonical_keys_are_compatible(tmp_path):
    manifest = _write_manifest(
        tmp_path,
        """
[plugin]
name = "aliases"
version = "1.0.0"
entry = "aliases.plugin:AliasesPlugin"
description = "Legacy fallback"

[plugin.locales.zh_CN]
description = "规范中文"

[plugin.locales.zh-TW]
description = "繁體別名"

[plugin.locales.en-US]
description = "English alias"

[plugin.locales.fr_FR]
description = "Description française"
""",
    )

    assert manifest.get_description("zh-TW") == "规范中文"
    assert manifest.get_description("en") == "English alias"
    assert manifest.get_description("fr_FR") == "Description française"
    assert manifest.get_description("ja_JP") == "English alias"


def test_missing_or_invalid_locales_fall_back_without_breaking_manifest(tmp_path):
    manifest = _write_manifest(
        tmp_path,
        """
[plugin]
name = "invalid-locales"
version = "1.0.0"
entry = "invalid_locales.plugin:InvalidLocalesPlugin"
description = "Legacy fallback"

[plugin.locales.zh_CN]
description = 123

[plugin.locales.en_US]
author = "No description here"
""",
    )

    assert manifest.localized_descriptions == {}
    assert manifest.get_description("zh_CN") == "Legacy fallback"


def test_non_table_locales_and_non_string_legacy_description_are_tolerated(tmp_path):
    manifest = _write_manifest(
        tmp_path,
        """
[plugin]
name = "invalid-description"
version = "1.0.0"
entry = "invalid_description.plugin:InvalidDescriptionPlugin"
description = 123
locales = "not a table"
""",
    )

    assert manifest.description == ""
    assert manifest.localized_descriptions == {}
    assert manifest.get_description("en_US") == ""


def test_plugin_manager_displays_resource_description_without_core_translation(qapp):
    manifest = PluginManifest(
        name="resource-text",
        version="1.0.0",
        entry="resource_text.plugin:ResourceTextPlugin",
        localized_descriptions={"en_US": "关闭"},
    )

    class Registry:
        def is_enabled(self, _plugin_name):
            return False

    class Manager:
        registry = Registry()

        def discover(self):
            return [manifest]

    set_language("en_US")
    dialog = PluginManagerDialog(Manager())
    try:
        table = dialog.findChild(QtWidgets.QTableWidget)
        assert table is not None
        assert table.item(0, 3).text() == "关闭"
    finally:
        dialog.deleteLater()
