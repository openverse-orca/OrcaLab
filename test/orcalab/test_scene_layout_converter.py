import ast
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from orcalab.scene_layout_converter import SceneLayoutConverter


def _parse_array(text: str) -> np.ndarray:
    return np.array(ast.literal_eval(text), dtype=float)


def test_convert_scene_produces_group_and_asset_structure():
    converter = SceneLayoutConverter()

    scene = {
        "name": "Kitchen Night",
        "layout": {
            "name": "Root Entity",
            "transform": {
                "Translate": [1.0, 2.0, 3.0],
                "Rotate": [0.0, 90.0, 0.0],
                "UniformScale": 2.0,
            },
            "instances": [
                {
                    "name": "Table",
                    "prefabPath": "Assets/MyProject/Prop/Table.prefab",
                    "transform": {
                        "Translate": [0.0, 0.0, 0.0],
                        "Rotate": [0.0, 0.0, 180.0],
                        "UniformScale": 1.0,
                    },
                }
            ],
            "children": [
                {
                    "name": "Static Object",
                    "transform": {
                        "Translate": [0.5, 1.5, -0.5],
                        "Rotate": [10.0, 20.0, 30.0],
                        "UniformScale": 0.5,
                    },
                    "instances": [
                        {
                            "name": "Cup",
                            "prefabPath": "Assets/MyProject/Prop/Cup.prefab",
                            "transform": {
                                "Translate": [1.0, 0.0, 0.0],
                                "Rotate": [0.0, 0.0, 0.0],
                                "UniformScale": 1.0,
                            },
                        },
                        {
                            "name": "Cup",
                            "prefabPath": "Assets/MyProject/Prop/Cup.prefab",
                            "transform": {
                                "Translate": [2.0, 0.0, 0.0],
                                "Rotate": [0.0, 45.0, 0.0],
                                "UniformScale": 1.0,
                            },
                        },
                    ],
                }
            ],
        },
    }

    result = converter.convert_scene(scene)

    assert result["name"] == "root"
    assert result["path"] == "/"
    assert result["type"] == "GroupActor"
    assert result["children"]

    root_entity = result["children"][0]
    assert root_entity["name"] == "Root_Entity"
    assert root_entity["path"] == "/Root_Entity"
    assert root_entity["type"] == "GroupActor"
    np.testing.assert_allclose(
        _parse_array(root_entity["transform"]["position"]),
        np.array([1.0, 2.0, 3.0]),
    )
    expected_root_quat = Rotation.from_euler("xyz", [0.0, 90.0, 0.0], degrees=True).as_quat()
    expected_root_quat = np.array(
        [expected_root_quat[3], expected_root_quat[0], expected_root_quat[1], expected_root_quat[2]]
    )
    np.testing.assert_allclose(
        _parse_array(root_entity["transform"]["rotation"]),
        expected_root_quat,
        atol=1e-6,
    )
    assert root_entity["transform"]["scale"] == 2.0

    table_actor = next(child for child in root_entity["children"] if child["name"] == "Table")
    assert table_actor["type"] == "AssetActor"
    assert table_actor["asset_path"] == "assets/myproject/prop/table"
    expected_table_quat = Rotation.from_euler("xyz", [0.0, 0.0, 180.0], degrees=True).as_quat()
    expected_table_quat = np.array(
        [expected_table_quat[3], expected_table_quat[0], expected_table_quat[1], expected_table_quat[2]]
    )
    np.testing.assert_allclose(
        _parse_array(table_actor["transform"]["rotation"]),
        expected_table_quat,
        atol=1e-6,
    )

    static_group = next(child for child in root_entity["children"] if child["name"] == "Static_Object")
    assert static_group["type"] == "GroupActor"
    assert len(static_group["children"]) == 2

    first_cup, second_cup = static_group["children"]
    assert first_cup["name"] == "Cup"
    assert second_cup["name"] == "Cup_1"


def test_convert_file_emits_layouts(tmp_path):
    converter = SceneLayoutConverter()
    scene = {
        "name": "Kitchen Night",
        "layout": {
            "name": "Level",
            "transform": {
                "Translate": [0.0, 0.0, 0.0],
                "Rotate": [0.0, 0.0, 0.0],
                "UniformScale": 1.0,
            },
        },
    }

    payload_path = tmp_path / "scene_layouts.json"
    payload_path.write_text(json.dumps({"scenes": [scene]}), encoding="utf-8")

    outputs = converter.convert_file(payload_path, tmp_path)
    assert len(outputs) == 1
    expected_output = tmp_path / "Kitchen_Night.json"
    assert outputs[0] == expected_output
    assert expected_output.exists()

    data = json.loads(expected_output.read_text(encoding="utf-8"))
    assert data["name"] == "root"
    assert data["children"][0]["name"] == "Level"

