"""
OrcaLab 资产同步服务

功能：
1. 从 DataLink 后端查询用户订阅的资产包列表
2. 检查本地已有的 uuid.pak 文件
3. 下载缺失的资产包并重命名为 uuid.pak
4. 删除既不在订阅列表也不在配置 paks 列表中的 pak 文件
"""

import json
import sys
import threading
from numpy import int64
import requests
import aiohttp
import asyncio
import pathlib
import shutil
from typing import List, Dict, Optional, Callable, Tuple
import time
import logging

from orcalab.project_util import calculate_file_sha256
from orcalab.config_service import ConfigService
from orcalab.exception import TokenExpiredException, ConnectionFailedException

logger = logging.getLogger(__name__)

class AssetSyncCallbacks:
    """资产同步回调接口"""
    
    def on_start(self):
        """同步开始"""
        pass
    
    def on_query_start(self):
        """开始查询订阅列表"""
        pass
    
    def on_query_complete(self, packages: List[Dict]):
        """查询完成"""
        pass
    
    def on_asset_status(self, asset_id: str, asset_name: str, file_name: str, size: int, status: str):
        """
        资产包状态
        status: 'ok' (已最新), 'download' (待下载), 'delete' (待删除)
        """
        pass

    def on_set_status(self, asset_id: str, asset_name: str, file_name: str, size: int, status: str):
        """
        设置资产包状态
        status: 'ok' (已最新), 'download' (待下载), 'delete' (待删除)
        """
        pass

    def on_set_name_size(self, asset_id: str, name: str, size: float):
        """
        设置资产包名字和大小
        """
        pass
    
    def on_download_start(self, asset_id: str, asset_name: str):
        """开始下载"""
        pass
    
    def on_download_progress(self, asset_id: str, progress: int64, speed: float):
        """
        下载进度
        progress: 0-100
        speed: MB/s
        """
        pass
    
    def on_download_complete(self, asset_id: str, success: bool, error: str = ""):
        """下载完成"""
        pass
    
    def on_delete(self, file_name: str):
        """删除文件"""
        pass
    
    def on_metadata_sync(self, status: str, count: int = 0, total: int = 0):
        """
        元数据同步状态
        status: 'start' (开始), 'fetching' (拉取列表), 'scanning' (扫描远端元数据), 'complete' (完成)
        count: 当前已处理数量
        total: 总数量
        """
        pass
    
    def on_complete(self, success: bool, message: str = ""):
        """同步完成"""
        pass


class AssetSyncService:
    """资产同步服务"""
    
    def __init__(self, username: str, access_token: str, base_url: str, cache_folder: pathlib.Path, downloaded_packages_folder: pathlib.Path,
                 config_paks: List[str], pak_urls: List[str] = None, timeout: int = 60, callbacks: Optional[AssetSyncCallbacks] = None,
                 verbose: bool = False, cancel_event: Optional[threading.Event] = None):
        """
        初始化资产同步服务
        
        Args:
            username: 用户名
            access_token: 访问令牌
            base_url: 后端 API 地址
            cache_folder: 本地资产包存储目录（目标目录）
            config_paks: 配置文件中的 paks 列表（绝对路径）
            pak_urls: 配置文件中的 pak_urls 列表（URL列表）
            timeout: 请求超时时间（秒）
            callbacks: 回调接口
            verbose: 是否输出详细日志
            cancel_event: 同步取消事件
        """
        self.username = username
        self.access_token = access_token
        self.base_url = base_url.rstrip('/')
        self.cache_folder = cache_folder
        self.downloaded_packages_folder = downloaded_packages_folder
        self.timeout = timeout
        self.callbacks = callbacks or AssetSyncCallbacks()
        self.verbose = verbose
        self._cancel_event = cancel_event
        self._callback_lock = threading.Lock()  # 保护回调函数的线程安全
        
        # 提取配置paks的文件名（用于后续比对）
        self.config_pak_names = set()
        for pak_path in config_paks:
            pak_file = pathlib.Path(pak_path)
            self.config_pak_names.add(pak_file.name)
        
        # 提取pak_urls的文件名（用于后续比对）
        self.pak_url_names = set()
        if pak_urls:
            for url in pak_urls:
                filename = url.split("/")[-1]
                self.pak_url_names.add(filename)
        
        if self.verbose:
            logger.info(
                "资产同步服务初始化: 用户=%s, 配置pak数=%s, pak_urls数=%s",
                self.username,
                len(self.config_pak_names),
                len(self.pak_url_names),
            )
    
    def _cancelled(self) -> bool:
        return self._cancel_event is not None and self._cancel_event.is_set()
    
    def log(self, message: str):
        """简化日志输出"""
        if self.verbose:
            logger.info(message)
    
    def get_headers(self) -> Dict[str, str]:
        """构造请求头"""
        return {
            'Authorization': f'Bearer {self.access_token}',
            'username': self.username,
            'Content-Type': 'application/json'
        }
    
    def query_subscribed_packages(self, app_version: str) -> Tuple[List[Dict], List[Dict]]:
        """
        查询用户订阅的资产包列表
        
        Returns:
            资产包列表，如果返回 'TOKEN_EXPIRED' 字符串表示 token 过期
        """
        self.callbacks.on_query_start()
        self.log("查询订阅列表...")

        if sys.platform == "win32":
            platform = "pc"
        else:
            platform = "linux"

        params = f"?version={app_version}&platform={platform}"
        
        try:
            url = f"{self.base_url}/orcalab/subscribed_packages/{params}"
            _start = time.monotonic()
            response = requests.get(url, headers=self.get_headers(), timeout=self.timeout)
            elapsed = time.monotonic() - _start
            logger.debug("HTTP GET %s/orcalab/subscribed_packages/ 耗时: %.3f 秒 (状态码: %s)", url, elapsed, response.status_code)
            
            if response.status_code == 401:
                logger.debug("认证失败（Token 可能已过期）. Status code: %d", response.status_code)
                raise TokenExpiredException("Token 已过期")
            
            if response.status_code != 200:
                logger.debug("查询失败: HTTP %d", response.status_code)
                return [],[]
            
            data = response.json()
            packages = data.get('packages', [])
            incompatible_packages = data.get('incompatiblePackages', [])
            
            self.callbacks.on_query_complete(packages)
            logger.debug(f"✓ 查询成功: {len(packages) + len(incompatible_packages)} 个资产包")
            
            return packages, incompatible_packages

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            logger.debug(f"❌ 连接资产库失败: {e}")
            raise ConnectionFailedException("连接资产库失败")
            
        except TokenExpiredException:
            raise
            
        except Exception as e:
            logger.debug(f"❌ 查询失败: {e}")
            return [],[]
    
    async def check_local_packages(self, packages: List[Dict], incompatible_packages: List[Dict]) -> tuple[List[Dict], List[str]]:
        """
        检查本地资产包
        
        Returns:
            (需要下载的列表, 需要删除的列表)
        """
        missing_packages = []
        
        self.base_pkg_map = {}
        self.patch_to_base_map = {}
        self.base_to_patch_map = {}
        self.download_info_cache = {}
        required_pkg_ids = set()

        for pkg in packages:
            required_pkg_ids.add(pkg['id'])
            file_name = pkg.get('fileName') or pkg.get('file_name', f"{pkg['id']}.pak")
            if "_patch_" in file_name:
                continue
            base_name = file_name.removesuffix(".pak")
            self.base_pkg_map[base_name] = pkg['id']

        for pkg in packages:
            file_name = pkg.get('fileName') or pkg.get('file_name', f"{pkg['id']}.pak")

            if "_patch_" not in file_name:
                continue

            base_name = file_name.split("_patch_")[0]
            base_pkg_id = self.base_pkg_map.get(base_name)
            if base_pkg_id:
                self.patch_to_base_map[pkg['id']] = base_pkg_id
                # 构建全量包到增量包的映射
                if base_pkg_id not in self.base_to_patch_map:
                    self.base_to_patch_map[base_pkg_id] = []
                self.base_to_patch_map[base_pkg_id].append(pkg)

        # 并发获取所有下载信息
        if required_pkg_ids:
            tasks = []
            pkg_id_list = list(required_pkg_ids)
            for pkg_id in pkg_id_list:
                tasks.append(self.get_download_url(pkg_id))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                pkg_id = pkg_id_list[i]
                if isinstance(result, Exception):
                    logger.debug(f"获取 {pkg_id} 的下载信息失败: {result}")
                    self.download_info_cache[pkg_id] = None
                else:
                    self.download_info_cache[pkg_id] = result

        for pkg in packages:
            file_name = pkg.get('fileName') or pkg.get('file_name', f"{pkg['id']}.pak")
            local_path = self.cache_folder / file_name
            downloaded_path = self.downloaded_packages_folder / file_name
            pkg_id = pkg['id']
            pkg_name = pkg['name']
            size = pkg['size']
            
            download_info = self.download_info_cache[pkg_id]

            if "_patch_" in file_name:
                pkg_id = self.patch_to_base_map[pkg['id']] 
            else:
                self.callbacks.on_asset_status(pkg_id, pkg_name, file_name, size, 'download')

            download_info = self.download_info_cache.get(pkg_id)            
            if download_info == None:
                self.callbacks.on_set_status(pkg_id, 'failed')
                logger.debug("%s 获取 download url 失败", file_name)
                continue
            cloud_file_sha256 = download_info.get("sha256")
            if local_path.exists():
                if cloud_file_sha256:
                    local_file_sha256 = calculate_file_sha256(local_path)
                    if local_file_sha256.lower() == cloud_file_sha256:
                        self.callbacks.on_set_status(pkg_id, 'ok')
                        logger.info("%s 已最新", file_name)
                    else:
                        self.callbacks.on_set_status(pkg_id, 'download')
                        missing_packages.append(pkg)
                        logger.info("%s hash 不匹配，需重新下载", file_name)
                else:
                    self.callbacks.on_set_status(pkg_id, 'ok')
                    logger.info("%s 已最新", file_name)
            elif downloaded_path.exists():
                if cloud_file_sha256:
                    local_file_sha256 = calculate_file_sha256(downloaded_path)
                    if local_file_sha256.lower() == cloud_file_sha256:
                        shutil.copy2(downloaded_path, local_path)
                        self.callbacks.on_set_status(pkg_id, 'ok')
                        logger.info("%s 已最新", file_name)
                    else:
                        self.callbacks.on_set_status(pkg_id, 'download')
                        missing_packages.append(pkg)
                        logger.info("%s hash 不匹配，需重新下载", file_name)
                else:
                    shutil.copy2(downloaded_path, local_path)
                    self.callbacks.on_set_status(pkg_id, 'ok')
                    logger.info("%s 已最新", file_name)
            else:
                self.callbacks.on_set_status(pkg_id, 'download')
                missing_packages.append(pkg)
                logger.info("%s 需要下载", file_name)

        for pkg in incompatible_packages:
            file_name = pkg.get('fileName') or pkg.get('file_name', f"{pkg['id']}.pak")
            pkg_id = pkg['id']
            pkg_name = pkg['name']
            if "_patch_" not in file_name:
                self.callbacks.on_asset_status(pkg_id, pkg_name, file_name, 0, 'incompatible')
            logger.info("%s 没有与当前版本兼容的资产", file_name)
        
        # 检查需要删除的文件
        subscribed_file_names = set()
        for pkg in packages:
            file_name = pkg.get('fileName') or pkg.get('file_name', f"{pkg['id']}.pak")
            subscribed_file_names.add(file_name)
        
        # 合并所有需要保留的文件名：订阅包、手工pak、pak_urls
        keep_file_names = subscribed_file_names | self.config_pak_names | self.pak_url_names
        
        to_delete = []
        for pak_file in self.cache_folder.glob("*.pak"):
            file_name = pak_file.name
            if file_name not in keep_file_names:
                to_delete.append(file_name)
                self.callbacks.on_delete(file_name)
                self.log(f"✗ {file_name} 待删除")
        
        return missing_packages, to_delete
    
    async def get_download_url(self, package_id: str) -> Optional[Dict]:
        """获取资产包的下载链接"""
        if sys.platform == "win32":
            platform = "pc"
        else:
            platform = "linux"
        params = f"?platform={platform}"

        try:
            url = f"{self.base_url}/orcalab/package/{package_id}/download_url/{params}"
            _start = time.monotonic()
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.get_headers(), timeout=aiohttp.ClientTimeout(total=self.timeout)) as response:
                    elapsed = time.monotonic() - _start
                    logger.debug("HTTP GET %s 耗时: %.3f 秒 (状态码: %s)", url, elapsed, response.status)
                    
                    if response.status != 200:
                        logger.debug(f"❌ 获取下载链接失败: HTTP {response.status}")
                        return None
                    
                    return await response.json()
            
        except Exception as e:
            logger.debug(f"❌ 获取下载链接失败: {e}")
            return None
    
    def get_image_url(self, asset_id: str) -> str:
        get_asset_metadata_url = f"{self.base_url}/asset/{asset_id}/"
        _start = time.monotonic()
        response = requests.get(get_asset_metadata_url, headers=self.get_headers(), timeout=self.timeout)
        elapsed = time.monotonic() - _start
        logger.debug("HTTP GET %s/asset/%s/ 耗时: %.3f 秒 (状态码: %s)", self.base_url, asset_id, elapsed, response.status_code)
        if response.status_code != 200:
            logger.debug(f"Get image url failed. Asset Id: {asset_id} Status: {response.status_code}")
            return None
        asset_metadata = response.json()
        return json.dumps(asset_metadata, ensure_ascii=False, indent=2)

    def check_metadata(self, packages: List[Dict], to_delete: List[str], to_missing: List[Dict]):
        metadata_path = self.cache_folder / "metadata.json"
        if not metadata_path.exists():
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump({}, f)
        raw = metadata_path.read_bytes()
        for enc in ('utf-8-sig', 'utf-8', 'gbk', 'latin-1'):
            try:
                metadata = json.loads(raw.decode(enc))
                break
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
        else:
            metadata = {}
        
        # 清理已删除的元数据
        for to_delete_pak in to_delete:
            pak_id = to_delete_pak.removesuffix('.pak')
            if pak_id in metadata.keys():
                del metadata[pak_id]
        
        to_update_metadata = set()
        package_infos = [
            {
                "id": package['id'],
                "name": package['name'],
                "revisionKind": package.get('revisionKind')
            }
            for package in packages
        ]

        patch_names = {
            p["name"] for p in package_infos if p["revisionKind"] == "patch"
        }
        
        for package_info in package_infos:
            pkg_id = package_info["id"]
            name = package_info["name"]
            kind = package_info["revisionKind"]

            if kind == "patch":
                if pkg_id not in metadata:
                    to_update_metadata.add(pkg_id)
            else:
                if name not in patch_names and pkg_id not in metadata:
                    to_update_metadata.add(pkg_id)

        package_ids = [package['id'] for package in package_infos]


        missing_pak_infos = [
            {
                "id": to_missing_pak['id'],
                "name": to_missing_pak['name'],
                "revisionKind": to_missing_pak.get('revisionKind')
            }
            for to_missing_pak in to_missing
        ]

        missing_patch_names = {
            p["name"] for p in missing_pak_infos if p["revisionKind"] == "patch"
        }
        for missing_pak_info in missing_pak_infos:
            pkg_id = missing_pak_info["id"]
            name = missing_pak_info["name"]
            kind = missing_pak_info["revisionKind"]

            if kind == "patch":
                to_update_metadata.add(missing_pak_info['id'])
                if missing_pak_info['id'] in metadata.keys():
                    del metadata[missing_pak_info['id']]
            else:
                if name not in missing_patch_names:
                    to_update_metadata.add(missing_pak_info['id'])
                    if missing_pak_info['id'] in metadata.keys():
                        del metadata[missing_pak_info['id']]
        
        keys = list(metadata.keys())
        for key in keys:
            if key not in package_ids and key not in to_update_metadata:
                del metadata[key]

        to_update_metadata_json = {}
        for package_id in to_update_metadata:
            to_update_metadata_json[package_id] = {}
        
        if len(to_update_metadata) == 0:
            self.callbacks.on_metadata_sync('complete', 0, 0)
        else:
            # 开始同步元数据
            self.callbacks.on_metadata_sync('start', 0, len(to_update_metadata))
            self.callbacks.on_metadata_sync('fetching', 0, 0)
            
            _start = time.monotonic()
            response = requests.get(f"{self.base_url}/meta/?isPublished=true", headers=self.get_headers(), timeout=self.timeout)
            elapsed = time.monotonic() - _start
            logger.debug("HTTP GET %s/meta/?isPublished=true 耗时: %.3f 秒 (状态码: %s)", self.base_url, elapsed, response.status_code)
            if response.status_code != 200:
                logger.debug(f"❌ 获取metadata失败: HTTP {response.status_code}")
                return
            remote_metadata_published = response.json()
            
            _start = time.monotonic()
            response = requests.get(f"{self.base_url}/meta/?isPublished=false", headers=self.get_headers(), timeout=self.timeout)
            elapsed = time.monotonic() - _start
            logger.debug("HTTP GET %s/meta/?isPublished=false 耗时: %.3f 秒 (状态码: %s)", self.base_url, elapsed, response.status_code)
            if response.status_code != 200:
                logger.debug(f"❌ 获取metadata失败: HTTP {response.status_code}")
                return
            remote_metadata_unpublished = response.json()
            remote_metadata = remote_metadata_published + remote_metadata_unpublished

            updated_count = 0
            total_remote = len(remote_metadata)
            for index, sub_metadata in enumerate(remote_metadata, start=1):
                if self._cancelled():
                    logger.debug("元数据同步已取消")
                    return
                if total_remote > 0 and (index == 1 or index % 20 == 0 or index == total_remote):
                    self.callbacks.on_metadata_sync('scanning', index, total_remote)
                if sub_metadata['id'] in to_update_metadata:
                    for key, value in sub_metadata.items():
                        if sub_metadata['id'] not in metadata.keys():
                            metadata[sub_metadata['id']] = {}
                            metadata[sub_metadata['id']]['children'] = []
                        metadata[sub_metadata['id']][key] = value
                    updated_count += 1
                    
                if 'parentPackageId' in sub_metadata and sub_metadata['parentPackageId'] in to_update_metadata:
                    if sub_metadata['parentPackageId'] not in metadata.keys():
                        metadata[sub_metadata['parentPackageId']] = {}
                        metadata[sub_metadata['parentPackageId']]['children'] = []
                    metadata[sub_metadata['parentPackageId']]['children'].append(sub_metadata)
                    
                    asset_id = sub_metadata['id']
                    image_url = self.get_image_url(asset_id)
                    if image_url is not None:
                        image_url = json.loads(image_url)
                        sub_metadata['pictures'] = image_url['pictures']
            
            # 完成同步
            self.callbacks.on_metadata_sync('complete', updated_count, len(to_update_metadata))
            
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    async def _download_package_group(self, group_id: str, packages: List[Dict]) -> Tuple[int, int]:
        """
        下载一组包（全量包及其增量包）
        
        Args:
            group_id: 组ID（全量包ID）
            packages: 包列表，已按全量包在前、增量包在后排序
            
        Returns:
            (成功数量, 失败数量)
        """
        success_count = 0
        fail_count = 0
        
        # 计算总大小
        total_group_size = 0
        for pkg in packages:
            download_info = self.download_info_cache.get(pkg['id'])
            if not download_info:
                print("未找到缓存的下载信息，正在获取:", pkg['id'])
                download_info = await self.get_download_url(pkg['id'])
                self.download_info_cache[pkg['id']] = download_info
            if download_info:
                total_group_size += download_info.get('size', 0)
        
        # 记录已下载大小
        downloaded_group_size = 0
        start_time = time.time()
        
        for pkg in packages:
            if self._cancelled():
                break
            
            package_id = pkg['id']
            file_name = pkg.get('fileName') or pkg.get('file_name', f"{pkg['id']}.pak")
            
            download_info = self.download_info_cache.get(package_id)
            if not download_info:
                download_info = await self.get_download_url(package_id)
            
            if not download_info:
                fail_count += 1
                with self._callback_lock:
                    self.callbacks.on_download_complete(group_id, False, "无法获取下载链接")
                continue
            
            download_url = download_info.get('downloadUrl') or download_info.get('download_url')
            size = download_info.get('size')
            cloud_file_sha256 = download_info.get("sha256")
            
            # 下载当前包
            success = await self._download_package_with_group_progress(
                group_id, file_name, download_url, cloud_file_sha256,
                total_group_size, downloaded_group_size, start_time
            )
            
            if success:
                success_count += 1
                downloaded_group_size += size
            else:
                # 失败后重试一次
                retry_success = await self._download_package_with_group_progress(
                    group_id, file_name, download_url, cloud_file_sha256,
                    total_group_size, downloaded_group_size, start_time
                )
                if retry_success:
                    success_count += 1
                    downloaded_group_size += size
                else:
                    fail_count += 1
        
        if not self._cancelled():
            with self._callback_lock:
                self.callbacks.on_download_complete(group_id, success_count > 0 and fail_count == 0)
        
        return success_count, fail_count
    
    async def _download_package_with_group_progress(self, group_id: str, file_name: str, download_url: str, 
                                           cloud_file_sha256: str, total_group_size: int, downloaded_group_size: int, 
                                           group_start_time: float) -> bool:
        """
        下载单个包并更新组进度
        
        Args:
            group_id: 组ID（全量包ID）
            file_name: 文件名
            download_url: 下载链接
            cloud_file_sha256: 文件哈希
            total_group_size: 组总大小
            downloaded_group_size: 组已下载大小
            group_start_time: 组开始下载时间
            
        Returns:
            是否下载成功
        """
        try:
            local_path = self.cache_folder / file_name
            temp_path = self.cache_folder / f"{file_name}.tmp"
            
            # 线程安全的回调调用
            with self._callback_lock:
                self.callbacks.on_set_name_size(group_id, file_name, float(total_group_size))
                self.callbacks.on_download_start(group_id)
            
            # 异步流式下载
            _start = time.monotonic()
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url, timeout=aiohttp.ClientTimeout(total=self.timeout * 2)) as response:
                    elapsed = time.monotonic() - _start
                    logger.debug("HTTP GET %s 首包耗时: %.3f 秒 (状态码: %s)", download_url, elapsed, response.status)

                    if response.status != 200:
                        logger.debug(f"❌ 下载失败: HTTP {response.status}")
                        with self._callback_lock:
                            self.callbacks.on_download_complete(group_id, False, f"HTTP {response.status}")
                        return False
                    
                    current_downloaded = 0
                    last_update_time = time.time()
                    
                    with open(temp_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            if self._cancelled():
                                logger.debug(f"下载已取消: {file_name}")
                                if temp_path.exists():
                                    temp_path.unlink()
                                with self._callback_lock:
                                    self.callbacks.on_download_complete(group_id, False, "已取消")
                                return False
                            if chunk:
                                f.write(chunk)
                                current_downloaded += len(chunk)
                                
                                # 更新组进度（每0.1秒更新一次）
                                current_time = time.time()
                                if total_group_size > 0 and current_time - last_update_time >= 0.1:
                                    total_downloaded = downloaded_group_size + current_downloaded
                                    progress = int64((total_downloaded / total_group_size) * 100)
                                    elapsed = current_time - group_start_time
                                    speed = (total_downloaded / (1024 * 1024)) / elapsed if elapsed > 0 else 0
                                    with self._callback_lock:
                                        self.callbacks.on_download_progress(group_id, progress, speed)
                                    last_update_time = current_time
            
            if self._cancelled():
                self.log(f"下载已取消: {file_name}")
                if temp_path.exists():
                    temp_path.unlink()
                with self._callback_lock:
                    self.callbacks.on_download_complete(group_id, False, "已取消")
                return False
            
            # 最终组进度更新
            if total_group_size > 0:
                total_downloaded = downloaded_group_size + current_downloaded
                progress = int64((total_downloaded / total_group_size) * 100)
                with self._callback_lock:
                    self.callbacks.on_download_progress(group_id, progress, 0)
            
            # 文件完整性验证
            local_file_sha256 = calculate_file_sha256(temp_path)
            if cloud_file_sha256:
                if local_file_sha256.lower() != cloud_file_sha256:
                    with self._callback_lock:
                        self.callbacks.on_download_complete(group_id, False, "incomplete")
                    return False
            
            # 重命名
            if local_path.exists():
                local_path.unlink()
            temp_path.rename(local_path)
            
            logger.debug(f"✓ {file_name} 下载完成")
            return True
            
        except Exception as e:
            logger.debug(f"❌ 下载失败: {e}")
            if 'temp_path' in locals() and temp_path.exists():
                temp_path.unlink()
            with self._callback_lock:
                self.callbacks.on_download_complete(group_id, False, str(e))
            return False
    
    def clean_unsubscribed_packages(self, to_delete: List[str]):
        """删除不需要的pak文件"""
        for file_name in to_delete:
            try:
                pak_file = self.cache_folder / file_name
                shutil.copy2(pak_file, self.downloaded_packages_folder / file_name)
                pak_file.unlink()
                logger.debug(f"✓ 已删除 {file_name}")
            except Exception as e:
                logger.debug(f"✗ 删除失败 {file_name}: {e}")
    
    async def sync_packages(self, init_paks: bool = False) -> bool:
        """
        同步资产包（主流程）
        
        Args:
            init_paks: 是否初始化pak包（如果为true，会在查询订阅列表后清除既不在手工列表也不在订阅列表中的包）
        
        Returns:
            同步是否成功，如果返回 'TOKEN_EXPIRED' 表示 token 过期
        """
        self.callbacks.on_start()

        # 根据版本号获取对应的资产ID
        config_service = ConfigService()
        app_version = config_service.app_version()
        
        # 1. 查询订阅列表

        try:
            packages, incompatible_packages = self.query_subscribed_packages(app_version)
        except TokenExpiredException:
            self.log("⚠️  Token 已过期，保留现有资产包，以离线模式启动")
            self.callbacks.on_complete(False, "Token 已过期")
            return False
        except ConnectionFailedException:
            self.log("⚠️  连接资产库失败，保留现有资产包，进入离线模式")
            self.callbacks.on_complete(False, "连接资产库失败，进入离线模式")
            return False
        
        if self._cancelled():
            self.log("同步已由用户取消")
            self.callbacks.on_complete(False, "用户已取消")
            return False
        
        # 收集订阅列表中的文件名
        subscribed_file_names = set()
        if packages:
            for pkg in packages:
                file_name = pkg.get('fileName') or pkg.get('file_name', f"{pkg['id']}.pak")
                subscribed_file_names.add(file_name)
        
        # 如果 init_paks=true，清除既不在手工列表、订阅列表也不在pak_urls列表中的包
        if init_paks:
            # 合并手工pak、订阅pak和pak_urls的文件名（要保留的文件）
            keep_file_names = subscribed_file_names | self.config_pak_names | self.pak_url_names
            
            from orcalab.project_util import move_packages_to_downloaded_folder
            if keep_file_names:
                # 把要删除的包复制到 downloaded_packages_folder 中
                move_packages_to_downloaded_folder(exclude_names=list(keep_file_names))
                self.log(f"已清除不在保留列表中的pak文件（保留 {len(keep_file_names)} 个包：{len(self.config_pak_names)} 个手工 + {len(subscribed_file_names)} 个订阅 + {len(self.pak_url_names)} 个pak_urls）")
            else:
                # 如果没有任何要保留的包，迁移所有
                move_packages_to_downloaded_folder()
                self.log("已清除所有pak文件（没有任何需要保留的包）")
        
        # 2. 检查本地文件
        missing_packages, to_delete = await self.check_local_packages(packages, incompatible_packages)
        
        if self._cancelled():
            self.log("同步已由用户取消")
            self.callbacks.on_complete(False, "用户已取消")
            return False
        
        # 3. 下载缺失的资产包
        success_count = 0
        fail_count = 0
        
        # 按全量包分组，将全量包和其增量包放在一起
        base_package_groups = {}
        for pkg in missing_packages:
            package_id = pkg['id']
            file_name = pkg.get('fileName') or pkg.get('file_name', f"{pkg['id']}.pak")
            
            # 确定分组ID（使用全量包ID）
            if "_patch_" in file_name and pkg['id'] in self.patch_to_base_map:
                group_id = self.patch_to_base_map[pkg['id']]
            else:
                group_id = package_id
            
            if group_id not in base_package_groups:
                base_package_groups[group_id] = []
            base_package_groups[group_id].append(pkg)
        
        # 并发下载每组包（每组内按顺序下载：先全量包，后增量包）
        if base_package_groups:
            # 创建异步任务列表
            download_tasks = []
            for group_id, group_packages in base_package_groups.items():
                if self._cancelled():
                    break
                # 创建异步任务
                download_tasks.append(self._download_package_group(group_id, group_packages))
            
            # 执行异步任务
            if download_tasks:
                results = await asyncio.gather(*download_tasks, return_exceptions=True)
                for result in results:
                    if self._cancelled():
                        break
                    if isinstance(result, tuple):
                        group_success, group_fail = result
                        success_count += group_success
                        fail_count += group_fail
                    else:
                        logger.debug(f"❌ 下载组任务异常: {result}")
                        fail_count += 1
        
        if self._cancelled():
            self.log("同步已由用户取消（跳过元数据与本地清理）")
            self.callbacks.on_complete(False, "用户已取消")
            return False
        
        # check metadata
        self.check_metadata(packages, to_delete, missing_packages)

        if self._cancelled():
            self.log("同步已由用户取消（跳过本地清理）")
            self.callbacks.on_complete(False, "用户已取消")
            return False

        # 4. 清理不需要的文件
        self.clean_unsubscribed_packages(to_delete)
        
        # 5. 完成
        message = f"下载: {success_count} 成功, {fail_count} 失败; 删除: {len(to_delete)} 个"
        self.callbacks.on_complete(True, message)
        self.log(f"同步完成: {message}")
        
        return True


def sync_assets(config_service, callbacks: Optional[AssetSyncCallbacks] = None, verbose: bool = False,
                cancel_event: Optional[threading.Event] = None) -> bool:
    """
    资产同步入口函数
    
    Args:
        config_service: 配置服务实例
        callbacks: 回调接口
        verbose: 是否输出详细日志
        cancel_event: 若设置 is_set()，同步逻辑将尽快中止
    
    Returns:
        同步是否成功
    """
    from orcalab.project_util import get_cache_folder, get_downloaded_packages_folder
    
    # 检查是否启用资产同步
    if not config_service.datalink_enable_sync():
        if verbose:
            logger.info("资产同步已禁用")
        return True
    
    # 检查认证信息
    username = config_service.datalink_username()
    token = config_service.datalink_token()
    
    if not username or not token:
        if verbose:
            logger.warning("⚠️  DataLink 认证信息未配置，跳过资产同步")
        return True
    
    # 获取配置
    base_url = config_service.datalink_base_url()
    cache_folder = get_cache_folder()
    downloaded_packages_folder = get_downloaded_packages_folder()
    config_paks = config_service.paks()
    pak_urls = config_service.pak_urls()
    timeout = config_service.datalink_timeout()
    init_paks = config_service.init_paks()
    
    # 创建同步服务并执行同步
    sync_service = AssetSyncService(
        username=username,
        access_token=token,
        base_url=base_url,
        cache_folder=cache_folder,
        downloaded_packages_folder=downloaded_packages_folder,
        config_paks=config_paks,
        pak_urls=pak_urls,
        timeout=timeout,
        callbacks=callbacks,
        verbose=verbose,
        cancel_event=cancel_event,
    )
    
    # 运行异步同步方法
    return asyncio.run(sync_service.sync_packages(init_paks=init_paks))
