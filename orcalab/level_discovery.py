import json
import logging
import zipfile
from io import TextIOWrapper
from pathlib import Path
from typing import Dict, List

from orcalab.project_util import get_cache_folder

logger = logging.getLogger(__name__)


def _read_scene_layouts(pak_path: Path) -> List[Dict[str, str]]:
    try:
        with zipfile.ZipFile(pak_path, "r") as pak:
            if "scene_layouts.json" not in pak.namelist():
                return []

            with pak.open("scene_layouts.json") as file:
                text_file = TextIOWrapper(file, encoding="utf-8")
                data = json.load(text_file)
    except zipfile.BadZipFile:
        logger.warning("无效的pak文件: %s", pak_path)
        return []
    except json.JSONDecodeError:
        logger.warning("无法解析场景布局文件: %s", pak_path)
        return []
    except Exception as exc:  # noqa: BLE001
        logger.warning("读取pak文件失败 %s: %s", pak_path, exc)
        return []

    if isinstance(data, list):
        scenes = data
    elif isinstance(data, dict):
        scenes = data.get("scenes", [])
    else:
        scenes = []

    results = []
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        name = scene.get("name")
        path = _to_spawnable_path(scene.get("path"))
        if not path:
            continue
        results.append(
            {
                "name": name or path,
                "path": path,
            }
        )

    return results


def _to_spawnable_path(path: str | None) -> str | None:
    if not path:
        return None
    if path.lower().endswith(".prefab"):
        return path[:-7] + ".spawnable"
    return path


def discover_levels_from_cache() -> List[Dict[str, str]]:
    """扫描缓存目录下的pak文件，收集场景信息"""
    cache_folder = get_cache_folder()
    if not cache_folder.exists():
        logger.info("缓存目录不存在，跳过场景扫描: %s", cache_folder)
        return []

    discovered_levels: List[Dict[str, str]] = []
    seen_paths = set()

    for pak_path in sorted(cache_folder.rglob("*.pak")):
        scenes = _read_scene_layouts(pak_path)
        if not scenes:
            continue

        for scene in scenes:
            path = scene["path"]
            if path in seen_paths:
                continue
            seen_paths.add(path)
            discovered_levels.append(scene)

    return discovered_levels

