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
        self.config["orca_project_folder"] = get_project_dir()

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
        return self.config["orcalab"]["executable"]

    def attach(self) -> bool:
        return self.config["orcalab"]["attach"]

    def orca_project_folder(self) -> str:
        return self.config["orca_project_folder"]

    def level(self) -> str:
        return self.config["orcalab"]["level"]