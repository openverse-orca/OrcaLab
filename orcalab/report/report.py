import os
import platform
import shutil
import subprocess
import sys
from typing import Dict, List, Optional

import importlib.metadata as importlib_metadata


def get_system_info() -> Dict[str, Optional[str]]:
    """Return basic system information.

    Fields include: system, node, release, version, machine, processor,
    platform, python_version, distro (if available), uptime_seconds (if available).
    """
    info: Dict[str, Optional[str]] = {}
    info["system"] = platform.system()
    info["node"] = platform.node()
    info["release"] = platform.release()
    info["version"] = platform.version()
    info["machine"] = platform.machine()
    info["processor"] = platform.processor() or None
    info["platform"] = platform.platform()
    info["python_version"] = platform.python_version()

    if sys.platform == "linux":
        # Try to get a distro string on Linux
        distro_name = None
        if info["system"] == "Linux":
            try:
                import distro as _distro  # type: ignore

                distro_name = _distro.name(pretty=True)
            except Exception:
                # fallback: check /etc/os-release
                try:
                    with open("/etc/os-release", "r") as f:
                        for line in f:
                            if line.startswith("PRETTY_NAME="):
                                distro_name = line.split("=", 1)[1].strip().strip('"')
                                break
                except Exception:
                    distro_name = None
        info["distro"] = distro_name

    return info


def get_cpu_info() -> Dict[str, Optional[object]]:
    """Return CPU information.

    Keys: physical_cores, logical_cores, model_name, frequency_mhz (if available)
    """
    cpu: Dict[str, Optional[object]] = {}
    # logical and physical cores
    try:
        import psutil

        cpu["logical_cores"] = psutil.cpu_count(logical=True)
        cpu["physical_cores"] = psutil.cpu_count(logical=False)
        try:
            freqs = psutil.cpu_freq()
            cpu["frequency_mhz"] = freqs.current if freqs is not None else None
        except Exception:
            cpu["frequency_mhz"] = None
    except Exception:
        cpu["logical_cores"] = os.cpu_count()
        cpu["physical_cores"] = None
        cpu["frequency_mhz"] = None

    if sys.platform == "linux":
        # model name (Linux /proc/cpuinfo best-effort)
        model = None
        try:
            if os.path.exists("/proc/cpuinfo"):
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if line.strip().startswith(
                            "model name"
                        ) or line.strip().startswith("Hardware"):
                            parts = line.split(":", 1)
                            if len(parts) > 1:
                                model = parts[1].strip()
                                break
        except Exception:
            model = None
    else:
        model = _run_cmd(
            [
                "powershell",
                "-Command",
                "(Get-WmiObject Win32_Processor).Name",
            ]
        )
    cpu["model_name"] = model
    return cpu


def _run_cmd(cmd: List[str], timeout: float = 5.0) -> Optional[str]:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=timeout)
        return out.decode(errors="ignore").strip()
    except Exception:
        return None


def get_gpu_info() -> List[Dict[str, Optional[object]]]:
    gpus: List[Dict[str, Optional[object]]] = []

    # 1) nvidia-smi parsing
    if shutil.which("nvidia-smi"):
        out = _run_cmd(
            [
                "nvidia-smi",
                "--query-gpu=index,name,driver_version,memory.total",
                "--format=csv,noheader,nounits",
            ]
        )
        if out:
            for line in out.splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 4:
                    gpus.append(
                        {
                            "index": parts[0],
                            "name": parts[1],
                            "driver_version": parts[2],
                            "memory_total_mb": parts[3],
                        }
                    )
            if gpus:
                return gpus

    if shutil.which("amd-smi"):
        out = _run_cmd(["amd-smi", "static", "--asic", "--vram", "--json"])
        if out:
            json_data = json.loads(out)
            return json_data

    return gpus


def get_env_vars() -> Dict[str, str]:
    """Return a copy of the current environment variables as a dict."""
    return dict(os.environ)


def get_system_packages() -> Dict[str, str]:
    # Debian/Ubuntu
    if shutil.which("dpkg-query"):
        out = _run_cmd(["dpkg-query", "-W", "-f=${Package} ${Version}\n"]) or ""
        packages: Dict[str, str] = {}
        for line in out.splitlines():
            if not line:
                continue
            parts = line.split(None, 1)
            pkg = parts[0]
            ver = parts[1].strip() if len(parts) > 1 else ""
            packages[pkg] = ver
        return packages

    # RPM (Fedora/CentOS)
    if shutil.which("rpm"):
        out = _run_cmd(["rpm", "-qa", "--qf", "%{NAME} %{VERSION}-%{RELEASE}\n"]) or ""
        packages: Dict[str, str] = {}
        for line in out.splitlines():
            parts = line.split(None, 1)
            if not parts:
                continue
            name = parts[0]
            ver = parts[1].strip() if len(parts) > 1 else ""
            packages[name] = ver
        return packages

    # pacman (Arch)
    if shutil.which("pacman"):
        out = _run_cmd(["pacman", "-Q"]) or ""
        packages: Dict[str, str] = {}
        for line in out.splitlines():
            parts = line.split(None, 1)
            if len(parts) >= 2:
                packages[parts[0]] = parts[1]
        return packages

    # apk (Alpine)
    if shutil.which("apk"):
        out = _run_cmd(["apk", "info", "-v"]) or ""
        packages: Dict[str, str] = {}
        for line in out.splitlines():
            parts = line.split("-")
            if parts:
                name = parts[0]
                version = "-".join(parts[1:]) if len(parts) > 1 else ""
                packages[name] = version
        return packages

    return {}


def get_python_packages() -> Dict[str, str]:
    packages: Dict[str, str] = {}
    distributions = list(importlib_metadata.distributions())
    for dist in distributions:
        packages[dist.metadata["Name"]] = dist.version
    return packages


if __name__ == "__main__":
    import json

    report = {
        "system": get_system_info(),
        "cpu": get_cpu_info(),
        "gpus": get_gpu_info(),
        "env": get_env_vars(),
        "system_packages": get_system_packages(),
        "python_packages": get_python_packages(),
    }
    print(json.dumps(report, indent=2, default=str))
