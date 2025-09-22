from orcalab.asset_service import AssetService


import unittest

import os

class TestAssetService(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.asset_service = AssetService()

    async def asyncTearDown(self):
        self.asset_service.destroy()

    # async def test_download_asset_to_file(self):
    #     test_url = "https://www.example.com"
    #     test_file = os.path.join(os.path.dirname(__file__), "test.html")

    #     await self.asset_service.download_asset_to_file(test_url, test_file)

    #     with open(test_file, "r", encoding="utf-8") as f:
    #         content = f.read()
    #         self.assertIn("Example Domain", content)

    async def test_download(self):
        test_url = "http://localhost:8000/hello.txt"
        test_file = os.path.join(os.path.dirname(__file__), "hello.txt")

        await self.asset_service.download_asset_to_file(test_url, test_file)

        # with open(test_file, "r", encoding="utf-8") as f:
        #     content = f.read()
        #     self.assertIn("Hello, World!", content)

if __name__ == "__main__":
    unittest.main()
