import os
import re
import tomllib

import pytest
from PySide6 import QtWidgets

import orcalab.config_service as config_service_module
from orcalab.config_service import ConfigService
from orcalab.i18n import get_language, install_qt_translation_hooks, set_language
from orcalab.setting.settings_dialog import SettingsDialog

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


_HAN_RE = re.compile(r"[\u3400-\u9fff]")


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.fixture
def language_config(tmp_path):
    original_instance = ConfigService._instance
    ConfigService._instance = None
    try:
        service = ConfigService()
        service.config = {"orcalab": {"language": "zh_CN"}}
        service.user_config_path = (tmp_path / "config.toml").as_posix()
        yield service
    finally:
        ConfigService._instance = original_instance


def test_language_setting_loads_translates_and_persists(qapp, language_config):
    previous_language = get_language()
    set_language("en_US")
    install_qt_translation_hooks()
    dialog = SettingsDialog()

    try:
        assert dialog.windowTitle() == "Settings"
        assert dialog.language_combo.currentData() == "zh_CN"
        assert {
            dialog.language_combo.itemData(index)
            for index in range(dialog.language_combo.count())
        } == {"en_US", "zh_CN"}
        assert all(
            not _HAN_RE.search(dialog.language_combo.itemText(index))
            for index in range(dialog.language_combo.count())
        )

        dialog.language_combo.setCurrentIndex(
            dialog.language_combo.findData("en_US")
        )
        dialog.accept()

        assert language_config.ui_language() == "en_US"
        with open(language_config.user_config_path, "rb") as config_file:
            persisted = tomllib.load(config_file)
        assert persisted["orcalab"]["language"] == "en_US"
    finally:
        dialog.deleteLater()
        set_language(previous_language)


def test_default_english_setting_can_switch_to_chinese(qapp, language_config):
    previous_language = get_language()
    language_config.config["orcalab"]["language"] = "en_US"
    set_language(language_config.ui_language())
    install_qt_translation_hooks()
    dialog = SettingsDialog()
    recreated_dialog = None

    try:
        assert dialog.windowTitle() == "Settings"
        assert dialog.language_combo.currentData() == "en_US"

        dialog.language_combo.setCurrentIndex(
            dialog.language_combo.findData("zh_CN")
        )
        dialog.accept()

        assert language_config.ui_language() == "zh_CN"
        with open(language_config.user_config_path, "rb") as config_file:
            persisted = tomllib.load(config_file)
        assert persisted["orcalab"]["language"] == "zh_CN"

        set_language(language_config.ui_language())
        recreated_dialog = SettingsDialog()
        assert recreated_dialog.windowTitle() == "设置"
        assert recreated_dialog.language_combo.currentData() == "zh_CN"
        assert [
            recreated_dialog.language_combo.itemText(index)
            for index in range(recreated_dialog.language_combo.count())
        ] == ["英语", "简体中文"]
    finally:
        dialog.deleteLater()
        if recreated_dialog is not None:
            recreated_dialog.deleteLater()
        set_language(previous_language)


def test_language_setting_uses_first_system_language_and_persists_it(
    qapp, language_config, monkeypatch
):
    previous_language = get_language()
    language_config.config = {"orcalab": {}}
    monkeypatch.setattr(
        config_service_module, "detect_system_language", lambda: "zh_CN"
    )
    initialized_language = language_config.ensure_ui_language()
    set_language(initialized_language)
    install_qt_translation_hooks()
    dialog = SettingsDialog()

    try:
        assert language_config.configured_ui_language() == "zh_CN"
        with open(language_config.user_config_path, "rb") as config_file:
            persisted = tomllib.load(config_file)
        assert persisted["orcalab"]["language"] == "zh_CN"
        assert dialog.windowTitle() == "设置"
        assert dialog.language_combo.currentData() == "zh_CN"
    finally:
        dialog.deleteLater()
        set_language(previous_language)
