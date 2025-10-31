import os
import tomllib
import sys
from pathlib import Path
import importlib.metadata

from orcalab.project_util import get_project_dir


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
                pyproject_path = os.path.join(os.path.dirname(__file__), "..", "pyproject.toml")
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
                print(f"警告: 配置文件中未找到版本号")
                return False
                
            if config_version != package_version:
                print(f"错误: 配置文件版本不匹配!")
                print(f"  配置文件版本: {config_version}")
                print(f"  当前包版本: {package_version}")
                print(f"  请更新配置文件或重新安装匹配版本的 orca-lab 包")
                return False
                
            print(f"配置文件版本校验通过: {config_version}")
            return True
            
        except Exception as e:
            print(f"版本校验时发生错误: {e}")
            return False

    def init_config(self, root_folder: str):
        self.config = {}
        self.config["orca_project_folder"] = str(get_project_dir())

        self.root_folder = root_folder
        
        # 智能查找配置文件路径
        self.config_path = self._find_config_file("orca.config.toml", root_folder)
        self.user_config_path = self._find_config_file("orca.config.user.toml", root_folder)

        with open(self.config_path, "rb") as file:
            shared_config = tomllib.load(file)

        # 进行版本校验
        if not self._validate_config_version(shared_config):
            print("版本校验失败，程序将退出")
            sys.exit(1)

        # 加载用户配置（如果存在）
        user_config = {}
        if os.path.exists(self.user_config_path):
            with open(self.user_config_path, "rb") as file:
                user_config = tomllib.load(file)
        else:
            print(f"用户配置文件不存在: {self.user_config_path}")
            print("将使用默认配置。如需自定义配置，请创建该文件或参考 orca.config.user.toml.example")

        self.config = deep_merge(self.config, shared_config)
        self.config = deep_merge(self.config, user_config)

        print(self.config)

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
        return self.config["orcalab"].get("level", "Default_level")
    
    def levels(self) -> list:
        return self.config["orcalab"].get("levels", [])
    
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
        return self.config.get("copilot", {}).get("server_url", "http://103.237.28.246:9023")
    
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
        return self.config.get("datalink", {}).get("base_url", "http://localhost:8080/api")
    
    def datalink_username(self) -> str:
        """获取 DataLink 用户名（优先从本地存储读取）"""
        from orcalab.token_storage import TokenStorage
        
        # 优先从本地存储读取
        token_data = TokenStorage.load_token()
        if token_data and token_data.get('username'):
            return token_data['username']
        
        # 否则从配置文件读取（兼容旧配置）
        return self.config.get("datalink", {}).get("username", "")
    
    def datalink_token(self) -> str:
        """获取 DataLink 访问令牌（优先从本地存储读取）"""
        from orcalab.token_storage import TokenStorage
        
        # 优先从本地存储读取
        token_data = TokenStorage.load_token()
        if token_data and token_data.get('access_token'):
            return token_data['access_token']
        
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
        return self.config.get("datalink", {}).get("auth_server_url", "https://datalink.orca3d.cn:8081")
    
    def web_server_url(self) -> str:
        """获取资产库服务器地址（用于认证后跳转）"""
        return self.config.get("web_server_url", "https://simassets.orca3d.cn/")