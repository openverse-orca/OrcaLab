import unittest
import asyncio
from unittest.mock import AsyncMock

from orcalab.texture_asset_cache import (
    TextureAssetCache,
    get_texture_asset_cache,
    STREAMING_IMAGE_ASSET_UUID,
    TEXTURE_ASSET_FETCH_CONFIG,
)


class MockAssetInfo:
    def __init__(self, asset_id: str, relative_path: str):
        self.asset_id = asset_id
        self.relative_path = relative_path


class MockPageResponse:
    def __init__(self, assets: list, page_index: int, total_pages: int, total_count: int):
        self.assets = assets
        self.page_index = page_index
        self.total_pages = total_pages
        self.total_count = total_count


def _make_mock_remote_scene(assets_by_page: dict[int, list[tuple[str, str]]]):
    total = sum(len(v) for v in assets_by_page.values())
    pages = len(assets_by_page)

    async def get_assets_by_type_page(asset_type_uuid, page_index, page_size):
        page_assets_raw = assets_by_page.get(page_index, [])
        page_assets = [MockAssetInfo(aid, apath) for aid, apath in page_assets_raw]
        return MockPageResponse(
            assets=page_assets,
            page_index=page_index,
            total_pages=pages,
            total_count=total,
        )

    mock = AsyncMock()
    mock.get_assets_by_type_page = get_assets_by_type_page
    return mock


class TestTextureAssetCache(unittest.TestCase):
    def test_singleton_returns_same_instance(self):
        cache1 = get_texture_asset_cache()
        cache2 = get_texture_asset_cache()
        self.assertIs(cache1, cache2)

    def test_initial_state_not_ready(self):
        cache = TextureAssetCache()
        self.assertFalse(cache.is_ready)
        self.assertIsNone(cache.get_path("any"))
        self.assertIsNone(cache.get_uuid("any"))
        self.assertEqual(cache.get_all_items(), [])

    def test_initialize_single_page(self):
        cache = TextureAssetCache()
        assets = {
            0: [
                ("{UUID-1}:0", "textures/rock.jpg.streamingimage"),
                ("{UUID-2}:0", "textures/wood.png.streamingimage"),
            ]
        }
        mock_scene = _make_mock_remote_scene(assets)

        asyncio.run(cache.initialize(mock_scene))

        self.assertTrue(cache.is_ready)
        self.assertEqual(cache.get_path("{UUID-1}:0"), "textures/rock.jpg.streamingimage")
        self.assertEqual(cache.get_path("{UUID-2}:0"), "textures/wood.png.streamingimage")
        self.assertEqual(cache.get_uuid("textures/rock.jpg.streamingimage"), "{UUID-1}:0")
        self.assertEqual(cache.get_uuid("textures/wood.png.streamingimage"), "{UUID-2}:0")
        self.assertEqual(len(cache.get_all_items()), 2)

    def test_initialize_multi_page(self):
        cache = TextureAssetCache()
        assets = {
            0: [("{UUID-1}:0", "textures/a.jpg.streamingimage")],
            1: [("{UUID-2}:0", "textures/b.jpg.streamingimage")],
            2: [("{UUID-3}:0", "textures/c.jpg.streamingimage")],
        }
        mock_scene = _make_mock_remote_scene(assets)

        asyncio.run(cache.initialize(mock_scene))

        self.assertTrue(cache.is_ready)
        self.assertEqual(len(cache.get_all_items()), 3)
        self.assertEqual(cache.get_path("{UUID-1}:0"), "textures/a.jpg.streamingimage")
        self.assertEqual(cache.get_path("{UUID-2}:0"), "textures/b.jpg.streamingimage")
        self.assertEqual(cache.get_path("{UUID-3}:0"), "textures/c.jpg.streamingimage")

    def test_initialize_empty_result(self):
        cache = TextureAssetCache()
        assets = {0: []}
        mock_scene = _make_mock_remote_scene(assets)

        config_backup = dict(TEXTURE_ASSET_FETCH_CONFIG)
        TEXTURE_ASSET_FETCH_CONFIG["min_asset_count"] = 0
        try:
            asyncio.run(cache.initialize(mock_scene))
        finally:
            TEXTURE_ASSET_FETCH_CONFIG.clear()
            TEXTURE_ASSET_FETCH_CONFIG.update(config_backup)

        self.assertTrue(cache.is_ready)
        self.assertEqual(cache.get_all_items(), [])

    def test_initialize_retry_on_failure(self):
        cache = TextureAssetCache()

        call_count = [0]

        async def failing_then_ok(asset_type_uuid, page_index, page_size):
            call_count[0] += 1
            if call_count[0] < 3:
                raise RuntimeError("gRPC not ready")
            return MockPageResponse(
                assets=[MockAssetInfo("{UUID-OK}:0", "textures/ok.jpg.streamingimage")],
                page_index=0,
                total_pages=1,
                total_count=1,
            )

        mock_scene = AsyncMock()
        mock_scene.get_assets_by_type_page = failing_then_ok

        config_backup = dict(TEXTURE_ASSET_FETCH_CONFIG)
        TEXTURE_ASSET_FETCH_CONFIG["max_retries"] = 5
        TEXTURE_ASSET_FETCH_CONFIG["base_delay_seconds"] = 0.01
        TEXTURE_ASSET_FETCH_CONFIG["backoff_multiplier"] = 1.0

        try:
            asyncio.run(cache.initialize(mock_scene))
        finally:
            TEXTURE_ASSET_FETCH_CONFIG.clear()
            TEXTURE_ASSET_FETCH_CONFIG.update(config_backup)

        self.assertTrue(cache.is_ready)
        self.assertEqual(call_count[0], 3)
        self.assertEqual(cache.get_path("{UUID-OK}:0"), "textures/ok.jpg.streamingimage")

    def test_initialize_all_retries_exhausted(self):
        cache = TextureAssetCache()

        async def always_fail(asset_type_uuid, page_index, page_size):
            raise RuntimeError("gRPC not ready")

        mock_scene = AsyncMock()
        mock_scene.get_assets_by_type_page = always_fail

        config_backup = dict(TEXTURE_ASSET_FETCH_CONFIG)
        TEXTURE_ASSET_FETCH_CONFIG["max_retries"] = 3
        TEXTURE_ASSET_FETCH_CONFIG["base_delay_seconds"] = 0.01
        TEXTURE_ASSET_FETCH_CONFIG["backoff_multiplier"] = 1.0

        try:
            asyncio.run(cache.initialize(mock_scene))
        finally:
            TEXTURE_ASSET_FETCH_CONFIG.clear()
            TEXTURE_ASSET_FETCH_CONFIG.update(config_backup)

        self.assertFalse(cache.is_ready)
        self.assertEqual(cache.get_all_items(), [])

    def test_get_path_nonexistent(self):
        cache = TextureAssetCache()
        cache._uuid_to_path = {"{UUID-1}:0": "textures/a.jpg.streamingimage"}
        self.assertIsNone(cache.get_path("{UUID-NONEXIST}:0"))

    def test_get_uuid_nonexistent(self):
        cache = TextureAssetCache()
        cache._path_to_uuid = {"textures/a.jpg.streamingimage": "{UUID-1}:0"}
        self.assertIsNone(cache.get_uuid("nonexistent.jpg"))

    def test_get_all_items_empty(self):
        cache = TextureAssetCache()
        self.assertEqual(cache.get_all_items(), [])

    def test_get_all_items_returns_correct_format(self):
        cache = TextureAssetCache()
        cache._uuid_to_path = {
            "{UUID-1}:0": "textures/a.jpg.streamingimage",
            "{UUID-2}:0": "textures/b.png.streamingimage",
        }
        items = cache.get_all_items()
        self.assertEqual(len(items), 2)
        self.assertIsInstance(items[0], tuple)
        self.assertEqual(len(items[0]), 2)

    def test_search_full_match(self):
        cache = TextureAssetCache()
        cache._uuid_to_path = {
            "{UUID-1}:0": "textures/rock.jpg.streamingimage",
            "{UUID-2}:0": "textures/wood.png.streamingimage",
            "{UUID-3}:0": "materials/rock.material",
        }
        results = cache.search("rock")
        self.assertEqual(len(results), 2)
        paths = [p for _, p in results]
        self.assertIn("textures/rock.jpg.streamingimage", paths)
        self.assertIn("materials/rock.material", paths)

    def test_search_case_insensitive(self):
        cache = TextureAssetCache()
        cache._uuid_to_path = {
            "{UUID-1}:0": "textures/Rock.jpg.streamingimage",
        }
        results = cache.search("rock")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][1], "textures/Rock.jpg.streamingimage")

    def test_search_no_match(self):
        cache = TextureAssetCache()
        cache._uuid_to_path = {
            "{UUID-1}:0": "textures/rock.jpg.streamingimage",
        }
        results = cache.search("nonexistent")
        self.assertEqual(len(results), 0)

    def test_search_empty_keyword_returns_all(self):
        cache = TextureAssetCache()
        cache._uuid_to_path = {
            "{UUID-1}:0": "textures/a.jpg.streamingimage",
            "{UUID-2}:0": "textures/b.png.streamingimage",
        }
        results = cache.search("")
        self.assertEqual(len(results), 2)

    def test_streaming_image_asset_uuid_constant(self):
        self.assertEqual(
            STREAMING_IMAGE_ASSET_UUID,
            "{3C96A826-9099-4308-A604-7B19ADBF8761}",
        )


if __name__ == "__main__":
    unittest.main()