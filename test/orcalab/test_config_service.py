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


def test_raytracing_enabled_defaults_to_true(fresh_config_service):
    assert fresh_config_service.raytracing_enabled() is True


def test_set_raytracing_enabled_updates_in_memory(fresh_config_service, monkeypatch):
    # set_raytracing_enabled 会调用 set_user_config 写用户配置文件，
    # 测试环境中没有该路径，patch 为空操作以仅验证内存态更新
    monkeypatch.setattr(fresh_config_service, "set_user_config", lambda *args, **kwargs: None)
    fresh_config_service.set_raytracing_enabled(False)
    assert fresh_config_service.raytracing_enabled() is False

