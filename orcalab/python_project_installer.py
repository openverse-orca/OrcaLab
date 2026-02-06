import os
import sys
import tarfile
import shutil
import subprocess
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, Callable
import logging

from PySide6 import QtWidgets, QtCore, QtGui
import requests
import importlib.metadata

from orcalab.config_service import ConfigService
from orcalab.project_util import project_id

logger = logging.getLogger(__name__)


class InstallProgressDialog(QtWidgets.QDialog):
    """安装进度对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OrcaLab 安装进度")
        self.setMinimumWidth(500)
        self.setModal(True)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 当前操作标签
        self.status_label = QtWidgets.QLabel("准备安装...")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.status_label)
        
        # 详细信息标签
        self.detail_label = QtWidgets.QLabel("")
        self.detail_label.setStyleSheet("color: #666666;")
        layout.addWidget(self.detail_label)
        
        # 进度条
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #cccccc;
                border-radius: 5px;
                text-align: center;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #2196F3;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # 日志文本框
        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                border: 1px solid #cccccc;
                border-radius: 3px;
                font-family: monospace;
                font-size: 10px;
            }
        """)
        layout.addWidget(self.log_text)
        
        layout.addStretch()
        
    def set_status(self, status: str):
        """设置当前状态"""
        self.status_label.setText(status)
        self.log(status)
        QtWidgets.QApplication.processEvents()
    
    def set_detail(self, detail: str):
        """设置详细信息"""
        self.detail_label.setText(detail)
        QtWidgets.QApplication.processEvents()
    
    def set_progress(self, value: int):
        """设置进度（0-100）"""
        self.progress_bar.setValue(value)
        QtWidgets.QApplication.processEvents()
    
    def log(self, message: str):
        """添加日志"""
        self.log_text.append(message)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        QtWidgets.QApplication.processEvents()
    
    def set_indeterminate(self):
        """设置为不确定进度模式"""
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)
    
    def set_determinate(self):
        """设置为确定进度模式"""
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)


def _extract_version_from_url(url: str) -> str:
    """从 URL 中提取版本号"""
    # 匹配类似 python-project.25.10.4.tar.xz 的模式
    match = re.search(r'python-project\.(\d+\.\d+\.\d+)\.tar\.xz', url)
    if match:
        return match.group(1)
    
    # 如果没有匹配到，尝试从 URL 的其他部分提取版本号
    # 匹配类似 /python-project.25.10.4/ 的模式
    match = re.search(r'/(\d+\.\d+\.\d+)/', url)
    if match:
        return match.group(1)
    
    # 如果都没有匹配到，返回 "unknown"
    return "unknown"


def _get_user_python_project_root(version: str = None) -> Path:
    if sys.platform == "win32":
        local_appdata = os.getenv("LOCALAPPDATA")
        if not local_appdata:
            raise EnvironmentError("LOCALAPPDATA environment variable is not set.")
        base = Path(local_appdata) / "Orca" / "OrcaStudio" / project_id / "user"
    else:
        base = Path.home() / "Orca" / "OrcaStudio" / project_id / "user"
    
    if version and version != "unknown":
        return base / f"orcalab-pyside-{version}"
    else:
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
            logger.warning("Could not load install state: %s", e)
    return {}


def _save_install_state(state: Dict[str, Any]) -> None:
    """保存安装状态"""
    state_file = _get_install_state_file()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning("Could not save install state: %s", e)


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
    
    # 开发者模式：检查本地路径是否变化
    if local_path:
        current_path = str(Path(local_path).expanduser().resolve())
        installed_path = state.get("installed_path")
        if installed_path != current_path:
            logger.info("Local path changed: %s -> %s", installed_path, current_path)
            return True
        return False
    
    # 用户模式：基于URL版本检查
    if download_url:
        # 从URL提取版本号
        url_version = _extract_version_from_url(download_url)
        
        # 检查URL是否变化
        current_url = download_url
        installed_url = state.get("installed_url")
        if installed_url != current_url:
            logger.info("URL changed: %s -> %s", installed_url, current_url)
            return True
        
        # 检查URL版本是否变化
        installed_url_version = state.get("url_version")
        if installed_url_version != url_version:
            logger.info("URL version changed: %s -> %s", installed_url_version, url_version)
            return True
        
        # 检查目标目录是否存在且包含有效项目
        dest_root = _get_user_python_project_root(url_version)
        if not dest_root.exists():
            logger.info("Target directory does not exist: %s", dest_root)
            return True
        
        # 检查是否有有效的Python项目文件
        if not _find_editable_root(dest_root):
            logger.info("No valid Python project found in: %s", dest_root)
            return True
        
        # 检查当前安装的 orcalab-pyside 是否指向正确的目录
        current_package_path = _get_current_orcalab_pyside_path()
        if current_package_path:
            expected_package_path = _find_editable_root(dest_root)
            if expected_package_path and current_package_path.resolve() != expected_package_path.resolve():
                logger.info("Package path mismatch: current=%s, expected=%s", current_package_path, expected_package_path)
                return True
        else:
            # 包不存在，需要安装
            logger.info("orcalab-pyside package not found, need to install")
            return True
        
        return False
    
    # 如果都没有配置，需要安装
    return True


def _download_archive(url: str, target_file: Path, progress_callback: Optional[Callable[[int, str], None]] = None) -> None:
    """下载文件
    
    Args:
        url: 下载链接
        target_file: 保存路径
        progress_callback: 进度回调函数，接收 (进度百分比, 详细信息) 参数
    """
    target_file.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total_size = int(r.headers.get('content-length', 0))
        downloaded = 0
        
        with open(target_file, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = int((downloaded / total_size) * 100)
                        detail = f"{downloaded / 1024 / 1024:.1f}MB / {total_size / 1024 / 1024:.1f}MB"
                        if progress_callback:
                            progress_callback(percent, detail)
                        else:
                            print(f"\r下载进度: {detail} ({percent}%)", end='', flush=True)
                    else:
                        detail = f"已下载: {downloaded / 1024 / 1024:.1f}MB"
                        if progress_callback:
                            progress_callback(0, detail)
                        else:
                            print(f"\r{detail}", end='', flush=True)
        if not progress_callback:
            print()  # 换行


def _extract_tar_xz(archive_path: Path, dest_dir: Path, progress_callback: Optional[Callable[[int, str], None]] = None) -> None:
    """解压 tar.xz 文件
    
    Args:
        archive_path: 压缩包路径
        dest_dir: 目标目录
        progress_callback: 进度回调函数，接收 (进度百分比, 详细信息) 参数
    """
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    with tarfile.open(archive_path, mode="r:xz") as tf:
        members = tf.getmembers()
        total_members = len(members)
        
        for i, member in enumerate(members):
            tf.extract(member, dest_dir)
            if progress_callback and total_members > 0:
                percent = int((i + 1) / total_members * 100)
                detail = f"解压: {member.name} ({i + 1}/{total_members})"
                progress_callback(percent, detail)


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


def _get_current_orcalab_pyside_path() -> Optional[Path]:
    """获取当前安装的 orcalab-pyside 包的路径"""
    try:
        import orcalab_pyside
        package_path = Path(orcalab_pyside.__file__).parent
        # 找到包的根目录（包含 pyproject.toml 或 setup.py 的目录）
        current = package_path
        while current.parent != current:  # 直到根目录
            if (current / "pyproject.toml").exists() or (current / "setup.py").exists():
                return current
            current = current.parent
        return package_path
    except ImportError as e:
        logger.error("Failed to get current orcalab-pyside path: %s", e)
        return None


def _download_pak_file(url: str, target_path: Path, progress_callback: Optional[Callable[[int, str], None]] = None) -> bool:
    """下载 pak 文件
    
    Args:
        url: 下载链接
        target_path: 保存路径
        progress_callback: 进度回调函数，接收 (进度百分比, 详细信息) 参数
        
    Returns:
        bool: 下载是否成功
    """
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            downloaded = 0
            
            with open(target_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = int((downloaded / total_size) * 100)
                            detail = f"{downloaded / 1024 / 1024:.1f}MB / {total_size / 1024 / 1024:.1f}MB"
                            if progress_callback:
                                progress_callback(percent, detail)
                        else:
                            detail = f"已下载: {downloaded / 1024 / 1024:.1f}MB"
                            if progress_callback:
                                progress_callback(0, detail)
        return True
    except Exception as e:
        logger.error("Failed to download pak file from %s: %s", url, e)
        return False


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
        logger.info("orcalab-pyside is already up to date, skipping installation")
        return

    logger.info("Installing or updating orcalab-pyside...")
    
    # 创建进度对话框
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    
    progress_dialog = InstallProgressDialog()
    progress_dialog.show()
    progress_dialog.set_status("正在准备安装...")
    progress_dialog.set_progress(0)
    
    try:
        orcalab_cfg = cfg.config.get("orcalab", {})
        local_path = str(orcalab_cfg.get("python_project_path", "") or "").strip()
        download_url = str(orcalab_cfg.get("python_project_url", "") or "").strip()

        # Determine source and install
        editable_root: Optional[Path] = None
        state_update = {}
        
        if local_path:
            progress_dialog.set_status("使用本地开发路径...")
            progress_dialog.log(f"本地路径: {local_path}")
            
            candidate = Path(local_path).expanduser().resolve()
            if not candidate.exists():
                raise FileNotFoundError(f"python_project_path not found: {candidate}")
            editable_root = candidate
            state_update["installed_path"] = str(candidate)
            state_update["installed_url"] = None
            state_update["url_version"] = None
            progress_dialog.set_progress(50)
        else:
            if not download_url:
                raise ValueError("python_project_url is empty in configuration")
            
            # 从URL提取版本号
            url_version = _extract_version_from_url(download_url)
            logger.info("Extracted version from URL: %s", url_version)
            progress_dialog.log(f"检测到版本: {url_version}")
            
            # 记录当前URL和版本
            state_update["installed_url"] = download_url
            state_update["installed_path"] = None
            state_update["url_version"] = url_version
            
            # Download to cache under user folder and extract to version-specific dest
            dest_root = _get_user_python_project_root(url_version)
            archive_name = f"python-project-{url_version}.tar.xz"
            archive_path = dest_root.parent / archive_name

            # 下载进度回调
            def download_progress(percent: int, detail: str):
                progress_dialog.set_status("正在下载 python-project...")
                progress_dialog.set_detail(detail)
                progress_dialog.set_progress(percent // 2)  # 0-50%
            
            progress_dialog.log(f"开始下载: {download_url}")
            _download_archive(download_url, archive_path, download_progress)
            progress_dialog.log(f"下载完成: {archive_path.name}")

            # 解压进度回调
            def extract_progress(percent: int, detail: str):
                progress_dialog.set_status("正在解压 python-project...")
                progress_dialog.set_detail(detail)
                progress_dialog.set_progress(50 + percent // 2)  # 50-100%
            
            progress_dialog.log(f"开始解压到: {dest_root}")
            _extract_tar_xz(archive_path, dest_root, extract_progress)
            progress_dialog.log("解压完成")
            
            # Try to locate package root (in case archive contains a top-level directory)
            found = _find_editable_root(dest_root)
            editable_root = found or dest_root

        # Install editable package into current environment
        progress_dialog.set_status("正在安装 Python 包...")
        progress_dialog.set_detail("运行 pip install -e ...")
        progress_dialog.set_indeterminate()
        progress_dialog.log(f"安装可编辑包: {editable_root}")
        
        logger.info("Installing editable package from %s...", editable_root)
        _pip_install_editable(editable_root)
        progress_dialog.log("包安装完成")
        
        # 下载 pak 文件（如果配置了）
        pak_urls = orcalab_cfg.get("pak_urls", [])
        if pak_urls:
            progress_dialog.set_determinate()
            progress_dialog.log(f"检测到 {len(pak_urls)} 个 pak 文件需要下载")
            
            from orcalab.project_util import get_cache_folder
            cache_folder = get_cache_folder()
            cache_folder.mkdir(parents=True, exist_ok=True)
            
            for i, pak_url in enumerate(pak_urls):
                filename = pak_url.split("/")[-1]
                target_path = cache_folder / filename
                
                # 如果文件已存在，跳过
                if target_path.exists():
                    progress_dialog.log(f"pak 文件已存在，跳过: {filename}")
                    continue
                
                def pak_download_progress(percent: int, detail: str):
                    progress_dialog.set_status(f"正在下载 pak 文件 ({i+1}/{len(pak_urls)})...")
                    progress_dialog.set_detail(f"{filename}: {detail}")
                    progress_dialog.set_progress(percent)
                
                progress_dialog.log(f"开始下载 pak 文件: {filename}")
                success = _download_pak_file(pak_url, target_path, pak_download_progress)
                
                if success:
                    progress_dialog.log(f"pak 文件下载完成: {filename}")
                else:
                    progress_dialog.log(f"pak 文件下载失败: {filename}")
        
        # 保存安装状态
        state_update["installed_at"] = str(Path.cwd())
        _save_install_state(state_update)
        
        progress_dialog.set_determinate()
        progress_dialog.set_progress(100)
        progress_dialog.set_status("安装完成！")
        progress_dialog.set_detail("请重新运行 OrcaLab")
        progress_dialog.log("所有安装步骤已完成")
        
        QtWidgets.QMessageBox.information(progress_dialog, "安装完成", "orcalab初始化完成, 请重新运行orcalab")
        
    except Exception as e:
        logger.exception("Installation failed: %s", e)
        progress_dialog.log(f"错误: {str(e)}")
        QtWidgets.QMessageBox.critical(progress_dialog, "安装失败", f"安装过程中出现错误:\n{str(e)}")
        raise
    finally:
        progress_dialog.close()
    
    # 包更新后直接退出程序
    import sys
    sys.exit(0)


def cli() -> None:
    ensure_python_project_installed()


