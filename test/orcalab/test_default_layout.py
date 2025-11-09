import json
from pathlib import Path

import pytest

from orcalab import default_layout

def test_prefab_to_spawnable():
    assert default_layout.prefab_to_spawnable("assets/foo.prefab") == "assets/foo.spawnable"
    assert default_layout.prefab_to_spawnable("assets/foo.spawnable") == "assets/foo.spawnable"
    assert default_layout.prefab_to_spawnable(None) is None


def test_prepare_default_layout_generates_file(tmp_path, monkeypatch):
    layout_data = {
        "scenes": [
            {
                "name": "MyScene",
                "path": "levels/foo.prefab",
                "layout": {
                    "name": "Level",
                    "transform": {
                        "Translate": [0.0, 0.0, 0.0],
                        "Rotate": [0.0, 0.0, 0.0],
                        "UniformScale": 1.0,
                    },
                },
            }
        ]
    }

    scene_layout_file = tmp_path / "scene_layouts.json"
    scene_layout_file.write_text(json.dumps(layout_data), encoding="utf-8")

    monkeypatch.setattr(default_layout, "get_user_tmp_folder", lambda: tmp_path)

    selected_level = {
        "name": "MyScene",
        "path": "levels/foo.spawnable",
        "scene_layout_file": str(scene_layout_file),
    }

    output_path = default_layout.prepare_default_layout(selected_level)
    assert output_path is not None
    output_file = Path(output_path)
    assert output_file.exists()

    data = json.loads(output_file.read_text(encoding="utf-8"))
    assert data["name"] == "root"
    assert any(child["type"] == "GroupActor" for child in data["children"])

