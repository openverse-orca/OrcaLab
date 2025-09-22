import grpc
from orcalab.asset_service_bus import AssetServiceRequestBus
import orcalab.protos.url_service_pb2_grpc as url_service_pb2_grpc
import orcalab.protos.url_service_pb2 as url_service_pb2

import argparse
import asyncio
import sys
import urllib.parse
import os

address = "localhost:50651"
scheme_name = "orca"


class UrlServiceServer(url_service_pb2_grpc.GrpcServiceServicer):
    def __init__(self):
        self.server = grpc.aio.server()
        url_service_pb2_grpc.add_GrpcServiceServicer_to_server(self, self.server)
        self.server.add_insecure_port(address)

    async def start(self):
        register_protocol()

        await self.server.start()

    async def stop(self):
        await self.server.stop(0)

    async def ProcessUrl(self, request, context):
        response = url_service_pb2.ProcessUrlResponse()
        raw_url = request.url
        print(f"Received ProcessUrl request: {raw_url}")

        prefix = "orca://download-asset?url="
        if raw_url.startswith(prefix):
            url = raw_url[len(prefix) :]
            print(f"Extracted URL: {url}")
            await AssetServiceRequestBus().download_asset_to_cache(url)

        response.status_code = url_service_pb2.StatusCode.Success
        return response


class UrlServiceClient:
    def __init__(self):
        self.channel = grpc.aio.insecure_channel(address)
        self.stub = url_service_pb2_grpc.GrpcServiceStub(self.channel)

    def _check_response(self, response):
        if response.status_code != url_service_pb2.StatusCode.Success:
            raise Exception(f"Request failed. {response.error_message}")

    async def process_url(self, url):
        request = url_service_pb2.ProcessUrlRequest(url=url)
        response = await self.stub.ProcessUrl(request)
        return response


async def serve():
    server = UrlServiceServer()
    await server.start()
    await server.server.wait_for_termination()


async def send_url(url):
    client = UrlServiceClient()

    # Decode the URL
    url = urllib.parse.unquote_plus(url)

    response = await client.process_url(url)
    print(f"ProcessUrl response: {response.status_code}")


def is_protocol_registered_win32():
    import winreg

    try:
        key_path = rf"SOFTWARE\Classes\{scheme_name}"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False


def register_protocol_win32():
    import winreg

    executable = sys.executable

    # We do not need a console window for handling the protocol
    if executable.endswith("python.exe"):
        executable = executable.replace("python.exe", "pythonw.exe")

    this_file = __file__

    try:
        # Create the main key for the custom scheme
        key_path = rf"SOFTWARE\Classes\{scheme_name}"
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f"URL:{scheme_name} Protocol")
        winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
        winreg.CloseKey(key)

        # Create the 'shell\open\command' subkeys
        command_key_path = rf"{key_path}\shell\open\command"
        command_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, command_key_path)
        winreg.SetValueEx(
            command_key,
            "",
            0,
            winreg.REG_SZ,
            f'"{executable}" "{this_file}" --url "%1"',
        )
        winreg.CloseKey(command_key)

        print(f"URI scheme '{scheme_name}' registered successfully.")
    except Exception as e:
        print(f"Error registering URI scheme: {e}")


def unregister_protocol_win32():
    import winreg

    try:
        key_path = rf"SOFTWARE\Classes\{scheme_name}"
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"{key_path}\shell\open\command")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"{key_path}\shell\open")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"{key_path}\shell")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
        print(f"URI scheme '{scheme_name}' unregistered successfully.")
    except Exception as e:
        print(f"Error unregistering URI scheme: {e}")


def _desktop_entry_file_path():
    home = os.path.expanduser("~")
    return os.path.join(
        home, f".local/share/applications/{scheme_name}-url-handler.desktop"
    )


def is_registered_protocol_linux():
    if os.path.exists(_desktop_entry_file_path()):
        return True
    return False


def register_protocol_linux():

    executable = sys.executable

    # We do not need a console window for handling the protocol
    if executable.endswith("python"):
        executable = executable.replace("python", "pythonw")

    this_file = __file__

    # https://specifications.freedesktop.org/desktop-entry-spec/latest/

    text = f"""
[Desktop Entry]
Name=Orca URL Handler
Exec={executable} {this_file} --url %u  
Type=Application
NoDisplay=true
MimeType=x-scheme-handler/{scheme_name};
        """

    with open(_desktop_entry_file_path(), "w", encoding="utf-8") as f:
        f.write(text)


def unregister_protocol_linux():
    file = _desktop_entry_file_path()

    if not os.path.exists(file):
        return

    try:
        os.remove(file)
    except Exception as e:
        print(f"Error unregistering URI scheme: {e}")


def register_protocol():
    if sys.platform == "win32":
        register_protocol_win32()
    else:
        register_protocol_linux()


def unregister_protocol():
    if sys.platform == "win32":
        unregister_protocol_win32()
    else:
        unregister_protocol_linux()


def is_protocol_registered():
    if sys.platform == "win32":
        return is_protocol_registered_win32()
    else:
        return is_registered_protocol_linux()


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

    if args.serve:
        asyncio.run(serve())
    elif args.register:
        register_protocol()
    elif args.unregister:
        unregister_protocol()
    elif args.query:
        if is_protocol_registered():
            print(f"1")
        else:
            print(f"0")
    elif args.url:
        url = args.url
        if len(url) == 0:
            exit(-1)

        print(f"Sending URL to server: {url}")
        asyncio.run(send_url(url))
    else:
        parser.print_help()
