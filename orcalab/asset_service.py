from orcalab.asset_service_bus import AssetServiceRequest, AssetServiceRequestBus
from orcalab.application_bus import ApplicationRequestBus

import aiohttp
import pathlib
import aiofiles

from typing import override


class AssetService(AssetServiceRequest):

    def __init__(self):
        super().__init__()
        AssetServiceRequestBus.connect(self)

    def destroy(self):
        AssetServiceRequestBus.disconnect(self)

    @override
    async def download_asset_to_file(self, url: str, file: str) -> None:
        async with aiofiles.open(file, "wb") as f:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise Exception(
                            f"Failed to download asset. Status code: {response.status}"
                        )
                    data = await response.read()
                    await f.write(data)

    @override
    async def download_asset_to_cache(self, url: str) -> None:
        cache_folder = []
        ApplicationRequestBus().get_cache_folder(cache_folder)

        if len(cache_folder) == 0:
            raise Exception("Cache folder is not set.")

        cache_folder: str = cache_folder[0]

        await self.download_asset_to_file(url, cache_folder + "/" + "test1.txt")
