from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from PySide6 import QtWidgets

    from orcalab.plugin_system.plugin_context import PluginContext


class PluginBase:
    """所有 OrcaLab 插件的基类。

    生命周期由 PluginManager 驱动：
        on_load   -> 插件被加载时调用（注册 Event Bus handler、添加面板等）
        on_unload -> 插件被卸载时调用（清理资源、断开 Event Bus 连接）

    可选通知方法默认空实现，插件按需覆写：
        on_scene_loaded / on_simulation_started / on_simulation_stopped

    配置 UI 扩展点：
        create_config_widget -> 返回自定义 QWidget，用于插件管理对话框中编辑插件配置。
        不覆写时宿主回退到通用文本编辑器（编辑 plugin.toml 中 config_files 声明的文件）。

    注意：不继承 ABC，以允许插件同时继承 QtCore.QObject（解决 PySide6 元类冲突）。
    on_load 仍需子类覆写，否则抛出 NotImplementedError。
    """

    def __init__(
        self,
        context: Optional["PluginContext"] = None,
        *args: object,
        **kwargs: object,
    ) -> None:
        """初始化插件基类。

        context 通常由 PluginManager 在加载插件时显式传入。为 Optional 是
        为了兼容多继承场景：当子类同时继承 QObject 时，子类的
        super().__init__() 会沿 MRO 链无参传播到本方法（QObject / Object
        未在 Python 层定义 __init__，super() 直接落到 PluginBase）。
        子类应在自己的 __init__ 中显式调用 PluginBase.__init__(self, context)。
        """
        if context is not None:
            self.context = context
            self.logger = context.logger()

    def on_load(self) -> None:
        raise NotImplementedError("插件必须覆写 on_load 方法")

    def on_unload(self) -> None:
        pass

    def on_scene_loaded(self) -> None:
        pass

    def on_simulation_started(self) -> None:
        pass

    def on_simulation_stopped(self) -> None:
        pass

    def create_config_widget(
        self, parent: Optional["QtWidgets.QWidget"] = None
    ) -> Optional["QtWidgets.QWidget"]:
        """返回插件自定义的配置编辑控件。

        插件按需覆写此方法，返回一个 QWidget 子类实例。宿主会将该 widget
        嵌入到配置对话框中，由插件完全控制 UI 布局与保存逻辑。

        返回 None 时，宿主回退到通用文本编辑器（编辑 plugin.toml 中
        config_files 声明的文件）。
        """
        return None
