import json
import logging
from pathlib import Path
from typing import Dict

from orcalab.project_util import get_user_tmp_folder
from orcalab.scene_layout_converter import SceneLayoutConverter


logger = logging.getLogger(__name__)


def prefab_to_spawnable(path: str | None) -> str | None:
    if not path:
        return None
    lowered = path.lower()
    if lowered.endswith(".prefab"):
        return path[: -len(".prefab")] + ".spawnable"
    return path


def prepare_default_layout(selected_level: Dict[str, str]) -> str | None:
    scene_layout_file = selected_level.get("scene_layout_file")
    spawnable_path = selected_level.get("path")

    if not scene_layout_file or not spawnable_path:
        logger.warning("所选场景缺少必要的布局信息，无法生成默认布局。")
        return None

    layout_path = Path(scene_layout_file)
    if not layout_path.exists():
        logger.warning("场景布局文件不存在: %s", layout_path)
        return None

    try:
        with layout_path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
    except Exception as exc:  # noqa: BLE001
        logger.warning("读取场景布局文件失败 %s: %s", layout_path, exc)
        return None

    scenes = []
    if isinstance(data, dict):
        scenes = data.get("scenes", [])
    elif isinstance(data, list):
        scenes = data

    if not isinstance(scenes, list):
        logger.warning("场景布局文件格式不正确: %s", layout_path)
        return None

    target_scene = None
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        scene_path = prefab_to_spawnable(scene.get("path"))
        if scene_path and scene_path.lower() == str(spawnable_path).lower():
            target_scene = scene
            break

    if target_scene is None:
        logger.warning("未在 %s 中找到匹配场景，spawnable: %s", layout_path, spawnable_path)
        return None

    converter = SceneLayoutConverter()
    try:
        layout_dict = converter.convert_scene(target_scene)
    except Exception as exc:  # noqa: BLE001
        logger.exception("转换默认布局失败: %s", exc)
        return None

    output_dir = get_user_tmp_folder()
    output_path = output_dir / "default_layout.json"
    try:
        with output_path.open("w", encoding="utf-8") as fp:
            json.dump(layout_dict, fp, ensure_ascii=False, indent=4)
    except Exception as exc:  # noqa: BLE001
        logger.warning("写入默认布局文件失败 %s: %s", output_path, exc)
        return None

    return str(output_path)

