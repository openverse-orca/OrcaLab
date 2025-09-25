import os
import json
from typing import List
import pathlib
import sys
import shutil


project_id = "{3DB8A56E-2458-4543-93A1-1A41756B97DA}"


def get_project_dir():
    project_dir = pathlib.Path.home() / "Orca" / "OrcaLab" / "DefaultProject"
    return project_dir


def check_project_folder():

    project_dir = get_project_dir()
    if not project_dir.exists():
        project_dir.mkdir(parents=True, exist_ok=True)
        print(f"Created default project folder at: {project_dir}")

        data = {
            "project_name": "DefaultProject",
            "project_id": project_id,
            "display_name": "DefaultProject",
        }

        config_path = os.path.join(project_dir, "project.json")
        with open(config_path, "w") as f:
            json.dump(data, f, indent=4)


def get_cache_folder():
    if sys.platform == "win32":
        local_appdata = os.getenv("LOCALAPPDATA")
        if local_appdata:
            return pathlib.Path(local_appdata) / "Orca" / "OrcaStudio" / project_id / "Cache" / "pc"
        else:
            raise EnvironmentError("LOCALAPPDATA environment variable is not set.")
    else:
        return pathlib.Path.home() / "Orca" / "OrcaStudio" / project_id / "Cache" / "linux"
   

def copy_packages(packages: List[str]):
    cache_folder = get_cache_folder()
    cache_folder.mkdir(parents=True, exist_ok=True)
    for package in packages:
        package_path = pathlib.Path(package)
        if package_path.exists() and package_path.is_file():
            shutil.copy(package_path, cache_folder)
            print(f"Copied {package} to {cache_folder}")
        else:
            print(f"Package {package} does not exist or is not a file.")
    