import os
import json
from typing import List, Dict, Optional
import pathlib
import sys
import shutil
import hashlib
import pickle


project_id = "{3DB8A56E-2458-4543-93A1-1A41756B97DA}"


def get_project_dir():
    project_dir = pathlib.Path.home() / "Orca" / "OrcaLab" / "DefaultProject"
    return project_dir


def check_project_folder():

    project_dir = get_project_dir()
    if not project_dir.exists():
        project_dir.mkdir(parents=True, exist_ok=True)
        print(f"Created default project folder at: {project_dir}")

        data = {
            "project_name": "DefaultProject",
            "project_id": project_id,
            "display_name": "DefaultProject",
        }

        config_path = os.path.join(project_dir, "project.json")
        with open(config_path, "w") as f:
            json.dump(data, f, indent=4)


def get_cache_folder():
    if sys.platform == "win32":
        local_appdata = os.getenv("LOCALAPPDATA")
        if local_appdata:
            return pathlib.Path(local_appdata) / "Orca" / "OrcaStudio" / project_id / "Cache" / "pc"
        else:
            raise EnvironmentError("LOCALAPPDATA environment variable is not set.")
    else:
        return pathlib.Path.home() / "Orca" / "OrcaStudio" / project_id / "Cache" / "linux"
   

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
            print(f"Warning: Could not load MD5 cache: {e}")
    return {}

def save_md5_cache(cache: Dict[str, Dict]):
    """保存MD5缓存"""
    cache_file = get_md5_cache_file()
    try:
        with open(cache_file, 'wb') as f:
            pickle.dump(cache, f)
    except Exception as e:
        print(f"Warning: Could not save MD5 cache: {e}")

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
        print(f"Error calculating MD5 for {file_path}: {e}")
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


def copy_packages(packages: List[str]):
    """
    复制包文件到缓存目录，简化版本：
    1. 删除目标目录下的所有文件
    2. 复制指定的源pak文件到目标目录
    """
    cache_folder = get_cache_folder()
    cache_folder.mkdir(parents=True, exist_ok=True)
    
    # 删除目标目录下的所有文件
    if cache_folder.exists():
        for existing_file in cache_folder.iterdir():
            if existing_file.is_file():
                try:
                    existing_file.unlink()
                    print(f"Deleted file: {existing_file.name}")
                except Exception as e:
                    print(f"Error deleting file {existing_file.name}: {e}")
    
    # 复制指定的包文件
    for package in packages:
        package_path = pathlib.Path(package)
        if package_path.exists() and package_path.is_file():
            target_file = cache_folder / package_path.name
            try:
                shutil.copy2(package_path, target_file)  # 使用copy2保持元数据
                print(f"Copied {package_path.name} to {cache_folder}")
            except Exception as e:
                print(f"Error copying {package_path.name}: {e}")
        else:
            print(f"Warning: Package {package} does not exist or is not a file.")
    