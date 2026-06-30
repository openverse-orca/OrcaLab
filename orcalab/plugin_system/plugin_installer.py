from __future__ import annotations

import logging
import pathlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import Callable, Optional

from orcalab.plugin_system.plugin_manifest import PluginManifest
from orcalab.plugin_system.plugin_manager import get_plugins_root
from orcalab.plugin_system.plugin_registry import PluginRegistry

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, str], None]


class PluginInstaller:
    """插件安装器：解压压缩包、执行 init.sh、安装 Python 依赖、注册到注册表。

    安装流程：
        1. 解压压缩包到临时目录
        2. 在临时目录中查找 plugin.toml，解析清单
        3. 复制插件目录到 plugins/installed/<name>/
        4. 执行 init.sh 初始化脚本（引擎注册、资产初始化等）
        5. pip install Python 依赖
        6. 注册到 PluginRegistry
    """

    def __init__(self, registry: PluginRegistry):
        self._registry = registry

    def install_from_archive(
        self,
        archive_path: pathlib.Path,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> PluginManifest:
        """从本地压缩包安装插件。

        Args:
            archive_path: 压缩包路径（支持 .tar.xz / .tar.gz / .tgz）
            progress_callback: 进度回调 (percent, detail)

        Returns:
            解析后的插件清单

        Raises:
            FileNotFoundError: 压缩包不存在
            ValueError: 压缩包中缺少 plugin.toml
            RuntimeError: init.sh 执行失败
        """
        archive_path = pathlib.Path(archive_path)
        if not archive_path.is_file():
            raise FileNotFoundError(f"压缩包不存在: {archive_path}")

        def _report(percent: int, detail: str) -> None:
            if progress_callback:
                progress_callback(percent, detail)

        _report(5, f"开始安装: {archive_path.name}")

        with tempfile.TemporaryDirectory(prefix="orcalab_plugin_") as tmp_dir:
            tmp_path = pathlib.Path(tmp_dir)

            _report(10, "解压压缩包…")
            self._extract_archive(archive_path, tmp_path, progress_callback)

            _report(30, "查找插件清单…")
            manifest = self._find_manifest(tmp_path)
            if manifest is None:
                raise ValueError(
                    f"压缩包中未找到 plugin.toml: {archive_path}"
                )

            plugin_name = manifest.name
            logger.info("发现插件: %s v%s", plugin_name, manifest.version)
            _report(35, f"插件: {plugin_name} v{manifest.version}")

            dest_dir = get_plugins_root() / plugin_name
            if dest_dir.exists():
                logger.info("插件目录已存在，覆盖安装: %s", dest_dir)
                shutil.rmtree(dest_dir)

            _report(40, f"复制文件到 {dest_dir}…")
            shutil.copytree(manifest.plugin_dir, dest_dir)

            manifest.plugin_dir = dest_dir

            init_script = dest_dir / manifest.init_script
            if init_script.is_file():
                _report(50, f"执行初始化脚本: {manifest.init_script}…")
                self._run_init_script(init_script, dest_dir, progress_callback)
            else:
                logger.info("插件无 init.sh，跳过初始化")
                _report(50, "无初始化脚本，跳过")

            if manifest.has_requirements_file:
                _report(70, "从 requirements.txt 安装 Python 依赖…")
                self._install_python_deps_from_requirements(
                    manifest.requirements_path, progress_callback
                )
            elif manifest.python_dependencies:
                _report(70, "安装 Python 依赖…")
                self._install_python_deps(manifest.python_dependencies, progress_callback)
            else:
                _report(70, "无 Python 依赖，跳过")

            _report(90, "注册插件…")
            self._registry.register_installed(
                plugin_name, manifest.version, str(dest_dir)
            )

            _report(100, f"插件 {plugin_name} 安装完成")
            logger.info("插件 %s 安装完成: %s", plugin_name, dest_dir)
            return manifest

    def uninstall(self, plugin_name: str) -> bool:
        """卸载插件：执行卸载脚本、删除目录、从注册表移除。

        卸载流程：
            1. 如果存在 plugin.toml 且声明了 uninstall_script，执行它
               （由脚本负责注销引擎/工程、清理外部缓存等）
            2. 删除插件目录
            3. 从注册表移除

        Returns:
            True 如果成功删除，False 如果插件不存在
        """
        plugin_dir = get_plugins_root() / plugin_name
        if not plugin_dir.exists():
            logger.warning("插件目录不存在: %s", plugin_dir)
            self._registry.unregister(plugin_name)
            return False

        # 优先执行插件声明的卸载脚本
        toml_path = plugin_dir / "plugin.toml"
        if toml_path.is_file():
            try:
                manifest = PluginManifest.from_toml(toml_path)
            except Exception as e:
                logger.warning("解析 plugin.toml 失败，跳过卸载脚本: %s", e)
                manifest = None
            if manifest is not None and manifest.has_uninstall_script:
                logger.info("执行卸载脚本: %s", manifest.uninstall_script_path)
                try:
                    self._run_uninstall_script(
                        manifest.uninstall_script_path, plugin_dir
                    )
                except RuntimeError as e:
                    # 卸载脚本失败不阻断目录清理，但记录 ERROR
                    logger.error("卸载脚本执行失败: %s", e)

        try:
            shutil.rmtree(plugin_dir)
            logger.info("已删除插件目录: %s", plugin_dir)
        except OSError as e:
            logger.error("删除插件目录失败: %s", e)
            return False

        self._registry.unregister(plugin_name)
        logger.info("插件 %s 已卸载", plugin_name)
        return True

    @staticmethod
    def _extract_archive(
        archive_path: pathlib.Path,
        dest_dir: pathlib.Path,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> None:
        """解压 tar.xz / tar.gz 压缩包。"""
        dest_dir.mkdir(parents=True, exist_ok=True)

        if archive_path.suffix == ".xz":
            mode = "r:xz"
        elif archive_path.suffix in (".gz", ".tgz"):
            mode = "r:gz"
        else:
            mode = "r:*"

        with tarfile.open(archive_path, mode=mode) as tf:
            try:
                tf.extractall(dest_dir, filter="data")
            except TypeError:
                tf.extractall(dest_dir)

    @staticmethod
    def _find_manifest(extracted_dir: pathlib.Path) -> Optional[PluginManifest]:
        """在解压目录中查找 plugin.toml。

        支持压缩包内有一个顶层目录的情况（如 OrcaBundleMcp/plugin.toml）。
        """
        candidates = [extracted_dir]
        items = list(extracted_dir.iterdir())
        if len(items) == 1 and items[0].is_dir():
            candidates.append(items[0])

        for c in candidates:
            toml_path = c / "plugin.toml"
            if toml_path.is_file():
                try:
                    return PluginManifest.from_toml(toml_path)
                except Exception as e:
                    logger.error("解析 plugin.toml 失败: %s", e)
                    raise ValueError(f"plugin.toml 解析失败: {e}") from e
        return None

    @staticmethod
    def _run_init_script(
        script_path: pathlib.Path,
        work_dir: pathlib.Path,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> None:
        """执行插件的 init.sh 初始化脚本。

        init.sh 是插件系统约定的初始化脚本，负责：
        - 注册引擎/工程（如 o3de register）
        - 初始化资产
        - 生成配置文件

        脚本退出码非零视为失败。
        """
        logger.info("执行 init.sh: %s (工作目录: %s)", script_path, work_dir)
        try:
            result = subprocess.run(
                ["bash", str(script_path)],
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as e:
            raise RuntimeError(f"无法执行 init.sh（bash 不可用）: {e}") from e

        if result.stdout:
            for line in result.stdout.strip().splitlines():
                logger.info("[init.sh] %s", line)
        if result.stderr:
            for line in result.stderr.strip().splitlines():
                logger.warning("[init.sh] %s", line)

        if result.returncode != 0:
            raise RuntimeError(
                f"init.sh 执行失败 (退出码 {result.returncode}): {result.stderr.strip()}"
            )

    @staticmethod
    def _run_uninstall_script(
        script_path: pathlib.Path,
        work_dir: pathlib.Path,
    ) -> None:
        """执行插件的卸载脚本（如 uninstall.sh）。

        卸载脚本属于后处理步骤：脚本失败不阻断插件目录清理，
        但调用方需捕获 RuntimeError 并记录 ERROR。
        """
        logger.info("执行卸载脚本: %s (工作目录: %s)", script_path, work_dir)
        try:
            result = subprocess.run(
                ["bash", str(script_path)],
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as e:
            raise RuntimeError(f"无法执行卸载脚本（bash 不可用）: {e}") from e

        if result.stdout:
            for line in result.stdout.strip().splitlines():
                logger.info("[uninstall] %s", line)
        if result.stderr:
            for line in result.stderr.strip().splitlines():
                logger.warning("[uninstall] %s", line)

        if result.returncode != 0:
            raise RuntimeError(
                f"卸载脚本返回非零退出码 {result.returncode}: {result.stderr.strip()}"
            )

    @staticmethod
    def _install_python_deps(
        deps: list[str],
        progress_callback: Optional[ProgressCallback] = None,
    ) -> None:
        """通过 pip 安装 Python 依赖。"""
        if not deps:
            return

        cmd = [sys.executable, "-m", "pip", "install"] + deps
        logger.info("安装 Python 依赖: %s", " ".join(deps))
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.stdout:
            logger.debug("[pip] %s", result.stdout.strip())
        if result.returncode != 0:
            logger.error("[pip] %s", result.stderr.strip())
            raise RuntimeError(
                f"Python 依赖安装失败 (退出码 {result.returncode}): {result.stderr.strip()}"
            )

    @staticmethod
    def _install_python_deps_from_requirements(
        requirements_path: pathlib.Path,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> None:
        """通过 pip install -r requirements.txt 安装依赖。"""
        cmd = [sys.executable, "-m", "pip", "install", "-r", str(requirements_path)]
        logger.info("安装 Python 依赖 (requirements.txt): %s", requirements_path)
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.stdout:
            logger.debug("[pip] %s", result.stdout.strip())
        if result.returncode != 0:
            logger.error("[pip] %s", result.stderr.strip())
            raise RuntimeError(
                f"requirements.txt 依赖安装失败 (退出码 {result.returncode}): {result.stderr.strip()}"
            )
