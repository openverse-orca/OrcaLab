from __future__ import annotations

import importlib
import logging
import pathlib
import sys
import traceback
from typing import Dict, List, Optional

from orcalab.plugin_system.plugin_base import PluginBase
from orcalab.plugin_system.plugin_context import PluginContext
from orcalab.plugin_system.plugin_manifest import PluginManifest
from orcalab.plugin_system.plugin_registry import PluginRegistry

logger = logging.getLogger(__name__)

PLUGIN_MANIFEST_FILENAME = "plugin.toml"


def get_plugins_root() -> pathlib.Path:
    """获取插件安装根目录：<user_folder>/plugins/installed"""
    from orcalab.project_util import get_user_folder

    root = get_user_folder() / "plugins" / "installed"
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_plugin_registry_path() -> pathlib.Path:
    from orcalab.project_util import get_user_folder

    return get_user_folder() / "plugins" / "plugin_registry.json"


class PluginManager:
    """插件管理器：发现、加载、卸载插件，管理生命周期。

    设计要点：
    - 单个插件加载/卸载失败不影响其他插件和宿主（故障隔离）
    - 加载前将插件目录加入 sys.path，使 entry 中的模块路径可导入
    - 卸载时断开 Event Bus 连接由插件 on_unload 自行负责
    """

    def __init__(self, context: PluginContext):
        self._context = context
        self._plugins: Dict[str, PluginBase] = {}
        self._manifests: Dict[str, PluginManifest] = {}
        self._load_errors: Dict[str, str] = {}
        self._registry = PluginRegistry(get_plugin_registry_path())

    @property
    def registry(self) -> PluginRegistry:
        return self._registry

    def discover(self) -> List[PluginManifest]:
        """扫描插件根目录下所有含 plugin.toml 的子目录。"""
        root = get_plugins_root()
        manifests: List[PluginManifest] = []
        if not root.exists():
            return manifests

        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            toml_path = child / PLUGIN_MANIFEST_FILENAME
            if not toml_path.exists():
                continue
            try:
                manifest = PluginManifest.from_toml(toml_path)
                manifests.append(manifest)
            except Exception as e:
                logger.error("解析插件清单失败 %s: %s", toml_path, e)
        return manifests

    def load_enabled(self) -> None:
        """加载注册表中标记为 enabled 的所有插件。"""
        self._load_errors.clear()
        manifests = self.discover()
        loaded_count = 0
        for manifest in manifests:
            if not self._registry.is_enabled(manifest.name):
                logger.debug("插件 %s 未启用，跳过", manifest.name)
                continue
            if self._load(manifest):
                loaded_count += 1
        logger.info("插件加载完成，共加载 %d 个插件", loaded_count)

    def get_load_errors(self) -> Dict[str, str]:
        """获取本次加载失败的插件及其错误信息。"""
        return dict(self._load_errors)

    def _load(self, manifest: PluginManifest) -> bool:
        plugin_dir = manifest.plugin_dir.resolve()
        plugin_dir_str = str(plugin_dir)
        added_to_path = False
        if plugin_dir_str not in sys.path:
            sys.path.insert(0, plugin_dir_str)
            added_to_path = True

        try:
            module_path, class_name = manifest.entry.split(":", 1)
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            if not (isinstance(cls, type) and issubclass(cls, PluginBase)):
                err_msg = f"入口类 {class_name} 未继承 PluginBase"
                logger.error("插件 %s 的%s", manifest.name, err_msg)
                self._load_errors[manifest.name] = err_msg
                return False

            self._context.set_plugin_name(manifest.name)
            plugin_instance = cls(self._context)
            plugin_instance.on_load()

            self._plugins[manifest.name] = plugin_instance
            self._manifests[manifest.name] = manifest
            logger.info("插件 %s v%s 加载成功", manifest.name, manifest.version)
            return True

        except Exception as e:
            err_msg = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
            self._load_errors[manifest.name] = err_msg
            logger.error("加载插件 %s 失败:\n%s", manifest.name, err_msg)
            if added_to_path and plugin_dir_str in sys.path:
                sys.path.remove(plugin_dir_str)
            return False

    def unload_all(self) -> None:
        """卸载所有已加载插件。"""
        for name, plugin in list(self._plugins.items()):
            try:
                plugin.on_unload()
                logger.info("插件 %s 已卸载", name)
            except Exception as e:
                logger.exception("卸载插件 %s 失败: %s", name, e)
        self._plugins.clear()
        self._manifests.clear()

    def get_plugin(self, name: str) -> Optional[PluginBase]:
        return self._plugins.get(name)

    def list_loaded(self) -> List[str]:
        return list(self._plugins.keys())

    def get_all_menu_items(self) -> list[tuple[str, str, callable]]:
        """收集所有已加载插件注册的菜单项。"""
        items = []
        for plugin in self._plugins.values():
            ctx = getattr(plugin, "context", None)
            if ctx is not None and hasattr(ctx, "get_menu_items"):
                items.extend(ctx.get_menu_items())
        return items

    def notify_scene_loaded(self) -> None:
        for plugin in self._plugins.values():
            try:
                plugin.on_scene_loaded()
            except Exception as e:
                logger.exception("插件 on_scene_loaded 失败: %s", e)

    def notify_simulation_started(self) -> None:
        for plugin in self._plugins.values():
            try:
                plugin.on_simulation_started()
            except Exception as e:
                logger.exception("插件 on_simulation_started 失败: %s", e)

    def notify_simulation_stopped(self) -> None:
        for plugin in self._plugins.values():
            try:
                plugin.on_simulation_stopped()
            except Exception as e:
                logger.exception("插件 on_simulation_stopped 失败: %s", e)
