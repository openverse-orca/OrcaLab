import tomllib
from pathlib import Path

import pytest

import orcalab.config_service as config_service_module
from orcalab.config_service import ConfigService
from orcalab.i18n import resolve_language


@pytest.fixture
def fresh_config_service():
    original_instance = ConfigService._instance
    ConfigService._instance = None
    try:
        service = ConfigService()
        service.config = {"orcalab": {}}
        yield service
    finally:
        ConfigService._instance = original_instance


def test_normalize_level_item_preserves_metadata(fresh_config_service):
    item = {
        "name": "Kitchen",
        "path": "levels/sample.prefab",
        "scene_layout_file": "/tmp/sample.json",
    }

    result = fresh_config_service._normalize_level_item(item)
    assert result["scene_layout_file"] == "/tmp/sample.json"
    assert result["path"].endswith(".spawnable")


def test_merge_levels_prefers_new_metadata(fresh_config_service):
    fresh_config_service.config["orcalab"]["levels"] = [
        {
            "name": "Kitchen",
            "path": "levels/sample.spawnable",
            "scene_layout_file": "/old/path.json",
        }
    ]

    fresh_config_service.merge_levels(
        [
            {
                "name": "Kitchen",
                "path": "levels/sample.spawnable",
                "scene_layout_file": "/new/path.json",
            }
        ]
    )

    levels = fresh_config_service.levels()
    assert levels[0]["scene_layout_file"] == "/new/path.json"


def test_set_default_layout_file_handles_none(fresh_config_service):
    fresh_config_service.set_default_layout_file("/tmp/default.json")
    assert fresh_config_service.default_layout_file() == "/tmp/default.json"

    fresh_config_service.set_default_layout_file(None)
    assert fresh_config_service.default_layout_file() is None


def test_ui_language_defaults_to_english_before_initialization(fresh_config_service):
    assert fresh_config_service.ui_language() == "en_US"
    assert fresh_config_service.configured_ui_language() is None


@pytest.mark.parametrize("detected_language", ["en_US", "zh_CN"])
def test_ensure_ui_language_detects_and_persists_first_language(
    fresh_config_service, monkeypatch, tmp_path, detected_language
):
    user_config_path = tmp_path / "config.toml"
    fresh_config_service.user_config_path = user_config_path.as_posix()
    monkeypatch.setattr(
        config_service_module,
        "detect_system_language",
        lambda: detected_language,
    )

    assert fresh_config_service.ensure_ui_language() == detected_language
    assert fresh_config_service.ui_language() == detected_language
    assert fresh_config_service.configured_ui_language() == detected_language
    with user_config_path.open("rb") as config_file:
        persisted = tomllib.load(config_file)
    assert persisted["orcalab"]["language"] == detected_language


def test_cli_language_is_temporary_while_first_system_language_is_saved(
    fresh_config_service, monkeypatch, tmp_path
):
    user_config_path = tmp_path / "config.toml"
    fresh_config_service.user_config_path = user_config_path.as_posix()
    monkeypatch.setattr(
        config_service_module, "detect_system_language", lambda: "zh_CN"
    )

    saved_language = fresh_config_service.ensure_ui_language()
    effective_language = resolve_language("en_US", saved_language)

    assert effective_language == "en_US"
    assert fresh_config_service.configured_ui_language() == "zh_CN"
    with user_config_path.open("rb") as config_file:
        persisted = tomllib.load(config_file)
    assert persisted["orcalab"]["language"] == "zh_CN"


def test_configured_ui_language_is_not_reinitialized(
    fresh_config_service, monkeypatch, tmp_path
):
    fresh_config_service.user_config_path = (tmp_path / "config.toml").as_posix()
    fresh_config_service.config["orcalab"]["language"] = "en_US"

    def fail_if_detected():
        raise AssertionError("system language is only used for first initialization")

    monkeypatch.setattr(
        config_service_module, "detect_system_language", fail_if_detected
    )

    assert fresh_config_service.ensure_ui_language() == "en_US"
    assert fresh_config_service.ui_language() == "en_US"
    assert not Path(fresh_config_service.user_config_path).exists()


def test_read_user_ui_language_returns_saved_value(monkeypatch, tmp_path):
    user_config_path = tmp_path / "config.toml"
    user_config_path.write_text(
        '[orcalab]\nlanguage = "zh_CN"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        config_service_module,
        "get_user_config_path",
        lambda: user_config_path.as_posix(),
    )

    assert config_service_module.read_user_ui_language() == "zh_CN"


def test_shared_config_does_not_pin_the_ui_language():
    config_path = Path(__file__).resolve().parents[2] / "orcalab" / "orca.config.toml"
    with config_path.open("rb") as config_file:
        shared_config = tomllib.load(config_file)

    assert "language" not in shared_config["orcalab"]


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        ("zh", "zh_CN"),
        ("en", "en_US"),
        ("unsupported", "en_US"),
    ],
)
def test_set_ui_language_normalizes_and_persists(
    fresh_config_service, tmp_path, requested, expected
):
    user_config_path = tmp_path / "config.toml"
    fresh_config_service.user_config_path = user_config_path.as_posix()

    fresh_config_service.set_ui_language(requested)

    assert fresh_config_service.ui_language() == expected
    with user_config_path.open("rb") as config_file:
        persisted = tomllib.load(config_file)
    assert persisted["orcalab"]["language"] == expected
