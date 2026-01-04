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
from numpy import int64
import requests
import pathlib
from typing import List, Dict, Optional, Callable, Tuple
import time
import logging

from orcalab.config_service import ConfigService
from orcalab.exception import TokenExpiredException

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
        status: 'start' (开始), 'progress' (进度), 'complete' (完成)
        count: 当前已处理数量
        total: 总数量
        """
        pass
    
    def on_complete(self, success: bool, message: str = ""):
        """同步完成"""
        pass


class AssetSyncService:
    """资产同步服务"""
    
    def __init__(self, username: str, access_token: str, base_url: str, cache_folder: pathlib.Path, 
                 config_paks: List[str], pak_urls: List[str] = None, timeout: int = 60, callbacks: Optional[AssetSyncCallbacks] = None,
                 verbose: bool = False):
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
        """
        self.username = username
        self.access_token = access_token
        self.base_url = base_url.rstrip('/')
        self.cache_folder = cache_folder
        self.timeout = timeout
        self.callbacks = callbacks or AssetSyncCallbacks()
        self.verbose = verbose
        
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
            response = requests.get(url, headers=self.get_headers(), timeout=self.timeout)
            
            if response.status_code == 401:
                self.log("❌ 认证失败（Token 可能已过期）")
                raise TokenExpiredException("Token 已过期")
            
            if response.status_code != 200:
                self.log(f"❌ 查询失败: HTTP {response.status_code}")
                return [],[]
            
            data = response.json()
            packages = data.get('packages', [])
            incompatible_packages = data.get('incompatiblePackages', [])
            
            self.callbacks.on_query_complete(packages)
            self.log(f"✓ 查询成功: {len(packages) + len(incompatible_packages)} 个资产包")
            
            return packages, incompatible_packages
            
        except Exception as e:
            self.log(f"❌ 查询失败: {e}")
            return [],[]
    
    def check_local_packages(self, packages: List[Dict], incompatible_packages: List[Dict]) -> tuple[List[Dict], List[str]]:
        """
        检查本地资产包
        
        Returns:
            (需要下载的列表, 需要删除的列表)
        """
        missing_packages = []
        
        for pkg in packages:
            file_name = pkg.get('fileName') or pkg.get('file_name', f"{pkg['id']}.pak")
            local_path = self.cache_folder / file_name
            pkg_id = pkg['id']
            pkg_name = pkg['name']
            size = pkg['size']
            
            if local_path.exists():
                local_size = local_path.stat().st_size
                if local_size == size:
                    self.callbacks.on_asset_status(pkg_id, pkg_name, file_name, size, 'ok')
                    self.log(f"✓ {file_name} 已最新")
                else:
                    self.callbacks.on_asset_status(pkg_id, pkg_name, file_name, size, 'download')
                    missing_packages.append(pkg)
                    self.log(f"⬇ {file_name} 大小不匹配，需重新下载")
            else:
                self.callbacks.on_asset_status(pkg_id, pkg_name, file_name, size, 'download')
                missing_packages.append(pkg)
                self.log(f"⬇ {file_name} 需要下载")

        for pkg in incompatible_packages:
            file_name = pkg.get('fileName') or pkg.get('file_name', f"{pkg['id']}.pak")
            pkg_id = pkg['id']
            pkg_name = pkg['name']
            self.callbacks.on_asset_status(pkg_id, pkg_name, file_name, 0, 'incompatible')
            self.log(f"⬇ {file_name} 没有与当前版本兼容的资产")
        
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
    
    def get_download_url(self, package_id: str) -> Optional[Dict]:
        """获取资产包的下载链接"""
        try:
            url = f"{self.base_url}/orcalab/package/{package_id}/download_url/"
            response = requests.get(url, headers=self.get_headers(), timeout=self.timeout)
            
            if response.status_code != 200:
                self.log(f"❌ 获取下载链接失败: HTTP {response.status_code}")
                return None
            
            return response.json()
            
        except Exception as e:
            self.log(f"❌ 获取下载链接失败: {e}")
            return None
    
    def get_image_url(self, asset_id: str) -> str:
        get_asset_metadata_url = f"{self.base_url}/asset/{asset_id}/"
        response = requests.get(get_asset_metadata_url, headers=self.get_headers(), timeout=self.timeout)
        if response.status_code != 200:
            return None
        asset_metadata = response.json()
        return json.dumps(asset_metadata, ensure_ascii=False, indent=2)

    def check_metadata(self, packages: List[Dict], to_delete: List[str], to_missing: List[Dict]):
        metadata_path = self.cache_folder / "metadata.json"
        if not metadata_path.exists():
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump({}, f)
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # 清理已删除的元数据
        for to_delete_pak in to_delete:
            pak_id = to_delete_pak.removesuffix('.pak')
            if pak_id in metadata.keys():
                del metadata[pak_id]
        
        to_update_metadata = set()
        package_ids = [package['id'] for package in packages]
        for package_id in package_ids:
            if package_id not in metadata.keys():
                to_update_metadata.add(package_id)

        for to_missing_pak in to_missing:
            to_update_metadata.add(to_missing_pak['id'])
            if to_missing_pak['id'] in metadata.keys():
                del metadata[to_missing_pak['id']]
        
        keys = list(metadata.keys())
        for key in keys:
            if key not in package_ids and key not in to_update_metadata:
                del metadata[key]

        to_update_metadata_json = {}
        for package_id in to_update_metadata:
            to_update_metadata_json[package_id] = {}
        
        if len(to_update_metadata) > 0:
            # 开始同步元数据
            self.callbacks.on_metadata_sync('start', 0, len(to_update_metadata))
            
            response = requests.get(f"{self.base_url}/meta/?isPublished=true", headers=self.get_headers(), timeout=self.timeout)
            if response.status_code != 200:
                self.log(f"❌ 获取metadata失败: HTTP {response.status_code}")
                return
            remote_metadata_published = response.json()
            
            response = requests.get(f"{self.base_url}/meta/?isPublished=false", headers=self.get_headers(), timeout=self.timeout)
            if response.status_code != 200:
                self.log(f"❌ 获取metadata失败: HTTP {response.status_code}")
                return
            remote_metadata_unpublished = response.json()
            remote_metadata = remote_metadata_published + remote_metadata_unpublished

            updated_count = 0
            for sub_metadata in remote_metadata:
                if sub_metadata['id'] in to_update_metadata:
                    for key, value in sub_metadata.items():
                        if sub_metadata['id'] not in metadata.keys():
                            metadata[sub_metadata['id']] = {}
                            metadata[sub_metadata['id']]['children'] = []
                        metadata[sub_metadata['id']][key] = value
                    updated_count += 1
                    # 更新进度
                    self.callbacks.on_metadata_sync('progress', updated_count, len(to_update_metadata))
                    
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

    def download_package(self, package_id: str, file_name: str, download_url: str, expected_size: int) -> bool:
        """下载资产包"""
        try:
            local_path = self.cache_folder / file_name
            temp_path = self.cache_folder / f"{file_name}.tmp"
            
            self.callbacks.on_download_start(package_id, file_name)
            
            # 流式下载
            response = requests.get(download_url, stream=True, timeout=self.timeout * 2)
            
            if response.status_code != 200:
                self.log(f"❌ 下载失败: HTTP {response.status_code}")
                self.callbacks.on_download_complete(package_id, False, f"HTTP {response.status_code}")
                return False
            
            total_size = int64(response.headers.get('content-length', 0))
            downloaded_size = 0
            start_time = time.time()
            last_update_time = start_time
            
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # 更新进度（每0.1秒更新一次）
                        current_time = time.time()
                        if total_size > 0 and current_time - last_update_time >= 0.1:
                            progress = int64((downloaded_size / total_size) * 100)
                            elapsed = current_time - start_time
                            speed = (downloaded_size / (1024 * 1024)) / elapsed if elapsed > 0 else 0
                            self.callbacks.on_download_progress(package_id, progress, speed)
                            last_update_time = current_time
            
            # 最终进度更新
            if total_size > 0:
                self.callbacks.on_download_progress(package_id, 100, 0)
            
            # 重命名
            if local_path.exists():
                local_path.unlink()
            temp_path.rename(local_path)
            
            self.callbacks.on_download_complete(package_id, True)
            self.log(f"✓ {file_name} 下载完成")
            return True
            
        except Exception as e:
            self.log(f"❌ 下载失败: {e}")
            if temp_path.exists():
                temp_path.unlink()
            self.callbacks.on_download_complete(package_id, False, str(e))
            return False
    
    def clean_unsubscribed_packages(self, to_delete: List[str]):
        """删除不需要的pak文件"""
        for file_name in to_delete:
            try:
                pak_file = self.cache_folder / file_name
                pak_file.unlink()
                self.log(f"✓ 已删除 {file_name}")
            except Exception as e:
                self.log(f"✗ 删除失败 {file_name}: {e}")
    
    def sync_packages(self, init_paks: bool = False) -> bool:
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
            
            if keep_file_names:
                from orcalab.project_util import clear_cache_packages
                clear_cache_packages(exclude_names=list(keep_file_names))
                self.log(f"已清除不在保留列表中的pak文件（保留 {len(keep_file_names)} 个包：{len(self.config_pak_names)} 个手工 + {len(subscribed_file_names)} 个订阅 + {len(self.pak_url_names)} 个pak_urls）")
            else:
                # 如果没有任何要保留的包，清除所有
                from orcalab.project_util import clear_cache_packages
                clear_cache_packages()
                self.log("已清除所有pak文件（没有任何需要保留的包）")
        
        # 2. 检查本地文件
        missing_packages, to_delete = self.check_local_packages(packages, incompatible_packages)
        
        # 3. 下载缺失的资产包
        success_count = 0
        fail_count = 0
        
        for pkg in missing_packages:
            package_id = pkg['id']
            file_name = pkg.get('fileName') or pkg.get('file_name', f"{pkg['id']}.pak")
            
            # 获取下载链接
            download_info = self.get_download_url(package_id)
            
            if not download_info:
                fail_count += 1
                self.callbacks.on_download_complete(package_id, False, "无法获取下载链接")
                continue
            
            download_url = download_info.get('downloadUrl') or download_info.get('download_url')
            size = download_info.get('size')
            
            # 下载
            if self.download_package(package_id, file_name, download_url, size):
                success_count += 1
            else:
                fail_count += 1
        
        # check metadata
        self.check_metadata(packages, to_delete, missing_packages)

        # 4. 清理不需要的文件
        self.clean_unsubscribed_packages(to_delete)
        
        # 5. 完成
        message = f"下载: {success_count} 成功, {fail_count} 失败; 删除: {len(to_delete)} 个"
        self.callbacks.on_complete(True, message)
        self.log(f"同步完成: {message}")
        
        return True


def sync_assets(config_service, callbacks: Optional[AssetSyncCallbacks] = None, verbose: bool = False) -> bool:
    """
    资产同步入口函数
    
    Args:
        config_service: 配置服务实例
        callbacks: 回调接口
        verbose: 是否输出详细日志
    
    Returns:
        同步是否成功
    """
    from orcalab.project_util import get_cache_folder
    
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
        config_paks=config_paks,
        pak_urls=pak_urls,
        timeout=timeout,
        callbacks=callbacks,
        verbose=verbose
    )
    
    return sync_service.sync_packages(init_paks=init_paks)
