import argparse
import urllib
import asyncio
import pathlib

from orcalab.url_service.url_service import UrlServiceClient, UrlServiceServer


def _log_file_path():
    home = pathlib.Path.home()
    log_dir = home / "Orca" / "OrcaLab" / "Logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "url_service.log"


async def serve():
    server = UrlServiceServer()
    await server.start()
    await server.server.wait_for_termination()


async def send_url(url):
    client = UrlServiceClient()

    # Decode the URL
    # url = urllib.parse.unquote_plus(url)

    # with open(_log_file_path(), "a") as f:
    #     f.write(f"Sending URL: {url}\n")

    try:
        response = await client.process_url(url)
    except Exception as e:
        pass
    exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--url", required=False, type=str, help="The URL of the asset to download."
    )
    parser.add_argument(
        "--serve", action="store_true", help="Run as server. For testing purpose."
    )
    args = parser.parse_args()

    if args.serve:
        asyncio.run(serve())
    elif args.url:
        url = args.url
        if len(url) == 0:
            exit(-1)

        asyncio.run(send_url(url))
    else:
        parser.print_help()
