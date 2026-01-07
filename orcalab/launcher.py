import subprocess
import shutil
import pathlib
import sys
import os

from orcalab.config_service import ConfigService
from orcalab.cli_options import create_argparser


def create_config_file(workspace: pathlib.Path):
    this_dir = pathlib.Path(__file__).parent.resolve()

    config_service = ConfigService()
    # Hack: we do not want init here
    config_service._workspace = workspace
    config_service.workspace_data_folder().mkdir(parents=True, exist_ok=True)

    if config_service.workspace_config_file().exists():
        print("配置文件已存在")
        return

    template_config = this_dir / "orca.config.template.toml"
    if not template_config.exists():
        print(f"找不到模板配置文件: {template_config}")
        sys.exit(1)

    shutil.copy(template_config, config_service.workspace_config_file())


def launch_orcalab_gui():
    try:
        envs = os.environ.copy()
        if "LD_LIBRARY_PATH" in envs:
            del envs["LD_LIBRARY_PATH"]

        args = [sys.executable, "-m", "orcalab.main"] + sys.argv[1:]
        subprocess.run(args, env=envs)
        sys.exit(0)
    except Exception as e:
        print(f"启动 OrcaLab GUI 失败: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = create_argparser()

    args, unknown = parser.parse_known_args()

    workspace = pathlib.Path(args.workspace).resolve()

    if args.init_config:
        create_config_file(workspace)
        return

    launch_orcalab_gui()


if __name__ == "__main__":
    main()
