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

    return parser
