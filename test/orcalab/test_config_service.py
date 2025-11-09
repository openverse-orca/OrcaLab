import pytest

from orcalab.config_service import ConfigService


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

