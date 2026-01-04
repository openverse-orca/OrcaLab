import os
import tomllib
import sys
import pathlib
import importlib.metadata
import logging

from orcalab.project_util import get_project_dir

logger = logging.getLogger(__name__)


def deep_merge(dict1, dict2):
    """
    Recursively merges dict2 into dict1.
    If a key exists in both and their values are dictionaries,
    it recursively merges those nested dictionaries.
    Otherwise, it updates dict1 with the value from dict2.
    """
    for key, value in dict2.items():
        if key in dict1 and isinstance(dict1[key], dict) and isinstance(value, dict):
            # Recursively merge nested dictionaries
            deep_merge(dict1[key], value)
        else:
            # Update or add non-dictionary values
            dict1[key] = value
    return dict1


# ConfigService is a singleton
class ConfigService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)

            # Add any initialization logic here if needed

        return cls._instance

    def _find_config_file(self, filename: str, root_folder: str) -> str:
        """
        查找配置文件，优先查找用户配置，然后查找模块默认配置
        """
        # 1. 首先在传入的根目录中查找用户配置文件
        config_path = os.path.join(root_folder, filename)
        if os.path.exists(config_path):
            return config_path

        # 2. 在 orcalab 包目录中查找（模块默认配置）
        package_dir = os.path.dirname(__file__)
        config_path = os.path.join(package_dir, filename)
        if os.path.exists(config_path):
            return config_path

        # 3. 如果都找不到，返回默认路径（用于错误提示）
        return os.path.join(root_folder, filename)

    def _get_package_version(self) -> str:
        """
        获取当前安装的 orca-lab 包版本号
        """
        try:
            return importlib.metadata.version("orca-lab")
        except importlib.metadata.PackageNotFoundError:
            # 如果包未安装，尝试从 pyproject.toml 读取
            try:
                import tomllib

                pyproject_path = os.path.join(
                    os.path.dirname(__file__), "..", "pyproject.toml"
                )
                with open(pyproject_path, "rb") as f:
                    data = tomllib.load(f)
                    return data["project"]["version"]
            except Exception:
                return "unknown"

    def _validate_config_version(self, config_data: dict) -> bool:
        """
        验证配置文件版本是否与当前安装的包版本一致
        """
        try:
            config_version = config_data.get("orcalab", {}).get("version", "")
            package_version = self._get_package_version()

            if not config_version:
                logger.warning("配置文件中未找到版本号")
                return False

            if config_version != package_version:
                logger.error(
                    "配置文件版本不匹配! 配置文件版本: %s, 当前包版本: %s",
                    config_version,
                    package_version,
                )
                logger.error("请更新配置文件或重新安装匹配版本的 orca-lab 包")
                return False

            logger.info("配置文件版本校验通过: %s", config_version)
            return True

        except Exception as e:
            logger.exception("版本校验时发生错误: %s", e)
            return False

    def init_config(self, root_folder: pathlib.Path, workspace: pathlib.Path):
        self.config = {}
        self.config["orca_project_folder"] = str(get_project_dir())

        self._workspace = workspace

        self.root_folder = root_folder
        self.discovered_levels = []

        # 智能查找配置文件路径
        self.config_path = self._find_config_file(
            "orca.config.toml", root_folder.as_posix()
        )
        self.old_user_config_path = self._find_config_file(
            "orca.config.user.toml", root_folder.as_posix()
        )

        if sys.platform == "win32":
            platform_config_name = "orca.config.platform_win32.toml"
        else:
            platform_config_name = "orca.config.platform_linux.toml"

        self.platform_config_path = self._find_config_file(
            platform_config_name, root_folder.as_posix()
        )

        with open(self.config_path, "rb") as file:
            shared_config = tomllib.load(file)

        platform_config = {}
        if os.path.exists(self.platform_config_path):
            with open(self.platform_config_path, "rb") as file:
                platform_config = tomllib.load(file)

        # Deperacated
        # 加载用户配置（如果存在）
        old_user_config = {}
        if os.path.exists(self.old_user_config_path):
            with open(self.old_user_config_path, "rb") as file:
                old_user_config = tomllib.load(file)

        workspace_config = {}
        if os.path.exists(self.workspace_config_file()):
            with open(self.workspace_config_file(), "rb") as file:
                workspace_config = tomllib.load(file)

        self.config = deep_merge(self.config, shared_config)
        self.config = deep_merge(self.config, platform_config)
        self.config = deep_merge(self.config, old_user_config)
        self.config = deep_merge(self.config, workspace_config)

        self._normalize_levels()

        logger.debug("加载的配置: %s", self.config)

        # 进行版本校验
        if not self._validate_config_version(shared_config):
            logger.error("版本校验失败，程序将退出")
            sys.exit(1)

    def _normalize_levels(self):
        """确保 levels 配置为包含 name/path 的列表，并移除重复项"""
        orcalab_cfg = self.config.setdefault("orcalab", {})
        levels = orcalab_cfg.get("levels", [])

        normalized_levels = []
        for item in levels:
            level_data = self._normalize_level_item(item)
            if level_data:
                normalized_levels.append(level_data)

        orcalab_cfg["levels"] = self._deduplicate_levels(normalized_levels)

    def _deduplicate_levels(self, levels):
        seen_paths = set()
        deduped = []
        for item in levels:
            path = item["path"]
            if path in seen_paths:
                continue
            seen_paths.add(path)
            deduped.append(item)
        return deduped

    def app_version(self) -> str:
        return self._get_package_version()

    def workspace(self) -> pathlib.Path:
        return self._workspace

    def workspace_data_folder(self) -> pathlib.Path:
        return self._workspace / ".orcalab"

    def workspace_config_file(self) -> pathlib.Path:
        return self.workspace_data_folder() / "config.toml"

    def edit_port(self) -> int:
        return self.config["orcalab"]["edit_port"]

    def sim_port(self) -> int:
        return self.config["orcalab"]["sim_port"]

    def executable(self) -> str:
        # return self.config["orcalab"]["executable"]
        return "pseudo.exe"

    def attach(self) -> bool:
        # return self.config["orcalab"]["attach"]
        return True

    def is_development(self) -> bool:
        value = self.config["orcalab"]["dev"]["development"]
        return bool(value)

    def connect_builder_hub(self) -> bool:
        if not self.is_development():
            return False

        value = self.config["orcalab"]["dev"]["connect_builder_hub"]
        return bool(value)

    def dev_project_path(self) -> str:
        if not self.is_development():
            return ""

        value = self.config["orcalab"]["dev"]["project_path"]
        return str(value)

    def paks(self) -> list:
        return self.config["orcalab"].get("paks", [])

    def pak_urls(self) -> list:
        return self.config["orcalab"].get("pak_urls", [])

    def level(self) -> str:
        level_value = self.config["orcalab"].get("level")
        if isinstance(level_value, dict):
            return level_value.get("path") or level_value.get("name") or "Default_level"
        return level_value or "Default_level"

    def levels(self) -> list:
        return self.config["orcalab"].get("levels", [])

    def merge_levels(self, additional_levels: list):
        """合并额外场景，避免重复"""
        if not additional_levels:
            return

        normalized = []
        for item in additional_levels:
            level_data = self._normalize_level_item(item)
            if level_data:
                normalized.append(level_data)

        if not normalized:
            return

        merged = self._deduplicate_levels(normalized + self.levels())
        self.config["orcalab"]["levels"] = merged

    def set_current_level(self, level_info: dict):
        level_data = self._normalize_level_item(level_info)
        if not level_data:
            return

        # 确保场景在列表中
        self.merge_levels([level_data])

        self.config.setdefault("orcalab", {})["level"] = level_data

    def _normalize_level_item(self, item):
        if isinstance(item, str):
            name = self._to_spawnable_path(item)
            return {"name": name, "path": name}

        if isinstance(item, dict):
            path = item.get("path") or item.get("name")
            path = self._to_spawnable_path(path)
            if not path:
                logger.warning("忽略无效的场景配置: %s", item)
                return None
            name = item.get("name") or path
            normalized = {"name": name, "path": path}
            for key, value in item.items():
                if key not in {"name", "path"}:
                    normalized[key] = value
            return normalized

        logger.warning("无法识别的场景配置类型: %s", item)
        return None

    @staticmethod
    def _to_spawnable_path(path):
        if not path:
            return None
        if path.lower().endswith(".prefab"):
            return path[:-7] + ".spawnable"
        return path

    def orca_project_folder(self) -> str:
        return self.config["orca_project_folder"]

    def init_paks(self) -> bool:
        return self.config["orcalab"].get("init_paks", True)

    def lock_fps(self) -> str:
        if self.config["orcalab"]["lock_fps"] == 30:
            return "--lockFps30"
        elif self.config["orcalab"]["lock_fps"] == 60:
            return "--lockFps60"
        else:
            return ""

    def copilot_server_url(self) -> str:
        return self.config.get("copilot", {}).get(
            "server_url", "http://103.237.28.246:9023"
        )

    def copilot_timeout(self) -> int:
        return self.config.get("copilot", {}).get("timeout", 180)

    def external_programs(self) -> list:
        """获取仿真程序配置列表"""
        return self.config.get("external_programs", {}).get("programs", [])

    def default_external_program(self) -> str:
        """获取默认仿真程序名称"""
        return self.config.get("external_programs", {}).get("default", "sim_process")

    def get_external_program_config(self, program_name: str) -> dict:
        """根据程序名称获取程序配置"""
        programs = self.external_programs()
        for program in programs:
            if program.get("name") == program_name:
                return program
        return {}

    def datalink_base_url(self) -> str:
        """获取 DataLink 后端 API 地址"""
        return self.config.get("datalink", {}).get(
            "base_url", "http://localhost:8080/api"
        )

    def datalink_username(self) -> str:
        """获取 DataLink 用户名（优先从本地存储读取）"""
        from orcalab.token_storage import TokenStorage

        # 优先从本地存储读取
        token_data = TokenStorage.load_token()
        if token_data and token_data.get("username"):
            return token_data["username"]

        # 否则从配置文件读取（兼容旧配置）
        return self.config.get("datalink", {}).get("username", "")

    def datalink_token(self) -> str:
        """获取 DataLink 访问令牌（优先从本地存储读取）"""
        from orcalab.token_storage import TokenStorage

        # 优先从本地存储读取
        token_data = TokenStorage.load_token()
        if token_data and token_data.get("access_token"):
            return token_data["access_token"]

        # 否则从配置文件读取（兼容旧配置）
        return self.config.get("datalink", {}).get("token", "")

    def datalink_enable_sync(self) -> bool:
        """是否启用 DataLink 资产同步"""
        return self.config.get("datalink", {}).get("enable_sync", True)

    def datalink_timeout(self) -> int:
        """获取 DataLink 请求超时时间"""
        return self.config.get("datalink", {}).get("timeout", 60)

    def datalink_auth_server_url(self) -> str:
        """获取 DataLink 认证服务器地址"""
        return self.config.get("datalink", {}).get(
            "auth_server_url", "https://datalink.orca3d.cn:8081"
        )

    def web_server_url(self) -> str:
        """获取资产库服务器地址（用于认证后跳转）"""
        return self.config.get("datalink", {}).get(
            "web_server_url", "https://simassets.orca3d.cn/"
        )

    def layout_mode(self) -> str:
        return self.config.setdefault("orcalab", {}).get("layout_mode", "default")

    def set_layout_mode(self, mode: str):
        self.config.setdefault("orcalab", {})["layout_mode"] = mode

    def default_layout_file(self) -> str | None:
        path = self.config.setdefault("orcalab", {}).get("default_layout_file")
        if not path:
            return None
        return path

    def set_default_layout_file(self, path: str | None):
        if path:
            self.config.setdefault("orcalab", {})["default_layout_file"] = path
        else:
            self.config.setdefault("orcalab", {}).pop("default_layout_file", None)

    def current_level_info(self) -> dict | None:
        level_value = self.config["orcalab"].get("level")
        if isinstance(level_value, dict):
            return level_value
        if isinstance(level_value, str):
            return {"name": level_value, "path": level_value}
        return None
