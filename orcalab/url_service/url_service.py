import grpc
import orcalab.protos.url_service_pb2_grpc as url_service_pb2_grpc
import orcalab.protos.url_service_pb2 as url_service_pb2

from orcalab.asset_service_bus import AssetServiceRequestBus


address = "localhost:50651"
scheme_name = "orca"


class UrlServiceServer(url_service_pb2_grpc.GrpcServiceServicer):
    def __init__(self):
        self.server = grpc.aio.server()
        url_service_pb2_grpc.add_GrpcServiceServicer_to_server(self, self.server)
        self.server.add_insecure_port(address)

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
