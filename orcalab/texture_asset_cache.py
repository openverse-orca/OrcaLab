import asyncio
import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

STREAMING_IMAGE_ASSET_UUID = "{3C96A826-9099-4308-A604-7B19ADBF8761}"

TEXTURE_ASSET_FETCH_CONFIG = {
    "max_retries": 5,
    "base_delay_seconds": 1,
    "backoff_multiplier": 2,
    "page_size": 2000,
    "min_asset_count": 1,
}

_texture_asset_cache_instance: "TextureAssetCache | None" = None


def get_texture_asset_cache() -> "TextureAssetCache":
    global _texture_asset_cache_instance
    if _texture_asset_cache_instance is None:
        _texture_asset_cache_instance = TextureAssetCache()
    return _texture_asset_cache_instance


class TextureAssetCache:
    def __init__(self):
        self._uuid_to_path: Dict[str, str] = {}
        self._path_to_uuid: Dict[str, str] = {}
        self._ready = False

    @property
    def is_ready(self) -> bool:
        return self._ready

    def get_path(self, uuid: str) -> str | None:
        return self._uuid_to_path.get(uuid)

    def get_uuid(self, path: str) -> str | None:
        return self._path_to_uuid.get(path)

    def get_all_items(self) -> list[Tuple[str, str]]:
        return list(self._uuid_to_path.items())

    async def initialize(self, remote_scene) -> None:
        config = TEXTURE_ASSET_FETCH_CONFIG
        max_retries = config["max_retries"]
        base_delay = config["base_delay_seconds"]
        multiplier = config["backoff_multiplier"]
        page_size = config["page_size"]
        min_asset_count = config["min_asset_count"]

        delay = base_delay
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    "纹理资产缓存加载: 第 %d/%d 次尝试...",
                    attempt,
                    max_retries,
                )

                await self._fetch_all_pages(remote_scene, page_size)

                total = len(self._uuid_to_path)
                if total >= min_asset_count:
                    self._ready = True
                    logger.info("纹理资产缓存就绪: %d 条", total)
                    return
                else:
                    logger.warning(
                        "纹理资产缓存: 仅获取到 %d 条（低于阈值 %d），等待重试...",
                        total,
                        min_asset_count,
                    )
                    self._uuid_to_path.clear()
                    self._path_to_uuid.clear()

            except Exception as e:
                logger.warning(
                    "纹理资产缓存加载失败 (第 %d 次): %s",
                    attempt,
                    e,
                )

            if attempt < max_retries:
                logger.info("纹理资产缓存: 等待 %.1f 秒后重试...", delay)
                await asyncio.sleep(delay)
                delay *= multiplier
            else:
                logger.error(
                    "纹理资产缓存: 已达最大重试次数 (%d)，纹理选择功能暂不可用",
                    max_retries,
                )
                self._ready = False

    async def _fetch_all_pages(self, remote_scene, page_size: int) -> None:
        page_index = 0
        while True:
            response = await remote_scene.get_assets_by_type_page(
                STREAMING_IMAGE_ASSET_UUID, page_index, page_size
            )

            for asset in response.assets:
                self._uuid_to_path[asset.asset_id] = asset.relative_path
                self._path_to_uuid[asset.relative_path] = asset.asset_id

            total_pages = response.total_pages
            logger.info(
                "纹理资产缓存: page=%d/%d, 本页 %d 条, 累计 %d 条",
                page_index + 1,
                total_pages,
                len(response.assets),
                len(self._uuid_to_path),
            )

            page_index += 1
            if page_index >= total_pages:
                break

    def search(self, keyword: str) -> list[Tuple[str, str]]:
        if not keyword:
            return self.get_all_items()

        keyword_lower = keyword.lower()
        results: list[Tuple[str, str]] = []
        for uuid_str, path in self._uuid_to_path.items():
            if keyword_lower in path.lower():
                results.append((uuid_str, path))
        return results