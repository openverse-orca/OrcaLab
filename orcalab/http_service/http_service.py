import os
import logging
import time
from orcalab.http_service.http_bus import HttpServiceRequest, HttpServiceRequestBus
from typing import List, Dict, Optional, Callable, Any
from typing_extensions import override
from orcalab.token_storage import TokenStorage
from orcalab.project_util import get_cache_folder
from orcalab.config_service import ConfigService
from concurrent.futures import ThreadPoolExecutor
import aiohttp
import asyncio
import functools
import json
import requests
import sys


logger = logging.getLogger(__name__)


def _log_request_time(method: str, url: str, start: float, status: int = None):
    elapsed = time.monotonic() - start
    status_str = f" (状态码: {status})" if status else ""
    logger.debug("HTTP %s %s 耗时: %.3f 秒%s", method, url, elapsed, status_str)

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
        self.version = ConfigService()._get_package_version()
        self._executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="http_service")
        self._upload_futures = []
        self.platform = "linux" if sys.platform == "linux" else "pc"

    @require_online
    @override
    async def get_all_metadata(self, output: List[str] = None) -> str:
        metadata_url = f"{self.base_url}/meta/?isPublished=true"
        metadata_url_unpublished = f"{self.base_url}/meta/?isPublished=false"
        async with aiohttp.ClientSession() as session:
            _start = time.monotonic()
            async with session.get(metadata_url, headers=self._get_headers()) as response:
                _log_request_time("GET", metadata_url, _start, response.status)
                if response.status != 200:
                    logger.debug(f"get all metadata failed. Status: {response.status}. MetadataUrl: {metadata_url}")
                    return None
                metadata_published = await response.json()
                _start = time.monotonic()
                async with session.get(metadata_url_unpublished, headers=self._get_headers()) as response:
                    _log_request_time("GET", metadata_url_unpublished, _start, response.status)
                    if response.status != 200:
                        logger.debug(f"get all metadata failed. Status: {response.status} MetadataUrl: {metadata_url_unpublished}")
                        return None
                    metadata_unpublished = await response.json()
                metadata = metadata_published + metadata_unpublished
                metadata = json.dumps(metadata, ensure_ascii=False, indent=2)
                if output is not None:
                    output.append(metadata)
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
        subscriptions_url = f"{self.base_url}/subscriptions/?version={self.version}&platform={self.platform}"
        async with aiohttp.ClientSession() as session:
            _start = time.monotonic()
            async with session.get(subscriptions_url, headers=self._get_headers()) as response:
                _log_request_time("GET", subscriptions_url, _start, response.status)
                if response.status != 200:
                    logger.debug(f"get subscriptions failed. Status: {response.status}")
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
            _start = time.monotonic()
            response = requests.post(post_asset_thumbnail_url, files=files, headers=headers)
            _log_request_time("POST", post_asset_thumbnail_url, _start, response.status_code)
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
            _start = time.monotonic()
            async with session.get(asset_url) as response:
                _log_request_time("GET", asset_url, _start, response.status)
                if response.status != 200:
                    logger.debug(f"get asset thumbnail to cache failed. Status: {response.status}")
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
            _start = time.monotonic()
            async with session.get(get_asset_metadata_url, headers=self._get_headers()) as response:
                _log_request_time("GET", get_asset_metadata_url, _start, response.status)
                if response.status != 200:
                    logger.debug(f"get image url failed. Status: {response.status}")
                    return None
                asset_metadata = await response.json()
                return json.dumps(asset_metadata, ensure_ascii=False, indent=2)

    @require_online
    @override
    async def get_my_metadata(self, output: List[str] = None) -> str:
        mymeta_url = f"{self.base_url}/mymeta/"
        async with aiohttp.ClientSession() as session:
            _start = time.monotonic()
            async with session.get(mymeta_url, headers=self._get_headers()) as response:
                _log_request_time("GET", mymeta_url, _start, response.status)
                if response.status != 200:
                    logger.debug(f"get my metadata failed. Status: {response.status}")
                    return None
                my_metadata = await response.json()
                my_metadata = json.dumps(my_metadata, ensure_ascii=False, indent=2)
                if output is not None:
                    output.append(my_metadata)
                return my_metadata

    @require_online
    @override
    async def get_asset_detail(self, asset_id: str, output: List[str] = None) -> str:
        asset_id = (asset_id or "").strip()
        if not asset_id:
            msg = json.dumps({"code": 400, "message": "asset_id 为空"}, ensure_ascii=False)
            if output is not None:
                output.append(msg)
            return msg

        asset_url = f"{self.base_url}/asset/{asset_id}/"
        async with aiohttp.ClientSession() as session:
            _start = time.monotonic()
            async with session.get(asset_url, headers=self._get_headers()) as response:
                _log_request_time("GET", asset_url, _start, response.status)
                if response.status != 200:
                    msg = json.dumps({"code": response.status, "message": f"获取资产详情失败"}, ensure_ascii=False)
                    if output is not None:
                        output.append(msg)
                    return msg
                asset_detail = await response.json()
                asset_detail = json.dumps(asset_detail, ensure_ascii=False, indent=2)
                if output is not None:
                    output.append(asset_detail)
                return asset_detail

    @require_online
    @override
    async def post_asset_subscribe(self, asset_package_id: str, output: List[str] = None) -> str:
        asset_package_id = (asset_package_id or "").strip()
        if not asset_package_id:
            msg = json.dumps({"success": False, "message": "asset_package_id 为空"}, ensure_ascii=False)
            if output is not None:
                output.append(msg)
            return msg

        url = f"{self.base_url}/asset/{asset_package_id}/subscribe/"
        async with aiohttp.ClientSession() as session:
            _start = time.monotonic()
            async with session.post(url, headers=self._get_headers(), json={}) as response:
                _log_request_time("POST", url, _start, response.status)
                body = await response.text()
                try:
                    body_json = json.loads(body) if body.strip() else {}
                except json.JSONDecodeError:
                    logger.exception("post_asset_subscribe: 请求异常")
                    body_json = {"raw": body}
                ok = response.status in (200, 201, 204)
                msg = json.dumps(
                    {
                        "success": ok,
                        "http_status": response.status,
                        "package_id": asset_package_id,
                        "body": body_json,
                    },
                    ensure_ascii=False,
                )
                if output is not None:
                    output.append(msg)
                return msg

    @require_online
    @override
    async def post_asset_unsubscribe(self, asset_package_id: str, output: List[str] = None) -> str:
        asset_package_id = (asset_package_id or "").strip()
        if not asset_package_id:
            msg = json.dumps({"success": False, "message": "asset_package_id 为空"}, ensure_ascii=False)
            if output is not None:
                output.append(msg)
            return msg

        url = f"{self.base_url}/asset/{asset_package_id}/unsubscribe/"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self._get_headers(), json={}) as response:
                body = await response.text()
                try:
                    body_json = json.loads(body) if body.strip() else {}
                except json.JSONDecodeError:
                    body_json = {"raw": body}
                ok = response.status in (200, 201, 204)
                msg = json.dumps(
                    {
                        "success": ok,
                        "http_status": response.status,
                        "package_id": asset_package_id,
                        "body": body_json,
                    },
                    ensure_ascii=False,
                )
                if output is not None:
                    output.append(msg)
                return msg

    @require_online
    @override
    async def get_asset_subscription_status(self, asset_package_id: str, output: List[str] = None) -> str:
        asset_package_id = (asset_package_id or "").strip()
        if not asset_package_id:
            msg = json.dumps({"success": False, "message": "asset_package_id 为空"}, ensure_ascii=False)
            if output is not None:
                output.append(msg)
            return msg

        url = f"{self.base_url}/asset/{asset_package_id}/subscription_status/"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._get_headers()) as response:
                body = await response.text()
                try:
                    body_json = json.loads(body) if body.strip() else {}
                except json.JSONDecodeError:
                    body_json = {"raw": body}
                ok = response.status == 200
                msg = json.dumps(
                    {
                        "success": ok,
                        "http_status": response.status,
                        "package_id": asset_package_id,
                        "body": body_json,
                    },
                    ensure_ascii=False,
                )
                if output is not None:
                    output.append(msg)
                return msg

    @require_online
    @override
    async def post_generate_task(self, task_data: dict, output: List[str] = None) -> str:
        if not task_data:
            msg = json.dumps({"code": 400, "message": "task_data 为空"}, ensure_ascii=False)
            if output is not None:
                output.append(msg)
            return msg

        url = f"{self.base_url}/generate/"
        async with aiohttp.ClientSession() as session:
            image_path = task_data.pop("image_path", None)
            data = aiohttp.FormData()
            for key, value in task_data.items():
                if value is not None:
                    data.add_field(key, str(value))
            if image_path:
                import os
                if not os.path.isfile(image_path):
                    msg = json.dumps({"code": 400, "message": f"图片文件不存在: {image_path}"}, ensure_ascii=False)
                    if output is not None:
                        output.append(msg)
                    return msg
                data.add_field("image", open(image_path, "rb"), filename=os.path.basename(image_path), content_type="image/png")
            headers = self._get_headers(include_content_type=False)
            _start = time.monotonic()
            async with session.post(url, headers=headers, data=data) as response:
                _log_request_time("POST", url, _start, response.status)
                body = await response.text()
                try:
                    body_json = json.loads(body) if body.strip() else {}
                except json.JSONDecodeError:
                    logger.exception("post_generate_task: 请求异常")
                    body_json = {"raw": body}
                ok = response.status in (200, 201, 202)
                msg = json.dumps(
                    {
                        "success": ok,
                        "http_status": response.status,
                        "body": body_json,
                    },
                    ensure_ascii=False,
                )
                if output is not None:
                    output.append(msg)
                return msg

    @require_online
    @override
    async def get_generate_task_status(self, task_id: str, output: List[str] = None) -> str:
        task_id = (task_id or "").strip()
        if not task_id:
            msg = json.dumps({"code": 400, "message": "task_id 为空"}, ensure_ascii=False)
            if output is not None:
                output.append(msg)
            return msg

        url = f"{self.base_url}/generate/status/{task_id}/"
        async with aiohttp.ClientSession() as session:
            _start = time.monotonic()
            async with session.get(url, headers=self._get_headers()) as response:
                _log_request_time("GET", url, _start, response.status)
                body = await response.text()
                try:
                    body_json = json.loads(body) if body.strip() else {}
                except json.JSONDecodeError:
                    logger.exception("get_generate_task_status: 请求异常")
                    body_json = {"raw": body}
                ok = response.status == 200
                msg = json.dumps(
                    {
                        "success": ok,
                        "http_status": response.status,
                        "body": body_json,
                    },
                    ensure_ascii=False,
                )
                if output is not None:
                    output.append(msg)
                return msg

    @require_online
    @override
    async def get_user_generate_tasks(self, output: List[str] = None) -> str:
        url = f"{self.base_url}/generate/user_tasks/"
        async with aiohttp.ClientSession() as session:
            _start = time.monotonic()
            async with session.get(url, headers=self._get_headers()) as response:
                _log_request_time("GET", url, _start, response.status)
                body = await response.text()
                try:
                    body_json = json.loads(body) if body.strip() else {}
                except json.JSONDecodeError:
                    logger.exception("get_user_generate_tasks: 请求异常")
                    body_json = {"raw": body}
                ok = response.status == 200
                msg = json.dumps(
                    {
                        "success": ok,
                        "http_status": response.status,
                        "body": body_json,
                    },
                    ensure_ascii=False,
                )
                if output is not None:
                    output.append(msg)
                return msg

    @require_online
    @override
    async def post_upload_generate_usdz(self, task_data: dict, output: List[str] = None) -> str:
        if not task_data:
            msg = json.dumps({"code": 400, "message": "task_data 为空"}, ensure_ascii=False)
            if output is not None:
                output.append(msg)
            return msg

        url = f"{self.base_url}/upload/generate_usdz/"
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            for key, value in task_data.items():
                if value is not None:
                    data.add_field(key, str(value))
            headers = self._get_headers(include_content_type=False)
            _start = time.monotonic()
            async with session.post(url, headers=headers, data=data) as response:
                _log_request_time("POST", url, _start, response.status)
                body = await response.text()
                try:
                    body_json = json.loads(body) if body.strip() else {}
                except json.JSONDecodeError:
                    logger.exception("post_upload_generate_usdz: 请求异常")
                    body_json = {"raw": body}
                ok = response.status in (200, 201, 202)
                msg = json.dumps(
                    {
                        "success": ok,
                        "http_status": response.status,
                        "body": body_json,
                    },
                    ensure_ascii=False,
                )
                if output is not None:
                    output.append(msg)
                return msg

    @require_online
    @override
    async def post_cancel_asset_zip(self, task_id: str, output: List[str] = None) -> str:
        task_id = (task_id or "").strip()
        if not task_id:
            msg = json.dumps({"code": 400, "message": "task_id 为空"}, ensure_ascii=False)
            if output is not None:
                output.append(msg)
            return msg

        url = f"{self.base_url}/cancel_asset_zip/{task_id}/"
        async with aiohttp.ClientSession() as session:
            _start = time.monotonic()
            async with session.post(url, headers=self._get_headers(), json={}) as response:
                _log_request_time("POST", url, _start, response.status)
                body = await response.text()
                try:
                    body_json = json.loads(body) if body.strip() else {}
                except json.JSONDecodeError:
                    logger.exception("post_cancel_asset_zip: 请求异常")
                    body_json = {"raw": body}
                ok = response.status == 200
                msg = json.dumps(
                    {
                        "success": ok,
                        "http_status": response.status,
                        "body": body_json,
                    },
                    ensure_ascii=False,
                )
                if output is not None:
                    output.append(msg)
                return msg

    @require_online
    @override
    async def post_check_asset_version(self, version_data: dict, output: List[str] = None) -> str:
        if not version_data:
            msg = json.dumps({"code": 400, "message": "version_data 为空"}, ensure_ascii=False)
            if output is not None:
                output.append(msg)
            return msg

        url = f"{self.base_url}/check-asset-version/"
        async with aiohttp.ClientSession() as session:
            _start = time.monotonic()
            async with session.post(url, headers=self._get_headers(), json=version_data) as response:
                _log_request_time("POST", url, _start, response.status)
                body = await response.text()
                try:
                    body_json = json.loads(body) if body.strip() else {}
                except json.JSONDecodeError:
                    logger.exception("post_check_asset_version: 请求异常")
                    body_json = {"raw": body}
                ok = response.status == 200
                msg = json.dumps(
                    {
                        "success": ok,
                        "http_status": response.status,
                        "body": body_json,
                    },
                    ensure_ascii=False,
                )
                if output is not None:
                    output.append(msg)
                return msg

    @require_online
    @override
    async def post_upload_asset_zip(self, upload_data: dict, output: List[str] = None) -> str:
        if not upload_data:
            msg = json.dumps({"code": 400, "message": "upload_data 为空"}, ensure_ascii=False)
            if output is not None:
                output.append(msg)
            return msg

        url = f"{self.base_url}/upload/asset_zip/"
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            for key, value in upload_data.items():
                if value is not None:
                    data.add_field(key, str(value))
            headers = self._get_headers(include_content_type=False)
            _start = time.monotonic()
            async with session.post(url, headers=headers, data=data) as response:
                _log_request_time("POST", url, _start, response.status)
                body = await response.text()
                try:
                    body_json = json.loads(body) if body.strip() else {}
                except json.JSONDecodeError:
                    logger.exception("post_upload_asset_zip: 请求异常")
                    body_json = {"raw": body}
                ok = response.status in (200, 201, 202)
                msg = json.dumps(
                    {
                        "success": ok,
                        "http_status": response.status,
                        "body": body_json,
                    },
                    ensure_ascii=False,
                )
                if output is not None:
                    output.append(msg)
                return msg

    @require_online
    @override
    async def post_upload_usdz(self, upload_data: dict, output: List[str] = None) -> str:
        if not upload_data:
            msg = json.dumps({"code": 400, "message": "upload_data 为空"}, ensure_ascii=False)
            if output is not None:
                output.append(msg)
            return msg

        url = f"{self.base_url}/upload/usdz/"
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            for key, value in upload_data.items():
                if value is not None:
                    data.add_field(key, str(value))
            headers = self._get_headers(include_content_type=False)
            _start = time.monotonic()
            async with session.post(url, headers=headers, data=data) as response:
                _log_request_time("POST", url, _start, response.status)
                body = await response.text()
                try:
                    body_json = json.loads(body) if body.strip() else {}
                except json.JSONDecodeError:
                    logger.exception("post_upload_usdz: 请求异常")
                    body_json = {"raw": body}
                ok = response.status in (200, 201, 202)
                msg = json.dumps(
                    {
                        "success": ok,
                        "http_status": response.status,
                        "body": body_json,
                    },
                    ensure_ascii=False,
                )
                if output is not None:
                    output.append(msg)
                return msg

    @require_online
    @override
    async def post_upload_xml(self, upload_data: dict, output: List[str] = None) -> str:
        if not upload_data:
            msg = json.dumps({"code": 400, "message": "upload_data 为空"}, ensure_ascii=False)
            if output is not None:
                output.append(msg)
            return msg

        url = f"{self.base_url}/upload/xml/"
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            for key, value in upload_data.items():
                if value is not None:
                    data.add_field(key, str(value))
            headers = self._get_headers(include_content_type=False)
            _start = time.monotonic()
            async with session.post(url, headers=headers, data=data) as response:
                _log_request_time("POST", url, _start, response.status)
                body = await response.text()
                try:
                    body_json = json.loads(body) if body.strip() else {}
                except json.JSONDecodeError:
                    logger.exception("post_upload_xml: 请求异常")
                    body_json = {"raw": body}
                ok = response.status in (200, 201, 202)
                msg = json.dumps(
                    {
                        "success": ok,
                        "http_status": response.status,
                        "body": body_json,
                    },
                    ensure_ascii=False,
                )
                if output is not None:
                    output.append(msg)
                return msg

    @require_online
    @override
    async def get_task_chain_progress(self, task_chain_id: str, output: List[str] = None) -> str:
        task_chain_id = (task_chain_id or "").strip()
        if not task_chain_id:
            msg = json.dumps({"code": 400, "message": "task_chain_id 为空"}, ensure_ascii=False)
            if output is not None:
                output.append(msg)
            return msg

        url = f"{self.base_url}/task_chain_progress/{task_chain_id}/"
        async with aiohttp.ClientSession() as session:
            _start = time.monotonic()
            async with session.get(url, headers=self._get_headers()) as response:
                _log_request_time("GET", url, _start, response.status)
                body = await response.text()
                try:
                    body_json = json.loads(body) if body.strip() else {}
                except json.JSONDecodeError:
                    logger.exception("get_task_chain_progress: 请求异常")
                    body_json = {"raw": body}
                ok = response.status == 200
                msg = json.dumps(
                    {
                        "success": ok,
                        "http_status": response.status,
                        "body": body_json,
                    },
                    ensure_ascii=False,
                )
                if output is not None:
                    output.append(msg)
                return msg

    @require_online
    @override
    async def post_save_asset_draft(self, task_id: str, draft_data: dict, output: List[str] = None) -> str:
        task_id = (task_id or "").strip()
        if not task_id:
            msg = json.dumps({"code": 400, "message": "task_id 为空"}, ensure_ascii=False)
            if output is not None:
                output.append(msg)
            return msg

        url = f"{self.base_url}/save_asset_draft/{task_id}/"
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            for key, value in draft_data.items():
                if value is not None:
                    data.add_field(key, str(value))
            headers = self._get_headers(include_content_type=False)
            _start = time.monotonic()
            async with session.post(url, headers=headers, data=data) as response:
                _log_request_time("POST", url, _start, response.status)
                body = await response.text()
                try:
                    body_json = json.loads(body) if body.strip() else {}
                except json.JSONDecodeError:
                    logger.exception("post_save_asset_draft: 请求异常")
                    body_json = {"raw": body}
                ok = response.status == 200
                msg = json.dumps(
                    {
                        "success": ok,
                        "http_status": response.status,
                        "body": body_json,
                    },
                    ensure_ascii=False,
                )
                if output is not None:
                    output.append(msg)
                return msg

    @require_online
    @override
    async def delete_asset(self, asset_id: str, output: List[str] = None) -> str:
        asset_id = (asset_id or "").strip()
        if not asset_id:
            msg = json.dumps({"code": 400, "message": "asset_id 为空"}, ensure_ascii=False)
            if output is not None:
                output.append(msg)
            return msg
        
        # 获取资产详情，校验作者
        detail_out: list[str] = []
        await self.get_asset_detail(asset_id, detail_out)
        if not detail_out:
            msg = json.dumps({"success": False, "message": "无法获取资产详情，请确认资产ID正确"}, ensure_ascii=False)
            if output is not None:
                output.append(msg)
            return msg
        
        try:
            detail_raw = json.loads(detail_out[0])
            detail_data = detail_raw if isinstance(detail_raw, dict) and "code" not in detail_raw else detail_raw.get("data", detail_raw)
            asset_author = detail_data.get("author", "") if isinstance(detail_data, dict) else ""
            asset_name = detail_data.get("name", asset_id) if isinstance(detail_data, dict) else asset_id
        except (json.JSONDecodeError, AttributeError):
            asset_author = ""
            asset_name = asset_id

        if asset_author and self.username and asset_author != self.username:
            msg = json.dumps(
                {
                    "success": False,
                    "message": f"无权删除资产「{asset_name}」：该资产作者为「{asset_author}」，当前用户为「{self.username}」，只能删除自己的资产",
                },
                ensure_ascii=False,
            )
            if output is not None:
                output.append(msg)
            return msg

        url = f"{self.base_url}/delete/{asset_id}/"
        async with aiohttp.ClientSession() as session:
            _start = time.monotonic()
            async with session.delete(url, headers=self._get_headers()) as response:
                _log_request_time("DELETE", url, _start, response.status)
                body = await response.text()
                try:
                    body_json = json.loads(body) if body.strip() else {}
                except json.JSONDecodeError:
                    logger.exception("delete_asset: 请求异常")
                    body_json = {"raw": body}
                ok = response.status == 200
                msg = json.dumps(
                    {
                        "success": ok,
                        "http_status": response.status,
                        "body": body_json,
                    },
                    ensure_ascii=False,
                )
                if output is not None:
                    output.append(msg)
                return msg

    @override
    def is_admin(self) -> bool:
        if not self.check_online():
            logger.warning("is_admin: 用户离线")
            return False
        
        is_admin_url = f"{self.base_url}/is_admin/"
        try:
            with requests.Session() as session:
                _start = time.monotonic()
                response = session.get(is_admin_url, headers=self._get_headers())
                _log_request_time("GET", is_admin_url, _start, response.status_code)
                if response.status_code != 200:
                    logger.warning("is_admin: 请求失败，状态码: %s", response.status_code)
                    return False
                is_admin = response.json()
                return is_admin['isAdmin']
        except Exception as e:
            logger.exception("is_admin: 请求异常: %s", e)
            return False

    @require_online
    @override
    async def search_assets(self, search_data: dict, output: List[str] = None) -> str:
        if not search_data:
            msg = json.dumps({"code": 400, "message": "search_data 为空"}, ensure_ascii=False)
            if output is not None:
                output.append(msg)
            return msg

        url = f"{self.base_url}/search/"
        async with aiohttp.ClientSession() as session:
            image_path = search_data.pop("image_path", None)
            data = aiohttp.FormData()
            for key, value in search_data.items():
                if value is not None:
                    data.add_field(key, str(value))
            if image_path:
                if not os.path.isfile(image_path):
                    msg = json.dumps({"code": 400, "message": f"图片文件不存在: {image_path}"}, ensure_ascii=False)
                    if output is not None:
                        output.append(msg)
                    return msg
                with open(image_path, "rb") as f:
                    data.add_field("image", f.read(), filename=os.path.basename(image_path), content_type="image/png")
            headers = self._get_headers(include_content_type=False)
            _start = time.monotonic()
            async with session.post(url, headers=headers, data=data) as response:
                _log_request_time("POST", url, _start, response.status)
                body = await response.text()
                try:
                    body_json = json.loads(body) if body.strip() else {}
                except json.JSONDecodeError:
                    logger.exception("search_assets: 响应解析失败")
                    body_json = {"raw": body}
                ok = response.status in (200, 201, 202)
                msg = json.dumps(
                    {
                        "success": ok,
                        "http_status": response.status,
                        "body": body_json,
                    },
                    ensure_ascii=False,
                )
                if output is not None:
                    output.append(msg)
                return msg


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


