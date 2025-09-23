
import orcalab.url_service.url_util_linux as url_util_linux
import orcalab.url_service.url_util_windows as url_util_windows

import argparse
import sys

def register_protocol():
    if sys.platform == "win32":
        url_util_windows.register_protocol()
    else:
        url_util_linux.register_protocol()


def unregister_protocol():
    if sys.platform == "win32":
        url_util_windows.unregister_protocol()
    else:
        url_util_linux.unregister_protocol()


def is_protocol_registered():
    if sys.platform == "win32":
        return url_util_windows.is_protocol_registered()
    else:
        return url_util_linux.is_protocol_registered()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--url", required=False, type=str, help="The URL of the asset to download."
    )
    parser.add_argument(
        "--serve", action="store_true", help="Run as server. For testing purpose."
    )
    parser.add_argument(
        "--register", action="store_true", help="Register custom protocol."
    )
    parser.add_argument(
        "--unregister", action="store_true", help="Unregister custom protocol."
    )
    parser.add_argument(
        "--query", action="store_true", help="Query if custom protocol is registered."
    )
    args = parser.parse_args()

    if args.register:
        register_protocol()
    elif args.unregister:
        unregister_protocol()
    elif args.query:
        if is_protocol_registered():
            print(f"1")
        else:
            print(f"0")
    else:
        parser.print_help()
