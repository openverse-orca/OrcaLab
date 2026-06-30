from __future__ import annotations

import logging
import pathlib
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from orcalab.config_service import ConfigService
    from orcalab.event_bus import EventBusProxy
    from orcalab.local_scene import LocalScene
    from orcalab.remote_scene import RemoteScene


class PluginContext:
    """插件与宿主交互的唯一入口。

    通过受控 API 访问宿主能力，避免插件直接 import 宿主内部模块，
    便于未来增加权限控制与沙箱隔离。
    """

    def __init__(self, main_window: Any):
        self._main_window = main_window
        self._plugin_name: str = ""
        self._logger: logging.Logger | None = None
        self._menu_items: list[tuple[str, str, Callable]] = []

    def set_plugin_name(self, name: str) -> None:
        self._plugin_name = name
        self._logger = logging.getLogger(f"orcalab.plugin.{name}")

    def logger(self) -> logging.Logger:
        if self._logger is None:
            self._logger = logging.getLogger("orcalab.plugin")
        return self._logger

    def get_config(self) -> "ConfigService":
        from orcalab.config_service import ConfigService

        return ConfigService()

    def get_local_scene(self) -> "LocalScene":
        return self._main_window.local_scene

    def get_remote_scene(self) -> "RemoteScene":
        return self._main_window.remote_scene

    def get_main_window(self) -> Any:
        return self._main_window

    def get_event_bus(self, bus_class: type) -> "EventBusProxy":
        """根据 Event Bus 接口类获取对应的单例 Proxy。

        用法：context.get_event_bus(SceneEditNotificationBus)
        """
        return bus_class()

    def add_panel(
        self,
        panel_name: str,
        panel_content: Any,
        area: str = "right",
        icon_path: Optional[str] = None,
    ) -> None:
        """添加面板到指定区域（left / right / bottom）。"""
        from orcalab.ui.panel import Panel
        from orcalab.ui.icon_util import make_icon
        from orcalab.ui.theme_service import ThemeService

        panel = Panel(panel_name, panel_content)
        if icon_path:
            theme_service = ThemeService()
            panel_icon_color = theme_service.get_color("panel_icon")
            panel.panel_icon = make_icon(icon_path, panel_icon_color)
        self._main_window.add_panel(panel, area)

    def add_menu_item(self, menu_title: str, item_text: str, callback: Callable[[], None]) -> None:
        """注册菜单项。

        menu_title 用于在插件菜单中分组显示；
        所有插件菜单项统一显示在"插件"菜单下，不再分发到其他宿主菜单，
        避免被 menu.clear() 清除或重复添加。
        """
        self._menu_items.append((menu_title, item_text, callback))

    def get_menu_items(self) -> list[tuple[str, str, Callable]]:
        """获取本插件注册的所有菜单项。"""
        return list(self._menu_items)

    def add_mcp_tool(self, func: Callable) -> None:
        """向 MCP 服务注册一个工具函数。

        需在 MCP 服务启动前调用；插件 on_load 时机满足该约束。
        """
        mcp_service = getattr(self._main_window, "mcp_service", None)
        if mcp_service is None:
            self.logger().warning("MCP 服务尚未创建，无法注册工具 %s", getattr(func, "__name__", func))
            return
        mcp_service.mcp.tool(func)

    def get_plugin_data_dir(self) -> pathlib.Path:
        """获取该插件的专属数据目录（可读写）。"""
        from orcalab.project_util import get_user_folder

        data_dir = get_user_folder() / "plugins" / self._plugin_name
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    def get_plugin_config(self, default: Any = None) -> Any:
        """从用户配置中读取本插件的配置节 [plugins.<plugin_name>]。"""
        cfg = self.get_config()
        plugins_cfg = cfg.config.get("plugins", {})
        return plugins_cfg.get(self._plugin_name, default if default is not None else {})
