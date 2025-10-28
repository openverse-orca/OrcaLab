import os
import tomllib

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

    def init_config(self, root_folder: str):
        self.config = {}
        self.config["orca_project_folder"] = str(get_project_dir())

        self.root_folder = root_folder
        self.config_path = os.path.join(self.root_folder, "orca.config.toml")
        self.user_config_path = os.path.join(self.root_folder, "orca.config.user.toml")

        with open(self.config_path, "rb") as file:
            shared_config = tomllib.load(file)

        with open(self.user_config_path, "rb") as file:
            user_config = tomllib.load(file)

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
    
    def level(self) -> str:
        return self.config["orcalab"].get("level", "Default_level")
    
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