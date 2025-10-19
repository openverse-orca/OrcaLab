"""
OrcaLab 资产同步服务

功能：
1. 从 DataLink 后端查询用户订阅的资产包列表
2. 检查本地已有的 uuid.pak 文件
3. 下载缺失的资产包并重命名为 uuid.pak
4. 删除既不在订阅列表也不在配置 paks 列表中的 pak 文件
"""

import requests
import pathlib
from typing import List, Dict, Optional, Callable
import time


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
    
    def on_download_progress(self, asset_id: str, progress: int, speed: float):
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
    
    def on_complete(self, success: bool, message: str = ""):
        """同步完成"""
        pass


class AssetSyncService:
    """资产同步服务"""
    
    def __init__(self, username: str, access_token: str, base_url: str, cache_folder: pathlib.Path, 
                 config_paks: List[str], timeout: int = 60, callbacks: Optional[AssetSyncCallbacks] = None,
                 verbose: bool = False):
        """
        初始化资产同步服务
        
        Args:
            username: 用户名
            access_token: 访问令牌
            base_url: 后端 API 地址
            cache_folder: 本地资产包存储目录（目标目录）
            config_paks: 配置文件中的 paks 列表（绝对路径）
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
        
        if self.verbose:
            print(f"资产同步服务初始化: 用户={self.username}, 配置pak数={len(self.config_pak_names)}")
    
    def log(self, message: str):
        """简化日志输出"""
        if self.verbose:
            print(message)
    
    def get_headers(self) -> Dict[str, str]:
        """构造请求头"""
        return {
            'Authorization': f'Bearer {self.access_token}',
            'username': self.username,
            'Content-Type': 'application/json'
        }
    
    def query_subscribed_packages(self) -> Optional[List[Dict]]:
        """查询用户订阅的资产包列表"""
        self.callbacks.on_query_start()
        self.log("查询订阅列表...")
        
        try:
            url = f"{self.base_url}/orcalab/subscribed_packages/"
            response = requests.get(url, headers=self.get_headers(), timeout=self.timeout)
            
            if response.status_code == 401:
                self.log("❌ 认证失败")
                return None
            
            if response.status_code != 200:
                self.log(f"❌ 查询失败: HTTP {response.status_code}")
                return None
            
            data = response.json()
            packages = data.get('packages', [])
            
            self.callbacks.on_query_complete(packages)
            self.log(f"✓ 查询成功: {len(packages)} 个资产包")
            
            return packages
            
        except Exception as e:
            self.log(f"❌ 查询失败: {e}")
            return None
    
    def check_local_packages(self, packages: List[Dict]) -> tuple[List[Dict], List[str]]:
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
        
        # 检查需要删除的文件
        subscribed_file_names = set()
        for pkg in packages:
            file_name = pkg.get('fileName') or pkg.get('file_name', f"{pkg['id']}.pak")
            subscribed_file_names.add(file_name)
        
        to_delete = []
        for pak_file in self.cache_folder.glob("*.pak"):
            file_name = pak_file.name
            if file_name not in subscribed_file_names and file_name not in self.config_pak_names:
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
            
            total_size = int(response.headers.get('content-length', 0))
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
                            progress = int((downloaded_size / total_size) * 100)
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
    
    def sync_packages(self) -> bool:
        """
        同步资产包（主流程）
        
        Returns:
            同步是否成功
        """
        self.callbacks.on_start()
        
        # 1. 查询订阅列表
        packages = self.query_subscribed_packages()
        
        if packages is None:
            self.callbacks.on_complete(False, "查询订阅列表失败")
            return False
        
        if not packages:
            self.log("没有订阅的资产包")
            # 仍然执行清理
            _, to_delete = self.check_local_packages([])
            self.clean_unsubscribed_packages(to_delete)
            self.callbacks.on_complete(True)
            return True
        
        # 2. 检查本地文件
        missing_packages, to_delete = self.check_local_packages(packages)
        
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
            print("资产同步已禁用")
        return True
    
    # 检查认证信息
    username = config_service.datalink_username()
    token = config_service.datalink_token()
    
    if not username or not token:
        if verbose:
            print("⚠️  DataLink 认证信息未配置，跳过资产同步")
        return True
    
    # 获取配置
    base_url = config_service.datalink_base_url()
    cache_folder = get_cache_folder()
    config_paks = config_service.paks()
    timeout = config_service.datalink_timeout()
    
    # 创建同步服务并执行同步
    sync_service = AssetSyncService(
        username=username,
        access_token=token,
        base_url=base_url,
        cache_folder=cache_folder,
        config_paks=config_paks,
        timeout=timeout,
        callbacks=callbacks,
        verbose=verbose
    )
    
    return sync_service.sync_packages()
