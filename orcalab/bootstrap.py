import os
import json
import orcalab.orca_uri as orca_uri

# Register orca uri scheme.

if not orca_uri.is_protocol_registered():
    orca_uri.register_protocol()


# Check project folder.

home_dir = os.path.expanduser("~")
project_dir = os.path.join(home_dir, "Orca", "OrcaLab", "DefaultProject")

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


