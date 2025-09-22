import os
import json


def get_project_dir():
    home_dir = os.path.expanduser("~")
    project_dir = os.path.join(home_dir, "Orca", "OrcaLab", "DefaultProject")
    return project_dir


def check_project_folder():

    project_dir = get_project_dir()
    if not os.path.exists(project_dir):
        os.makedirs(project_dir, exist_ok=True)
        print(f"Created default project folder at: {project_dir}")

        data = {
            "project_name": "DefaultProject",
            "project_id": "{3DB8A56E-2458-4543-93A1-1A41756B97DA}",
            "display_name": "DefaultProject",
        }

        config_path = os.path.join(project_dir, "project.json")
        with open(config_path, "w") as f:
            json.dump(data, f, indent=4)
