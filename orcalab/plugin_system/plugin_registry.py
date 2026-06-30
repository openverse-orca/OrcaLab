from __future__ import annotations

import json
import logging
import pathlib
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class PluginRegistry:
    """插件注册表，持久化记录已安装插件及其启用状态。

    存储位置：<user_folder>/plugins/plugin_registry.json
    """

    def __init__(self, registry_path: pathlib.Path):
        self._path = registry_path
        self._data: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception as e:
                logger.warning("加载插件注册表失败: %s", e)
                self._data = {}
        else:
            self._data = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning("保存插件注册表失败: %s", e)

    def is_enabled(self, plugin_name: str) -> bool:
        entry = self._data.get(plugin_name, {})
        return bool(entry.get("enabled", False))

    def set_enabled(self, plugin_name: str, enabled: bool) -> None:
        entry = self._data.setdefault(plugin_name, {})
        entry["enabled"] = enabled
        self._save()

    def is_installed(self, plugin_name: str) -> bool:
        return plugin_name in self._data

    def register_installed(self, plugin_name: str, version: str, plugin_dir: str) -> None:
        entry = self._data.setdefault(plugin_name, {})
        entry["version"] = version
        entry["plugin_dir"] = plugin_dir
        entry.setdefault("enabled", False)
        self._save()

    def unregister(self, plugin_name: str) -> None:
        self._data.pop(plugin_name, None)
        self._save()

    def list_installed(self) -> List[Dict[str, Any]]:
        result = []
        for name, entry in self._data.items():
            item = {"name": name}
            item.update(entry)
            result.append(item)
        return result
