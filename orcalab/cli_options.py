import argparse
import os
import pathlib
import sys

from orcalab.i18n import tr

_UI_LANGUAGE_CHOICES = ("zh_CN", "zh", "en_US", "en")


def _preparse_option(argv: list[str], option_name: str) -> str | None:
    value = None
    for index, arg in enumerate(argv):
        if arg == option_name and index + 1 < len(argv):
            value = argv[index + 1]
        elif arg.startswith(f"{option_name}="):
            value = arg.split("=", 1)[1]
    return value


def preparse_ui_language(argv: list[str]) -> str | None:
    """Return the explicit language requested for this launch."""
    return _preparse_option(argv, "--lang")


def create_argparser():
    parser = argparse.ArgumentParser(
        prog="orcalab",
        description=(
            tr("OrcaLab 启动器\n\n")
            + tr("已运行图形界面时，可用「orcalab-cli …」在终端调用 MCP 工具（参见 orcalab-cli -h）。\n\n")
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False,  # 禁用前缀匹配
    )
    parser.add_argument(
        "-l",
        "--log-level",
        dest="log_level",
        metavar="LEVEL",
        help=tr(
            "控制台日志等级（支持 DEBUG/INFO/WARNING/ERROR/CRITICAL），"
            "默认输出 WARNING 及以上，日志文件会记录 INFO 及以上的全部日志。"
        ),
    )

    parser.add_argument(
        "workspace", nargs="?", default=".", help=tr("工作目录，默认为当前目录")
    )

    parser.add_argument(
        "--init-config", action="store_true", help=tr("初始化配置文件并退出")
    )

    parser.add_argument("--verbose", action="store_true", help=tr("输出所有信息到终端"))
    parser.add_argument(
        "--lang",
        choices=_UI_LANGUAGE_CHOICES,
        help=tr(
            "临时设置本次启动的界面语言（zh_CN 或 en_US），不修改已保存设置。"
        ),
    )
    # Compatibility only: older dual-language Windows launchers may still pass
    # this option. It is accepted but deliberately ignored.
    parser.add_argument(
        "--initial-lang",
        choices=_UI_LANGUAGE_CHOICES,
        help=argparse.SUPPRESS,
    )

    parser.add_argument(
        "--scene", type=str, help=tr("指定要加载的场景文件。不指定会弹出场景选择界面。")
    )
    parser.add_argument(
        "--layout",
        type=str,
        help=tr("指定要加载的布局文件。'default', 'blank' 或者布局文件路径。不指定会加载默认布局。"),
    )
    parser.add_argument(
        "--sim-config",
        type=str,
        help=tr("指定要加载的仿真配置名称，必须在配置文件中存在。如果是'external'则使用外部程序模式启动。\
        不指定会弹出配置选择界面。这个参数只有在'--full-screen'模式下才会生效。"),
    )
    parser.add_argument("--full-screen", action="store_true", help=tr("以全屏模式启动应用"))
    parser.add_argument(
        "--port",
        type=int,
        help=tr("URL服务端口号（默认：50651）。如果端口被占用，程序会自动尝试其他端口。"),
    )
    parser.add_argument(
        "--force-adapter",
        type=str,
        help=tr("强制指定 GPU 适配器名称（子串匹配，不区分大小写），例如 NVIDIA、RTX、MTT"),
    )
    parser.add_argument(
        "--adapter-index",
        type=int,
        help=tr("当 --force-adapter 匹配到多个 GPU 时，选择第几个（默认 0）"),
    )

    return parser

# 判断 workspace 路径是否合法
def resolve_and_validate_workspace(
    workspace: str, *, init_config: bool
) -> pathlib.Path:
    """解析工作目录；不合法则打印错误并退出"""
    try:
        p = pathlib.Path(workspace).expanduser().resolve(strict=False)
    except OSError as e:
        print(tr("工作目录无效: {workspace} ({error})", workspace=workspace, error=e), file=sys.stderr)
        sys.exit(2)
    if p.exists():
        if not p.is_dir():
            print(tr("工作目录不是文件夹: {path}", path=p), file=sys.stderr)
            sys.exit(2)
        if not os.access(p, os.R_OK):
            print(tr("工作目录不可读: {path}", path=p), file=sys.stderr)
            sys.exit(2)
        if init_config and not os.access(p, os.W_OK):
            print(tr("工作目录不可写（无法初始化配置）: {path}", path=p), file=sys.stderr)
            sys.exit(2)
    else:
        if not init_config:
            print(tr("工作目录不存在: {path}", path=p), file=sys.stderr)
            sys.exit(2)
        parent = p.parent
        if not parent.exists() or not parent.is_dir():
            print(tr("工作目录的父路径不存在或不是文件夹: {path}", path=parent), file=sys.stderr)
            sys.exit(2)
        if not os.access(parent, os.W_OK):
            print(tr("父目录无写权限，无法创建工作目录: {path}", path=parent), file=sys.stderr)
            sys.exit(2)
    return p
