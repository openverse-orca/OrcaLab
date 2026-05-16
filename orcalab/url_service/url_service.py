import grpc
import logging
import socket
import time
import orcalab.protos.url_service_pb2_grpc as url_service_pb2_grpc
import orcalab.protos.url_service_pb2 as url_service_pb2

from orcalab.asset_service_bus import AssetServiceRequestBus


logger = logging.getLogger(__name__)

DEFAULT_PORT = 50651
scheme_name = "orca"


def find_free_port(start_port: int | None = None) -> int:
    if start_port is not None:
        if _is_port_available(start_port):
            return start_port
        logger.warning("端口 %s 不可用，正在查找可用端口...", start_port)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        port = s.getsockname()[1]
        logger.info("找到可用端口: %s", port)
        return port


def _is_port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("localhost", port))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            return True
        except OSError:
            return False


class UrlServiceServer(url_service_pb2_grpc.GrpcServiceServicer):
    def __init__(self, port: int = DEFAULT_PORT):
        self.port = port
        self.address = f"localhost:{self.port}"
        self.server = grpc.aio.server()
        url_service_pb2_grpc.add_GrpcServiceServicer_to_server(self, self.server)
        self.server.add_insecure_port(self.address)

    async def start(self):
        await self.server.start()

    async def stop(self):
        await self.server.stop(0)

    async def ProcessUrl(self, request, context):
        response = url_service_pb2.ProcessUrlResponse()
        raw_url = request.url
        print(f"Received ProcessUrl request: {raw_url}")

        prefix = "orca://download-asset/?url="
        if raw_url.startswith(prefix):
            url = raw_url[len(prefix):]
            print(f"Extracted URL: {url}")
            await AssetServiceRequestBus().download_asset_to_cache(url)

        response.status_code = url_service_pb2.StatusCode.Success
        return response


class UrlServiceClient:
    def __init__(self, port: int = DEFAULT_PORT):
        self.address = f"localhost:{port}"
        self.channel = grpc.aio.insecure_channel(self.address)
        self.stub = url_service_pb2_grpc.GrpcServiceStub(self.channel)

    def _check_response(self, response):
        if response.status_code != url_service_pb2.StatusCode.Success:
            raise Exception(f"Request failed. {response.error_message}")

    async def process_url(self, url):
        request = url_service_pb2.ProcessUrlRequest(url=url)
        _start = time.monotonic()
        response = await self.stub.ProcessUrl(request)
        elapsed = time.monotonic() - _start
        logger.debug("gRPC ProcessUrl 耗时: %.3f 秒", elapsed)
        return response