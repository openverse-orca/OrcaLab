from __future__ import annotations

import pathlib
import sys
from dataclasses import dataclass, field
from typing import Dict, List

from orcalab.i18n import get_language, tr

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def _canonical_locale_key(locale_name: str) -> str:
    """Normalize supported locale aliases without treating unknown locales as English."""
    value = locale_name.strip().replace("-", "_")
    normalized = value.lower()
    primary_language = normalized.split("_", 1)[0]

    if primary_language == "en" or normalized == "english":
        return "en_US"
    if primary_language == "zh" or normalized in {
        "cn",
        "chinese",
        "simpchinese",
        "simplified_chinese",
    }:
        return "zh_CN"
    return normalized


def _localized_descriptions(plugin_section: dict) -> Dict[str, str]:
    locales = plugin_section.get("locales", {})
    if not isinstance(locales, dict):
        return {}

    descriptions: Dict[str, str] = {}
    priorities: Dict[str, int] = {}
    for locale_name, locale_data in locales.items():
        if not isinstance(locale_name, str) or not isinstance(locale_data, dict):
            continue

        description = locale_data.get("description")
        if not isinstance(description, str) or not description.strip():
            continue

        locale_key = _canonical_locale_key(locale_name)
        if not locale_key:
            continue

        # If aliases collide, prefer the canonical spelling regardless of TOML order.
        priority = int(locale_name == locale_key)
        if locale_key not in descriptions or priority > priorities[locale_key]:
            descriptions[locale_key] = description
            priorities[locale_key] = priority

    return descriptions


@dataclass
class PluginManifest:
    """插件清单，对应 plugin.toml 的解析结果。"""

    name: str
    version: str
    entry: str
    author: str = ""
    description: str = ""
    min_orcalab_version: str = ""
    python_dependencies: List[str] = field(default_factory=list)
    config_files: List[str] = field(default_factory=list)
    extensions: Dict[str, List[str]] = field(default_factory=dict)
    init_script: str = ""
    uninstall_script: str = ""
    plugin_dir: pathlib.Path = field(default_factory=lambda: pathlib.Path())
    localized_descriptions: Dict[str, str] = field(default_factory=dict, kw_only=True)

    def get_description(self, language: str | None = None) -> str:
        """Return the plugin description for the requested or current UI language."""
        locale_key = _canonical_locale_key(language if language is not None else get_language())
        return (
            self.localized_descriptions.get(locale_key)
            or self.localized_descriptions.get("en_US")
            or self.description
            or ""
        )

    @property
    def init_script_path(self) -> pathlib.Path:
        return self.plugin_dir / self.init_script if self.init_script else self.plugin_dir / "init.sh"

    @property
    def uninstall_script_path(self) -> pathlib.Path:
        """卸载脚本路径（默认 uninstall.sh，可能不存在）。"""
        return self.plugin_dir / (self.uninstall_script or "uninstall.sh")

    @property
    def has_uninstall_script(self) -> bool:
        return self.uninstall_script_path.is_file()

    @property
    def requirements_path(self) -> pathlib.Path:
        """requirements.txt 路径（可能不存在）。"""
        return self.plugin_dir / "requirements.txt"

    @property
    def has_requirements_file(self) -> bool:
        return self.requirements_path.is_file()

    def get_config_file_paths(self) -> List[pathlib.Path]:
        """返回所有存在的配置文件路径。"""
        paths = []
        for rel in self.config_files:
            full = self.plugin_dir / rel
            if full.is_file():
                paths.append(full)
        return paths

    @classmethod
    def from_toml(cls, toml_path: pathlib.Path) -> "PluginManifest":
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)

        plugin_section = data.get("plugin", {})
        name = plugin_section.get("name", "")
        version = plugin_section.get("version", "")
        entry = plugin_section.get("entry", "")

        if not name:
            raise ValueError(
                tr("plugin.toml 缺少 [plugin].name: {path}", path=toml_path)
            )
        if not version:
            raise ValueError(
                tr("plugin.toml 缺少 [plugin].version: {path}", path=toml_path)
            )
        if not entry or ":" not in entry:
            raise ValueError(
                tr(
                    "plugin.toml [plugin].entry 必须为 "
                    "'module.path:ClassName' 格式: {path}",
                    path=toml_path,
                )
            )

        deps_section = plugin_section.get("dependencies", {}) or {}
        python_deps = list(deps_section.get("python", []))

        config_files = list(plugin_section.get("config_files", []))

        extensions = plugin_section.get("extensions", {}) or {}

        description = plugin_section.get("description", "")
        if not isinstance(description, str):
            description = ""

        return cls(
            name=name,
            version=version,
            entry=entry,
            author=plugin_section.get("author", ""),
            description=description,
            min_orcalab_version=plugin_section.get("min_orcalab_version", ""),
            python_dependencies=python_deps,
            config_files=config_files,
            extensions=extensions,
            init_script=plugin_section.get("init_script", "init.sh"),
            uninstall_script=plugin_section.get("uninstall_script", "uninstall.sh"),
            plugin_dir=toml_path.parent,
            localized_descriptions=_localized_descriptions(plugin_section),
        )
