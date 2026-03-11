import argparse


def create_argparser():
    parser = argparse.ArgumentParser(
        prog="orcalab",
        description=("OrcaLab 启动器\n\n"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False,  # 禁用前缀匹配
    )
    parser.add_argument(
        "-l",
        "--log-level",
        dest="log_level",
        metavar="LEVEL",
        help="控制台日志等级（支持 DEBUG/INFO/WARNING/ERROR/CRITICAL），默认输出 WARNING 及以上，日志文件会记录 INFO 及以上的全部日志。",
    )

    parser.add_argument(
        "workspace", nargs="?", default=".", help="工作目录，默认为当前目录"
    )

    parser.add_argument(
        "--init-config", action="store_true", help="初始化配置文件并退出"
    )

    parser.add_argument("--verbose", action="store_true", help="输出所有信息到终端")

    parser.add_argument(
        "--scene", type=str, help="指定要加载的场景文件。不指定会弹出场景选择界面。"
    )
    parser.add_argument(
        "--layout",
        type=str,
        help="指定要加载的布局文件。'default', 'blank' 或者布局文件路径。不指定会加载默认布局。",
    )
    parser.add_argument(
        "--sim-config",
        type=str,
        help="指定要加载的仿真配置名称，必须在配置文件中存在。如果是'external'则使用外部程序模式启动。\
        不指定会弹出配置选择界面。这个参数只有在'--full-screen'模式下才会生效。",
    )
    parser.add_argument("--full-screen", action="store_true", help="以全屏模式启动应用")

    return parser
