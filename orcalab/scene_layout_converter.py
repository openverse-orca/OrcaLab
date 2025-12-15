import argparse
import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import numpy as np
from scipy.spatial.transform import Rotation


logger = logging.getLogger(__name__)


class SceneLayoutConverter:
    """
    Convert Orca Studio ``scene_layouts.json`` payloads to OrcaLab layout files.

    Usage
    -----
    >>> converter = SceneLayoutConverter()
    >>> converter.convert_file("/path/to/scene_layouts.json", "/path/to/output")

    The converter will emit one OrcaLab layout JSON per scene contained in the
    source file. Each generated layout mirrors the hierarchical entity structure
    from the source and normalises names, transforms and asset references to
    match OrcaLab's expectations.
    """

    def __init__(self, layout_version: str = "1.0"):
        self._layout_version = layout_version

    def convert_file(
        self,
        scene_layout_file: str | Path,
        output_dir: str | Path,
        *,
        overwrite: bool = True,
    ) -> List[Path]:
        """
        Convert a ``scene_layouts.json`` file and write one OrcaLab layout per scene.

        Parameters
        ----------
        scene_layout_file:
            Path to the source ``scene_layouts.json`` file.
        output_dir:
            Directory where resulting layout files should be written. The directory
            is created when it does not already exist.
        overwrite:
            Whether to overwrite existing files with the same name.

        Returns
        -------
        List[Path]
            Paths to the generated layout files.
        """
        scenes = self._load_scene_layouts(scene_layout_file)

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        generated_paths: List[Path] = []
        for scene in scenes:
            scene_dict = self.convert_scene(scene)
            filename = self._build_output_filename(scene)
            target = output_path / filename
            if target.exists() and not overwrite:
                raise FileExistsError(f"Target layout file already exists: {target}")

            with target.open("w", encoding="utf-8") as fp:
                json.dump(scene_dict, fp, indent=4, ensure_ascii=False)

            generated_paths.append(target)

        return generated_paths

    def convert_scene(self, scene: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert a single scene dictionary to an OrcaLab layout dictionary.
        """
        registry: dict[str, set[str]] = defaultdict(set)
        root_children: List[Dict[str, Any]] = []

        layout = scene.get("layout")
        if isinstance(layout, dict):
            converted = self._convert_entity(layout, parent_path="/", name_registry=registry)
            if converted:
                root_children.append(converted)
        else:
            logger.warning("Scene missing 'layout' block, generating empty layout for %s", scene)

        root_layout = {
            "version": self._layout_version,
            "name": "root",
            "path": "/",
            "transform": self._identity_transform(),
            "type": "GroupActor",
            "children": root_children,
        }

        return root_layout

    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #

    def _load_scene_layouts(self, scene_layout_file: str | Path) -> List[Dict[str, Any]]:
        path = Path(scene_layout_file)
        with path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)

        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]

        if isinstance(data, dict):
            scenes = data.get("scenes", [])
            return [item for item in scenes if isinstance(item, dict)]

        logger.warning("Unrecognised scene layout payload: %s", type(data).__name__)
        return []

    def _convert_entity(
        self,
        entity: Dict[str, Any],
        *,
        parent_path: str,
        name_registry: dict[str, set[str]],
    ) -> Dict[str, Any] | None:
        raw_name = entity.get("name") or "Group"
        name = self._unique_name(parent_path, raw_name, name_registry)
        path = self._join_path(parent_path, name)
        transform = self._build_transform(entity.get("transform"))

        children: List[Dict[str, Any]] = []

        for child in entity.get("children", []) or []:
            if not isinstance(child, dict):
                continue
            converted_child = self._convert_entity(child, parent_path=path, name_registry=name_registry)
            if converted_child:
                children.append(converted_child)

        for instance in entity.get("instances", []) or []:
            if not isinstance(instance, dict):
                continue
            asset = self._convert_instance(instance, parent_path=path, name_registry=name_registry)
            if asset:
                children.append(asset)

        group_actor = {
            "name": name,
            "path": path,
            "transform": transform,
            "type": "GroupActor",
            "children": children,
        }

        return group_actor

    def _convert_instance(
        self,
        instance: Dict[str, Any],
        *,
        parent_path: str,
        name_registry: dict[str, set[str]],
    ) -> Dict[str, Any] | None:
        prefab_path = instance.get("prefabPath")
        asset_path = self._prefab_to_asset_path(prefab_path)
        if not asset_path:
            logger.warning("Skip instance without valid prefabPath: %s", instance)
            return None

        raw_name = instance.get("name") or Path(prefab_path).stem
        name = self._unique_name(parent_path, raw_name, name_registry)
        path = self._join_path(parent_path, name)
        transform = self._build_transform(instance.get("transform"))

        asset_actor = {
            "name": name,
            "path": path,
            "transform": transform,
            "type": "AssetActor",
            "asset_path": asset_path,
        }

        return asset_actor

    def _unique_name(
        self,
        parent_path: str,
        desired_name: str,
        name_registry: dict[str, set[str]],
    ) -> str:
        base = self._sanitize_name(desired_name)
        if not base:
            base = "Node"

        registry = name_registry[parent_path]
        if base not in registry:
            registry.add(base)
            return base

        suffix = 1
        while True:
            candidate = f"{base}_{suffix}"
            if candidate not in registry:
                registry.add(candidate)
                return candidate
            suffix += 1

    @staticmethod
    def _sanitize_name(name: str) -> str:
        if not isinstance(name, str):
            return ""
        sanitized = re.sub(r"[^0-9A-Za-z_]", "_", name)
        sanitized = re.sub(r"_+", "_", sanitized).strip("_")
        if not sanitized:
            return ""
        if sanitized[0].isdigit():
            sanitized = f"_{sanitized}"
        return sanitized

    @staticmethod
    def _join_path(parent_path: str, name: str) -> str:
        if parent_path == "/":
            return f"/{name}"
        return f"{parent_path}/{name}"

    def _build_transform(self, transform_data: Dict[str, Any] | None) -> Dict[str, Any]:
        if not isinstance(transform_data, dict):
            position = np.zeros(3)
            quaternion = np.array([1.0, 0.0, 0.0, 0.0])
            scale = 1.0
        else:
            position = np.array(transform_data.get("Translate", [0.0, 0.0, 0.0]), dtype=float)
            rotation = np.array(transform_data.get("Rotate", [0.0, 0.0, 0.0]), dtype=float)
            scale = float(transform_data.get("UniformScale", 1.0))
            quaternion = self._euler_to_quaternion(rotation)

        return {
            "position": self._format_array(position),
            "rotation": self._format_array(quaternion),
            "scale": scale,
        }

    @staticmethod
    def _identity_transform() -> Dict[str, Any]:
        return {
            "position": "[0,0,0]",
            "rotation": "[1,0,0,0]",
            "scale": 1.0,
        }

    @staticmethod
    def _format_array(values: Iterable[float]) -> str:
        formatted = ",".join(SceneLayoutConverter._format_number(v) for v in values)
        return f"[{formatted}]"

    @staticmethod
    def _format_number(value: float) -> str:
        if abs(value) < 1e-10:
            value = 0.0
        return f"{value:.10g}"

    @staticmethod
    def _prefab_to_asset_path(prefab_path: str | None) -> str:
        if not prefab_path:
            return ""
        path = prefab_path.replace("\\", "/").strip().lower()
        if path.endswith(".prefab"):
            path = path[:-7]
        return path

    @staticmethod
    def _build_output_filename(scene: Dict[str, Any]) -> str:
        identifier = scene.get("name") or scene.get("path") or "scene"
        sanitized = SceneLayoutConverter._sanitize_name(identifier) or "scene"
        return f"{sanitized}.json"

    @staticmethod
    def _euler_to_quaternion(euler: Sequence[float]) -> np.ndarray:
        try:
            rotation = Rotation.from_euler("xyz", euler, degrees=True)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to convert rotation %s, falling back to identity", euler)
            return np.array([1.0, 0.0, 0.0, 0.0], dtype=float)

        quat_xyzw = rotation.as_quat()
        quaternion = np.array(
            [quat_xyzw[3], quat_xyzw[0], quat_xyzw[1], quat_xyzw[2]],
            dtype=float,
        )
        return quaternion


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert Orca Studio scene_layouts.json to OrcaLab layout files."
    )
    parser.add_argument(
        "scene_layout_file",
        help="Path to the scene_layouts.json to convert.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        dest="output_dir",
        help="Directory to place generated OrcaLab layout files. Defaults to the input file directory.",
    )
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Fail if the output file already exists.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Logging level for console output.",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log_level))

    input_path = Path(args.scene_layout_file).expanduser().resolve()
    if not input_path.exists():
        parser.error(f"Scene layout file does not exist: {input_path}")

    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else input_path.parent
    )

    try:
        converter = SceneLayoutConverter()
        generated = converter.convert_file(
            scene_layout_file=input_path,
            output_dir=output_dir,
            overwrite=not args.no_overwrite,
        )
    except FileExistsError as exc:
        logger.error("%s", exc)
        return 1
    except Exception:
        logger.exception("Failed to convert %s", input_path)
        return 1

    if not generated:
        logger.warning("No scenes found in %s", input_path)
    else:
        logger.info("Generated %d layout file(s):", len(generated))
        for path in generated:
            logger.info("  %s", path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

