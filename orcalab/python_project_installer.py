import os
import sys
import tarfile
import shutil
import subprocess
import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any

import requests
import importlib.metadata

from orcalab.config_service import ConfigService
from orcalab.project_util import project_id


def _get_user_python_project_root() -> Path:
    if sys.platform == "win32":
        local_appdata = os.getenv("LOCALAPPDATA")
        if not local_appdata:
            raise EnvironmentError("LOCALAPPDATA environment variable is not set.")
        base = Path(local_appdata) / "Orca" / "OrcaStudio" / project_id / "user"
    else:
        base = Path.home() / "Orca" / "OrcaStudio" / project_id / "user"
    return base / "orcalab-pyside"


def _get_install_state_file() -> Path:
    """获取安装状态文件路径"""
    if sys.platform == "win32":
        local_appdata = os.getenv("LOCALAPPDATA")
        if not local_appdata:
            raise EnvironmentError("LOCALAPPDATA environment variable is not set.")
        base = Path(local_appdata) / "Orca" / "OrcaStudio" / project_id / "user"
    else:
        base = Path.home() / "Orca" / "OrcaStudio" / project_id / "user"
    return base / ".orcalab-pyside-install-state.json"


def _load_install_state() -> Dict[str, Any]:
    """加载安装状态"""
    state_file = _get_install_state_file()
    if state_file.exists():
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load install state: {e}")
    return {}


def _save_install_state(state: Dict[str, Any]) -> None:
    """保存安装状态"""
    state_file = _get_install_state_file()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: Could not save install state: {e}")


def _get_current_orca_lab_version() -> str:
    """获取当前安装的 orca-lab 版本"""
    try:
        return importlib.metadata.version("orca-lab")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _is_installation_needed(config: ConfigService) -> bool:
    """检查是否需要安装或更新"""
    state = _load_install_state()
    orcalab_cfg = config.config.get("orcalab", {})
    local_path = str(orcalab_cfg.get("python_project_path", "") or "").strip()
    download_url = str(orcalab_cfg.get("python_project_url", "") or "").strip()
    current_version = _get_current_orca_lab_version()
    
    # 开发者模式：检查本地路径是否变化
    if local_path:
        current_path = str(Path(local_path).expanduser().resolve())
        installed_path = state.get("installed_path")
        if installed_path != current_path:
            print(f"Local path changed: {installed_path} -> {current_path}")
            return True
        return False
    
    # 用户模式：检查版本是否变化
    if download_url:
        installed_version = state.get("installed_version")
        if installed_version != current_version:
            print(f"Orca-lab version changed: {installed_version} -> {current_version}")
            return True
            
        # 检查URL是否变化
        current_url = download_url
        installed_url = state.get("installed_url")
        if installed_url != current_url:
            print(f"URL changed: {installed_url} -> {current_url}")
            return True
        
        # 检查目标目录是否存在且包含有效项目
        dest_root = _get_user_python_project_root()
        if not dest_root.exists():
            print(f"Target directory does not exist: {dest_root}")
            return True
        
        # 检查是否有有效的Python项目文件
        if not _find_editable_root(dest_root):
            print(f"No valid Python project found in: {dest_root}")
            return True
        
        return False
    
    # 如果都没有配置，需要安装
    return True


def _download_archive(url: str, target_file: Path) -> None:
    target_file.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(target_file, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)


def _extract_tar_xz(archive_path: Path, dest_dir: Path) -> None:
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, mode="r:xz") as tf:
        tf.extractall(dest_dir)


def _find_editable_root(extracted_dir: Path) -> Optional[Path]:
    candidates = [extracted_dir]
    # If the archive contains a single top-level folder, drill into it
    items = list(extracted_dir.iterdir())
    if len(items) == 1 and items[0].is_dir():
        candidates.append(items[0])
    for c in candidates:
        if (c / "pyproject.toml").exists() or (c / "setup.py").exists():
            return c
    return None


def _pip_install_editable(package_root: Path) -> None:
    # Use current python's pip to ensure same environment
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", str(package_root)])


def ensure_python_project_installed(config: Optional[ConfigService] = None) -> None:
    """确保 orcalab-pyside 已安装，支持版本变化检测"""
    # Read config
    cfg = config or ConfigService()
    if not hasattr(cfg, "config"):
        # If not initialized by caller, initialize with project root resolved from this file
        current_dir = os.path.dirname(__file__)
        project_root = os.path.abspath(os.path.join(current_dir, os.pardir))
        cfg.init_config(project_root)

    # 检查是否需要安装或更新
    if not _is_installation_needed(cfg):
        print("orcalab-pyside is already up to date, skipping installation")
        return

    print("Installing or updating orcalab-pyside...")
    
    orcalab_cfg = cfg.config.get("orcalab", {})
    local_path = str(orcalab_cfg.get("python_project_path", "") or "").strip()
    download_url = str(orcalab_cfg.get("python_project_url", "") or "").strip()
    current_version = _get_current_orca_lab_version()

    # Determine source and install
    editable_root: Optional[Path] = None
    state_update = {}
    
    if local_path:
        candidate = Path(local_path).expanduser().resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"python_project_path not found: {candidate}")
        editable_root = candidate
        state_update["installed_path"] = str(candidate)
        state_update["installed_url"] = None  # 开发者模式不使用URL
    else:
        if not download_url:
            raise ValueError("python_project_url is empty in configuration")
        
        # 记录当前URL
        state_update["installed_url"] = download_url
        state_update["installed_path"] = None  # 用户模式不使用本地路径
        
        # Download to cache under user folder and extract to fixed dest
        dest_root = _get_user_python_project_root()
        archive_name = "python-project.tar.xz"
        archive_path = dest_root.parent / archive_name

        # 总是重新下载以确保版本同步
        print(f"Downloading from {download_url}...")
        _download_archive(download_url, archive_path)

        print(f"Extracting to {dest_root}...")
        _extract_tar_xz(archive_path, dest_root)
        
        # Try to locate package root (in case archive contains a top-level directory)
        found = _find_editable_root(dest_root)
        editable_root = found or dest_root

    # Install editable package into current environment
    print(f"Installing editable package from {editable_root}...")
    _pip_install_editable(editable_root)
    
    # 保存安装状态
    state_update["installed_at"] = str(Path.cwd())  # 记录安装时的环境
    state_update["installed_version"] = current_version
    _save_install_state(state_update)
    
    print("orcalab-pyside installation completed successfully")


def cli() -> None:
    ensure_python_project_installed()


