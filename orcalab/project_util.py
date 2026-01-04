import os
import json
from typing import List, Dict, Optional
import pathlib
import sys
import shutil
import hashlib
import pickle
import aiohttp
import aiofiles
import asyncio
import logging


project_id = "{3DB8A56E-2458-4543-93A1-1A41756B97DA}"

logger = logging.getLogger(__name__)


def get_project_dir():
    project_dir = pathlib.Path.home() / "Orca" / "OrcaLab" / "DefaultProject"
    return project_dir


def get_orca_studio_root() -> pathlib.Path:
    """获取 OrcaStudio 项目的根目录"""
    if sys.platform == "win32":
        local_appdata = os.getenv("LOCALAPPDATA")
        if local_appdata:
            base_path = pathlib.Path(local_appdata)
        else:
            raise EnvironmentError("LOCALAPPDATA environment variable is not set.")
    else:
        base_path = pathlib.Path.home()
    return base_path / "Orca" / "OrcaStudio" / project_id


def check_project_folder():

    project_dir = get_project_dir()
    if not project_dir.exists():
        project_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Created default project folder at: %s", project_dir)

        data = {
            "project_name": "DefaultProject",
            "project_id": project_id,
            "display_name": "DefaultProject",
        }

        config_path = os.path.join(project_dir, "project.json")
        with open(config_path, "w") as f:
            json.dump(data, f, indent=4)

    get_cache_folder().mkdir(parents=True, exist_ok=True)


def get_cache_folder():
    if sys.platform == "win32":
        return get_orca_studio_root() / "Cache" / "pc"
    else:
        return get_orca_studio_root() / "Cache" / "linux"


def get_user_folder() -> pathlib.Path:
    """获取用户数据目录"""
    return get_orca_studio_root() / "user"


def get_user_log_folder() -> pathlib.Path:
    """获取日志输出目录"""
    return get_user_folder() / "log"


def get_user_scene_layout_folder() -> pathlib.Path:
    """获取缓存的场景布局目录"""
    folder = get_user_folder() / "scene_layouts"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def get_user_tmp_folder() -> pathlib.Path:
    """获取用户临时目录"""
    folder = get_user_folder() / "tmp"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def get_orcalab_cache_folder():
    """
    获取orcalab子目录的缓存文件夹路径
    pak_urls 下载的文件存储在这个子目录下
    """
    return get_cache_folder() / "orcalab"
   

def get_md5_cache_file() -> pathlib.Path:
    """获取MD5缓存文件路径"""
    cache_folder = get_cache_folder()
    return cache_folder / ".md5_cache.pkl"

def load_md5_cache() -> Dict[str, Dict]:
    """加载MD5缓存"""
    cache_file = get_md5_cache_file()
    if cache_file.exists():
        try:
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            logger.warning("Could not load MD5 cache: %s", e)
    return {}

def save_md5_cache(cache: Dict[str, Dict]):
    """保存MD5缓存"""
    cache_file = get_md5_cache_file()
    try:
        with open(cache_file, 'wb') as f:
            pickle.dump(cache, f)
    except Exception as e:
        logger.warning("Could not save MD5 cache: %s", e)

def get_file_metadata(file_path: pathlib.Path) -> Dict:
    """获取文件元数据"""
    try:
        stat = file_path.stat()
        return {
            'size': stat.st_size,
            'mtime': stat.st_mtime,
            'ctime': stat.st_ctime
        }
    except OSError:
        return {}

def calculate_file_md5(file_path: pathlib.Path) -> str:
    """计算文件的MD5值（优化版本）"""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            # 使用更大的块大小提高性能
            for chunk in iter(lambda: f.read(1024 * 1024), b""):  # 1MB chunks
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.error("Error calculating MD5 for %s: %s", file_path, e)
        return ""

def get_cached_md5(file_path: pathlib.Path, cache: Dict[str, Dict]) -> Optional[str]:
    """从缓存中获取MD5值"""
    file_key = str(file_path)
    if file_key in cache:
        cached_metadata = cache[file_key]
        current_metadata = get_file_metadata(file_path)
        
        # 检查文件是否被修改
        if (current_metadata.get('size') == cached_metadata.get('size') and
            current_metadata.get('mtime') == cached_metadata.get('mtime')):
            return cached_metadata.get('md5')
    
    return None

def files_are_identical_fast(source: pathlib.Path, target: pathlib.Path) -> Optional[bool]:
    """快速比较两个文件是否相同（使用元数据）"""
    try:
        source_stat = source.stat()
        target_stat = target.stat()
        
        # 如果文件大小不同，肯定不同
        if source_stat.st_size != target_stat.st_size:
            return False
        
        # 如果大小相同且修改时间相同，很可能相同
        if source_stat.st_mtime == target_stat.st_mtime:
            return True
        
        # 大小相同但时间不同，需要进一步检查
        return None
    except OSError:
        return False


def clear_cache_packages(exclude_names: Optional[List[str]] = None):
    """
    清除缓存目录下的pak文件
    
    Args:
        exclude_names: 要保留的文件名列表（不删除这些文件）
    """
    cache_folder = get_cache_folder()
    if not cache_folder.exists():
        return
    
    exclude_set = set(exclude_names) if exclude_names else set()
    deleted_count = 0
    
    for pak_file in cache_folder.glob("*.pak"):
        if pak_file.name not in exclude_set:
            try:
                pak_file.unlink()
                deleted_count += 1
                logger.info("Deleted %s from cache", pak_file.name)
            except Exception as e:
                logger.error("Error deleting %s: %s", pak_file.name, e)
    
    if deleted_count > 0:
        logger.info("Cleared %s pak file(s) from cache folder", deleted_count)


def copy_packages(packages: List[str]):
    """
    复制包文件到缓存目录
    将指定的pak文件复制到目标目录（不会删除已存在的其他pak文件）
    """
    cache_folder = get_cache_folder()
    cache_folder.mkdir(parents=True, exist_ok=True)
    
    # 复制指定的包文件
    for package in packages:
        package_path = pathlib.Path(package)
        if package_path.exists() and package_path.is_file():
            target_file = cache_folder / package_path.name
            try:
                shutil.copy2(package_path, target_file)  # 使用copy2保持元数据
                logger.info("Copied %s to %s", package_path.name, cache_folder)
            except Exception as e:
                logger.error("Error copying %s: %s", package_path.name, e)
        else:
            logger.warning("Package %s does not exist or is not a file.", package)


async def download_pak_from_url(url: str, target_path: pathlib.Path) -> bool:
    """
    从URL下载pak文件到指定路径
    
    Args:
        url: 下载URL
        target_path: 目标文件路径
        
    Returns:
        bool: 下载是否成功
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error("Failed to download %s. Status code: %s", url, response.status)
                    return False
                
                # 确保目标目录存在
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                # 下载文件
                async with aiofiles.open(target_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)
                
                logger.info("Downloaded %s to %s", url, target_path)
                return True
                
    except Exception as e:
        logger.error("Error downloading %s: %s", url, e)
        return False


def sync_pak_urls(pak_urls: List[str]) -> List[str]:
    """
    同步pak_urls列表到缓存目录
    确保缓存目录下的文件与pak_urls列表一致（先检查后决定删除和下载）
    
    Args:
        pak_urls: pak文件下载URL列表
        
    Returns:
        List[str]: 下载成功的文件路径列表
    """
    cache_folder = get_cache_folder()
    cache_folder.mkdir(parents=True, exist_ok=True)
    
    # 从URL列表提取预期的文件名
    expected_file_names = set()
    url_to_filename = {}
    for url in pak_urls:
        filename = url.split("/")[-1]
        expected_file_names.add(filename)
        url_to_filename[url] = filename
    
    # 检查现有文件，删除不在预期列表中的文件
    # 注意：只删除那些确定是来自pak_urls的文件（通过文件名匹配）
    deleted_count = 0
    for pak_file in cache_folder.glob("*.pak"):
        if pak_file.name not in expected_file_names:
            # 不在这里删除，因为可能还有其他来源的文件（手工pak或订阅pak）
            # pak_urls的清理会在asset_sync_service中与其他来源一起处理
            pass
    
    # 下载缺失的文件
    downloaded_files = []
    for url in pak_urls:
        filename = url_to_filename[url]
        target_path = cache_folder / filename
        
        # 如果文件已存在，检查是否需要更新（跳过下载，避免重复下载）
        if target_path.exists():
            logger.info("File %s already exists in cache, skipping download", filename)
            downloaded_files.append(str(target_path))
            continue
        
        # 同步下载
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环正在运行，创建新任务
                task = asyncio.create_task(download_pak_from_url(url, target_path))
                success = loop.run_until_complete(task)
            else:
                # 如果事件循环未运行，直接运行
                success = loop.run_until_complete(download_pak_from_url(url, target_path))
            
            if success:
                downloaded_files.append(str(target_path))
                logger.info("Downloaded %s to cache", filename)
        except Exception as e:
            logger.error("Error downloading %s: %s", url, e)
    
    return downloaded_files


def download_pak_files_sync(pak_urls: List[str]) -> List[str]:
    """
    同步下载pak文件到缓存目录（已废弃，请使用 sync_pak_urls）
    
    Args:
        pak_urls: pak文件下载URL列表
        
    Returns:
        List[str]: 下载成功的文件路径列表
    """
    return sync_pak_urls(pak_urls)
    