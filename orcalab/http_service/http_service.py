import os
import logging
from orcalab.http_service.http_bus import HttpServiceRequest, HttpServiceRequestBus
from typing import List, Dict, Optional, Callable, Any, override
from orcalab.token_storage import TokenStorage
from orcalab.project_util import get_cache_folder
from orcalab.config_service import ConfigService
from concurrent.futures import ThreadPoolExecutor
import aiohttp
import asyncio
import functools
import json
import requests


logger = logging.getLogger(__name__)

def require_online(func: Callable) -> Callable:
    """装饰器：检查在线状态，离线时跳过请求"""
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs) -> Any:
        if not self.check_online():
            return None
        return await func(self, *args, **kwargs)
    return wrapper

class HttpService(HttpServiceRequest):
    def __init__(self):
        super().__init__()
        HttpServiceRequestBus.connect(self)
        token = TokenStorage.load_token()
        self.is_online = token is not None
        if token is not None:
            self.access_token = token['access_token']
            self.refresh_token = token['refresh_token']
            self.username = token['username']
        else:
            self.access_token = None
            self.refresh_token = None
            self.username = None
        self.cache_folder = get_cache_folder()
        self.base_url = ConfigService().datalink_base_url()
        self._executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="http_service")
        self._upload_futures = []

    @require_online
    @override
    async def get_all_metadata(self, output: List[str] = None) -> str:
        metadata_url = f"{self.base_url}/meta/?isPublished=true"
        metadata_url_unpublished = f"{self.base_url}/meta/?isPublished=false"
        async with aiohttp.ClientSession() as session:
            async with session.get(metadata_url, headers=self._get_headers()) as response:
                if response.status != 200:
                    return None
                metadata_published = await response.json()
                async with session.get(metadata_url_unpublished, headers=self._get_headers()) as response:
                    if response.status != 200:
                        return None
                    metadata_unpublished = await response.json()
                metadata = metadata_published + metadata_unpublished
                metadata = json.dumps(metadata, ensure_ascii=False, indent=2)
                if output is not None:
                    output.extend(metadata)
                return metadata

    @require_online
    @override
    async def get_subscription_metadata(self, output: List[str] = None) -> str:
        all_metadata = await self.get_all_metadata()
        if all_metadata is None:
            return None
        subscriptions = await self.get_subscriptions()
        if subscriptions is None:
            return None
        metadata = json.loads(all_metadata)
        subscriptions = json.loads(subscriptions)
        subscriptions_id = [subscription['assetPackageId'] for subscription in subscriptions['subscriptions']]
        output_json = {}
        for sub_metadata in metadata:
            # pak资产包信息
            if sub_metadata['id'] in subscriptions_id:
                for key, value in sub_metadata.items():
                    if sub_metadata['id'] not in output_json.keys():
                        output_json[sub_metadata['id']] = {}
                        output_json[sub_metadata['id']]['children'] = []
                    output_json[sub_metadata['id']][key] = value
            # pak包含的资产
            if 'parentPackageId' in sub_metadata and sub_metadata['parentPackageId'] in subscriptions_id:
                if sub_metadata['parentPackageId'] not in output_json.keys():
                    output_json[sub_metadata['parentPackageId']] = {}
                    output_json[sub_metadata['parentPackageId']]['children'] = []
                output_json[sub_metadata['parentPackageId']]['children'].append(sub_metadata)
        
        # 图片url信息 - 并行执行
        tasks = []
        asset_metadata_list = []
        for sub_metadata in output_json.values():
            for asset_metadata in sub_metadata['children']:
                asset_id = asset_metadata['id']
                tasks.append(self.get_image_url(asset_id))
                asset_metadata_list.append(asset_metadata)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for asset_metadata, asset_url in zip(asset_metadata_list, results):
            if asset_url is not None and not isinstance(asset_url, Exception):
                asset_url = json.loads(asset_url)
                asset_metadata['pictures'] = asset_url['pictures']

        output_json = json.dumps(output_json, ensure_ascii=False, indent=2)
        if output is not None:
            output.extend(output_json)
        
        return output_json

    @require_online
    @override
    async def get_subscriptions(self, output: List[str] = None) -> str:
        subscriptions_url = f"{self.base_url}/subscriptions/"
        async with aiohttp.ClientSession() as session:
            async with session.get(subscriptions_url, headers=self._get_headers()) as response:
                if response.status != 200:
                    return None
                subscriptions = await response.json()
                subscriptions = json.dumps(subscriptions, ensure_ascii=False, indent=2)
                if output is not None:
                    output.extend(subscriptions)
                return subscriptions

    @require_online
    @override
    async def post_asset_thumbnail(self, asset_id: str, thumbnail_path: List[str]) -> None:
        future = self._executor.submit(self._post_asset_thumbnail, asset_id, thumbnail_path)
        self._upload_futures.append(future)

    async def wait_for_upload_finished(self) -> None:
        wrapped_futures = [asyncio.wrap_future(f) for f in self._upload_futures]
        await asyncio.gather(*wrapped_futures)
        self._upload_futures.clear()

    def _post_asset_thumbnail(self, asset_id: str, thumbnail_path: List[str]) -> None:
        post_asset_thumbnail_url = f"{self.base_url}/assets/{asset_id}/render/"
        
        files = []
        for file_path in thumbnail_path:
            try:
                if not os.path.exists(file_path):
                    logger.error("Thumbnail file not found: %s", file_path)
                    continue
                filename = os.path.basename(file_path)
                content_type = self._get_image_content_type(file_path)
                with open(file_path, 'rb') as f:
                    files.append(('files', (filename, f.read(), content_type)))
            except Exception as e:
                logger.exception("Error reading thumbnail file %s: %s", file_path, e)
                continue
        
        if not files:
            logger.error("No valid thumbnail files to upload for asset %s", asset_id)
            return
        
        try:
            headers = self._get_headers(include_content_type=False)
            response = requests.post(post_asset_thumbnail_url, files=files, headers=headers)
            if response.status_code in [200, 201, 204]:
                logger.info("Upload thumbnail success: %s, files: %s", response.status_code, thumbnail_path)
            else:
                logger.error("Upload thumbnail failed: %s, files: %s", response.status_code, thumbnail_path)
        except Exception as e:
            logger.exception("Error uploading thumbnail for asset %s: %s", asset_id, e)

    @require_online
    @override
    async def get_asset_thumbnail2cache(self, asset_url: str, asset_save_path: str) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.get(asset_url) as response:
                if response.status != 200:
                    return None
                data = await response.read()
                if not os.path.exists(os.path.dirname(asset_save_path)):
                    os.makedirs(os.path.dirname(asset_save_path), exist_ok=True)
                with open(asset_save_path, 'wb') as f:
                    f.write(data) 

    @require_online
    @override
    async def get_image_url(self, asset_id: str) -> str:
        get_asset_metadata_url = f"{self.base_url}/asset/{asset_id}/"
        async with aiohttp.ClientSession() as session:
            async with session.get(get_asset_metadata_url, headers=self._get_headers()) as response:
                if response.status != 200:
                    return None
                asset_metadata = await response.json()
                return json.dumps(asset_metadata, ensure_ascii=False, indent=2)

    @override
    def is_admin(self) -> bool:
        if not self.check_online():
            logger.warning("is_admin: 用户离线")
            return False
        
        is_admin_url = f"{self.base_url}/is_admin/"
        try:
            with requests.Session() as session:
                response = session.get(is_admin_url, headers=self._get_headers())
                if response.status_code != 200:
                    logger.warning("is_admin: 请求失败，状态码: %s", response.status_code)
                    return False
                is_admin = response.json()
                return is_admin['isAdmin']
        except Exception as e:
            logger.exception("is_admin: 请求异常: %s", e)
            return False


    def _get_headers(self, include_content_type: bool = True) -> Dict[str, str]:

        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'username': self.username,
        }
        if include_content_type:
            headers['Content-Type'] = 'application/json'
        return headers
    
    def _get_image_content_type(self, file_path: str) -> str:
        """根据文件扩展名返回对应的Content-Type"""
        ext = file_path.lower().split('.')[-1]
        content_types = {
            'png': 'image/png',
            'apng': 'image/apng',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'gif': 'image/gif',
            'webp': 'image/webp',
        }
        return content_types.get(ext, 'image/png')



    def check_online(self) -> bool:
        return self.is_online


