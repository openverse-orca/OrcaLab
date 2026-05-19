import logging
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class GpuVendor(Enum):
    NVIDIA = "NVIDIA"
    AMD = "AMD"
    INTEL = "Intel"
    MOORE_THREADS = "Moore Threads"
    CORERISE = "Corerise"
    ILUVATAR = "Iluvatar"
    METAX = "MetaX"
    UNKNOWN = "Unknown"


class DriverStatus(Enum):
    OK = "ok"
    NOT_INSTALLED = "not_installed"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class GpuDeviceInfo:
    vendor: GpuVendor
    name: str
    pci_address: str = ""
    driver_status: DriverStatus = DriverStatus.UNKNOWN
    driver_version: str = ""
    driver_cli_tool: str = ""
    memory_total_mb: str = ""
    raw_output: str = ""


@dataclass
class GpuDriverCheckResult:
    has_gpu_hardware: bool = False
    has_working_driver: bool = False
    devices: List[GpuDeviceInfo] = field(default_factory=list)

    def devices_with_driver_ok(self) -> List[GpuDeviceInfo]:
        return [d for d in self.devices if d.driver_status == DriverStatus.OK]

    def devices_without_driver(self) -> List[GpuDeviceInfo]:
        return [d for d in self.devices if d.driver_status != DriverStatus.OK]


_VENDOR_LSPCI_PATTERNS: List[Tuple[GpuVendor, str]] = [
    (GpuVendor.NVIDIA, "NVIDIA Corporation"),
    (GpuVendor.AMD, "Advanced Micro Devices"),
    (GpuVendor.AMD, "AMD/ATI"),
    (GpuVendor.INTEL, "Intel Corporation"),
    (GpuVendor.MOORE_THREADS, "Moore Threads"),
    (GpuVendor.MOORE_THREADS, "MTT"),
    (GpuVendor.CORERISE, "Corerise"),
    (GpuVendor.ILUVATAR, "Iluvatar"),
    (GpuVendor.METAX, "MetaX"),
]

_VENDOR_DRIVER_TOOLS: Dict[GpuVendor, List[str]] = {
    GpuVendor.NVIDIA: ["nvidia-smi"],
    GpuVendor.AMD: ["amd-smi", "rocm-smi"],
    GpuVendor.INTEL: ["intel_gpu_top", "xpu-smi"],
    GpuVendor.MOORE_THREADS: ["mthreads-gmi"],
    GpuVendor.CORERISE: ["ventus-gmi"],
    GpuVendor.ILUVATAR: ["ixsmi"],
    GpuVendor.METAX: ["mxsmi"],
}

_VENDOR_DRIVER_GUIDANCE: Dict[GpuVendor, Dict[str, str]] = {
    GpuVendor.NVIDIA: {
        "name_cn": "NVIDIA",
        "install_ubuntu": "sudo apt install nvidia-driver-535\n或访问官网下载 .run 安装包",
        "install_generic": "访问 NVIDIA 官网下载对应驱动",
        "url": "https://www.nvidia.com/Download/index.aspx",
        "verify_cmd": "nvidia-smi",
    },
    GpuVendor.AMD: {
        "name_cn": "AMD",
        "install_ubuntu": "sudo apt install amdgpu-pro-install\n或安装 ROCm: https://rocm.docs.amd.com/",
        "install_generic": "访问 AMD 官网下载对应驱动",
        "url": "https://www.amd.com/en/support",
        "verify_cmd": "amd-smi 或 rocm-smi",
    },
    GpuVendor.INTEL: {
        "name_cn": "Intel",
        "install_ubuntu": "sudo apt install intel-media-va-driver\n或安装 Compute Runtime: https://github.com/intel/compute-runtime",
        "install_generic": "访问 Intel 官网下载对应驱动",
        "url": "https://www.intel.com/content/www/us/en/download-center",
        "verify_cmd": "intel_gpu_top 或 xpu-smi",
    },
    GpuVendor.MOORE_THREADS: {
        "name_cn": "摩尔线程",
        "install_ubuntu": "参考摩尔线程官方文档安装 MTGPU 驱动",
        "install_generic": "访问摩尔线程官网下载驱动",
        "url": "https://www.mthreads.com/pes/drivers/search",
        "verify_cmd": "mthreads-gmi",
    },
    GpuVendor.CORERISE: {
        "name_cn": "瀚博",
        "install_ubuntu": "参考瀚博官方文档安装 Ventus 驱动",
        "install_generic": "访问瀚博官网下载驱动",
        "url": "https://www.corerise.com/service.html",
        "verify_cmd": "ventus-gmi",
    },
    GpuVendor.ILUVATAR: {
        "name_cn": "天数智芯",
        "install_ubuntu": "参考天数智芯官方文档安装驱动",
        "install_generic": "访问天数智芯官网下载驱动",
        "url": "https://www.iluvatar.com/support",
        "verify_cmd": "ixsmi",
    },
    GpuVendor.METAX: {
        "name_cn": "沐曦",
        "install_ubuntu": "参考沐曦官方文档安装驱动",
        "install_generic": "访问沐曦官网下载驱动",
        "url": "https://developer.metax-tech.com/softnova",
        "verify_cmd": "mxsmi",
    },
    GpuVendor.UNKNOWN: {
        "name_cn": "未知厂商",
        "install_ubuntu": "请联系显卡厂商获取驱动",
        "install_generic": "请联系显卡厂商获取驱动",
        "url": "",
        "verify_cmd": "",
    },
}


def _run_cmd(cmd: List[str], timeout: float = 5.0) -> Optional[str]:
    try:
        out = subprocess.check_output(
            cmd, stderr=subprocess.DEVNULL, timeout=timeout
        )
        return out.decode(errors="ignore").strip()
    except Exception:
        return None


def _detect_gpu_hardware_linux() -> List[GpuDeviceInfo]:
    devices: List[GpuDeviceInfo] = []

    lspci = shutil.which("lspci")
    if not lspci:
        logger.debug("lspci 不可用，尝试 /sys/bus/pci 方式检测")
        devices.extend(_detect_gpu_hardware_sysfs())
        return devices

    out = _run_cmd([lspci, "-nn", "-D"])
    if not out:
        return devices

    for line in out.splitlines():
        if not re.search(r"\b(VGA|3D|Display)\b", line, re.IGNORECASE):
            continue

        pci_address = ""
        match = re.match(r"^([0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.\d+)", line)
        if match:
            pci_address = match.group(1)

        vendor = GpuVendor.UNKNOWN
        for known_vendor, pattern in _VENDOR_LSPCI_PATTERNS:
            if pattern.lower() in line.lower():
                vendor = known_vendor
                break

        name = line.split(":", 2)[-1].strip() if ":" in line else line.strip()

        devices.append(GpuDeviceInfo(
            vendor=vendor,
            name=name,
            pci_address=pci_address,
        ))

    return devices


def _detect_gpu_hardware_sysfs() -> List[GpuDeviceInfo]:
    devices: List[GpuDeviceInfo] = []
    sysfs_path = "/sys/bus/pci/devices"
    if not os.path.isdir(sysfs_path):
        return devices

    gpu_class_codes = ("0x030000", "0x030200", "0x0300", "0x0302")

    try:
        for slot in os.listdir(sysfs_path):
            slot_path = os.path.join(sysfs_path, slot)
            class_file = os.path.join(slot_path, "class")
            if not os.path.isfile(class_file):
                continue
            try:
                with open(class_file, "r") as f:
                    pci_class = f.read().strip()
            except Exception:
                continue

            if not any(pci_class.startswith(c) for c in gpu_class_codes):
                continue

            vendor_id = ""
            vendor_file = os.path.join(slot_path, "vendor")
            if os.path.isfile(vendor_file):
                try:
                    with open(vendor_file, "r") as f:
                        vendor_id = f.read().strip()
                except Exception:
                    pass

            device_name = ""
            device_file = os.path.join(slot_path, "device")
            if os.path.isfile(device_file):
                try:
                    with open(device_file, "r") as f:
                        device_name = f.read().strip()
                except Exception:
                    pass

            vendor = _vendor_id_to_enum(vendor_id)
            name = f"PCI Device {vendor_id}:{device_name}" if device_name else f"PCI Device {vendor_id}"

            devices.append(GpuDeviceInfo(
                vendor=vendor,
                name=name,
                pci_address=slot,
            ))
    except Exception:
        logger.debug("读取 /sys/bus/pci/devices 失败", exc_info=True)

    return devices


_PCI_VENDOR_IDS: Dict[str, GpuVendor] = {
    "0x10de": GpuVendor.NVIDIA,
    "0x1002": GpuVendor.AMD,
    "0x8086": GpuVendor.INTEL,
    "0x1ed5": GpuVendor.MOORE_THREADS,
    "0x1cfa": GpuVendor.CORERISE,
    "0x7d1a": GpuVendor.ILUVATAR,
    "0x1f95": GpuVendor.METAX,
}


def _vendor_id_to_enum(vendor_id: str) -> GpuVendor:
    return _PCI_VENDOR_IDS.get(vendor_id, GpuVendor.UNKNOWN)


def _check_driver_nvidia(device: GpuDeviceInfo) -> GpuDeviceInfo:
    tool = shutil.which("nvidia-smi")
    if not tool:
        device.driver_status = DriverStatus.NOT_INSTALLED
        device.driver_cli_tool = "nvidia-smi"
        return device

    out = _run_cmd([
        "nvidia-smi",
        "--query-gpu=index,name,driver_version,memory.total",
        "--format=csv,noheader,nounits",
    ])
    if not out:
        device.driver_status = DriverStatus.ERROR
        device.driver_cli_tool = "nvidia-smi"
        return device

    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 4:
            device.name = parts[1]
            device.driver_version = parts[2]
            device.memory_total_mb = parts[3]
            device.driver_status = DriverStatus.OK
            device.driver_cli_tool = "nvidia-smi"
            break
    else:
        device.driver_status = DriverStatus.ERROR
        device.driver_cli_tool = "nvidia-smi"

    return device


def _check_driver_amd(device: GpuDeviceInfo) -> GpuDeviceInfo:
    for tool_name in ["amd-smi", "rocm-smi"]:
        tool = shutil.which(tool_name)
        if not tool:
            continue

        if tool_name == "amd-smi":
            out = _run_cmd(["amd-smi", "static", "--asic", "--vram", "--json"])
            if out:
                try:
                    import json
                    data = json.loads(out)
                    if isinstance(data, list) and data:
                        first = data[0]
                        device.name = first.get("asic", {}).get("market_name", device.name)
                        device.driver_version = first.get("asic", {}).get("driver_version", "")
                        device.driver_status = DriverStatus.OK
                        device.driver_cli_tool = "amd-smi"
                        return device
                except Exception:
                    pass
        elif tool_name == "rocm-smi":
            out = _run_cmd(["rocm-smi", "--showdriverversion"])
            if out:
                for line in out.splitlines():
                    if "Driver version" in line or "driver" in line.lower():
                        parts = line.split(":", 1)
                        if len(parts) > 1:
                            device.driver_version = parts[1].strip()
                        break
                device.driver_status = DriverStatus.OK
                device.driver_cli_tool = "rocm-smi"
                return device

    device.driver_status = DriverStatus.NOT_INSTALLED
    device.driver_cli_tool = "amd-smi 或 rocm-smi"
    return device


def _check_driver_intel(device: GpuDeviceInfo) -> GpuDeviceInfo:
    for tool_name in ["xpu-smi", "intel_gpu_top"]:
        tool = shutil.which(tool_name)
        if not tool:
            continue

        if tool_name == "xpu-smi":
            out = _run_cmd(["xpu-smi", "discovery", "-d"])
            if out:
                device.driver_status = DriverStatus.OK
                device.driver_cli_tool = "xpu-smi"
                for line in out.splitlines():
                    if "driver version" in line.lower() or "driver_version" in line.lower():
                        parts = line.split(":", 1)
                        if len(parts) > 1:
                            device.driver_version = parts[1].strip()
                        break
                return device
        elif tool_name == "intel_gpu_top":
            device.driver_status = DriverStatus.OK
            device.driver_cli_tool = "intel_gpu_top"
            return device

    if sys.platform == "linux":
        i915_path = "/sys/module/i915"
        if os.path.isdir(i915_path):
            device.driver_status = DriverStatus.OK
            device.driver_cli_tool = "i915 (kernel)"
            device.driver_version = _read_sysfs_module_version("i915")
            return device

    device.driver_status = DriverStatus.NOT_INSTALLED
    device.driver_cli_tool = "xpu-smi 或 intel_gpu_top"
    return device


def _check_driver_generic(device: GpuDeviceInfo, tool_names: List[str]) -> GpuDeviceInfo:
    for tool_name in tool_names:
        tool = shutil.which(tool_name)
        if not tool:
            continue

        out = _run_cmd([tool_name])
        if out:
            device.driver_status = DriverStatus.OK
            device.driver_cli_tool = tool_name
            for line in out.splitlines()[:10]:
                if "driver" in line.lower() or "version" in line.lower():
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        device.driver_version = parts[1].strip()
                    break
            return device

    device.driver_status = DriverStatus.NOT_INSTALLED
    device.driver_cli_tool = " 或 ".join(tool_names)
    return device


def _read_sysfs_module_version(module_name: str) -> str:
    try:
        with open(f"/sys/module/{module_name}/version", "r") as f:
            return f.read().strip()
    except Exception:
        return ""


_DRIVER_CHECK_DISPATCH = {
    GpuVendor.NVIDIA: lambda d: _check_driver_nvidia(d),
    GpuVendor.AMD: lambda d: _check_driver_amd(d),
    GpuVendor.INTEL: lambda d: _check_driver_intel(d),
    GpuVendor.MOORE_THREADS: lambda d: _check_driver_generic(d, ["mthreads-gmi"]),
    GpuVendor.CORERISE: lambda d: _check_driver_generic(d, ["ventus-gmi"]),
    GpuVendor.ILUVATAR: lambda d: _check_driver_generic(d, ["ixsmi"]),
    GpuVendor.METAX: lambda d: _check_driver_generic(d, ["mxsmi"]),
}


def check_gpu_drivers() -> GpuDriverCheckResult:
    result = GpuDriverCheckResult()

    if sys.platform == "linux":
        devices = _detect_gpu_hardware_linux()
    else:
        devices = _detect_gpu_hardware_windows()

    result.devices = devices
    result.has_gpu_hardware = len(devices) > 0

    for device in devices:
        checker = _DRIVER_CHECK_DISPATCH.get(device.vendor)
        if checker:
            checker(device)
        else:
            device.driver_status = DriverStatus.UNKNOWN

    result.has_working_driver = any(
        d.driver_status == DriverStatus.OK for d in devices
    )

    return result


def _detect_gpu_hardware_windows() -> List[GpuDeviceInfo]:
    devices: List[GpuDeviceInfo] = []

    out = _run_cmd([
        "powershell", "-Command",
        "Get-WmiObject Win32_VideoController | "
        "Select-Object Name, AdapterCompatibility, DriverVersion, AdapterRAM | "
        "ConvertTo-Json"
    ])
    if not out:
        return devices

    import json
    try:
        data = json.loads(out)
        if isinstance(data, dict):
            data = [data]
        for item in data:
            name = item.get("Name", "Unknown GPU")
            compat = item.get("AdapterCompatibility", "")
            driver_ver = item.get("DriverVersion", "")
            adapter_ram = item.get("AdapterRAM", 0)

            vendor = GpuVendor.UNKNOWN
            compat_lower = compat.lower()
            for known_vendor, pattern in _VENDOR_LSPCI_PATTERNS:
                if pattern.lower() in compat_lower:
                    vendor = known_vendor
                    break

            mem_mb = str(adapter_ram // (1024 * 1024)) if isinstance(adapter_ram, (int, float)) and adapter_ram > 0 else ""

            device = GpuDeviceInfo(
                vendor=vendor,
                name=name,
                driver_version=driver_ver,
                memory_total_mb=mem_mb,
            )

            if vendor in _DRIVER_CHECK_DISPATCH:
                _DRIVER_CHECK_DISPATCH[vendor](device)
            elif driver_ver:
                device.driver_status = DriverStatus.OK
            else:
                device.driver_status = DriverStatus.NOT_INSTALLED

            devices.append(device)
    except Exception:
        logger.debug("解析 Windows GPU 信息失败", exc_info=True)

    return devices


def build_driver_guidance_text(result: GpuDriverCheckResult) -> str:
    if result.has_working_driver:
        return ""

    if not result.has_gpu_hardware:
        return (
            "未检测到任何 GPU 硬件。\n\n"
            "OrcaLab 需要独立显卡才能运行。请确认：\n"
            "1. 您的电脑已安装独立显卡\n"
            "2. 显卡已正确插入 PCIe 插槽\n"
            "3. 显示器已连接到独立显卡的输出接口\n\n"
            "最低 GPU 要求：NVIDIA RTX 3060 或同等性能显卡"
        )

    lines = ["检测到 GPU 硬件但驱动未安装或不可用：\n"]

    for device in result.devices_without_driver():
        guidance = _VENDOR_DRIVER_GUIDANCE.get(device.vendor, _VENDOR_DRIVER_GUIDANCE[GpuVendor.UNKNOWN])
        lines.append(f"【{guidance['name_cn']}】{device.name}")
        lines.append(f"  检测工具: {device.driver_cli_tool}")
        lines.append(f"  驱动状态: {_driver_status_text(device.driver_status)}")
        lines.append(f"  安装方式 (Ubuntu): {guidance['install_ubuntu']}")
        lines.append(f"  通用安装: {guidance['install_generic']}")
        if guidance["url"]:
            lines.append(f"  驱动下载: {guidance['url']}")
        lines.append(f"  安装后验证: {guidance['verify_cmd']}")
        lines.append("")

    lines.append("安装驱动后请重启电脑，然后重新启动 OrcaLab。")
    return "\n".join(lines)


def build_driver_detail_text(result: GpuDriverCheckResult) -> str:
    if not result.devices:
        return "未检测到 GPU 设备"

    lines = []
    for i, device in enumerate(result.devices):
        guidance = _VENDOR_DRIVER_GUIDANCE.get(device.vendor, _VENDOR_DRIVER_GUIDANCE[GpuVendor.UNKNOWN])
        lines.append(f"--- GPU {i} ---")
        lines.append(f"厂商: {guidance['name_cn']}")
        lines.append(f"设备名: {device.name}")
        lines.append(f"PCI 地址: {device.pci_address or 'N/A'}")
        lines.append(f"驱动状态: {_driver_status_text(device.driver_status)}")
        lines.append(f"驱动版本: {device.driver_version or 'N/A'}")
        lines.append(f"检测工具: {device.driver_cli_tool or 'N/A'}")
        lines.append(f"显存: {device.memory_total_mb or 'N/A'} MB")
        lines.append("")

    return "\n".join(lines)


def _driver_status_text(status: DriverStatus) -> str:
    mapping = {
        DriverStatus.OK: "正常",
        DriverStatus.NOT_INSTALLED: "未安装",
        DriverStatus.ERROR: "异常",
        DriverStatus.UNKNOWN: "未知",
    }
    return mapping.get(status, "未知")


def show_gpu_driver_warning(result: GpuDriverCheckResult) -> bool:
    if result.has_working_driver:
        return True

    from PySide6 import QtWidgets, QtCore

    guidance_text = build_driver_guidance_text(result)
    detail_text = build_driver_detail_text(result)

    msg_box = QtWidgets.QMessageBox()
    msg_box.setWindowTitle("GPU 驱动异常")
    msg_box.setIcon(QtWidgets.QMessageBox.Icon.Critical)
    msg_box.setMinimumSize(800, 500)

    if not result.has_gpu_hardware:
        msg_box.setText("未检测到 GPU 硬件，OrcaLab 无法启动。")
        msg_box.setInformativeText(
            "OrcaLab 需要独立显卡才能运行。\n\n"
            "请确认已安装独立显卡并正确连接，然后重新启动 OrcaLab。"
        )
    else:
        msg_box.setText("GPU 驱动未安装或不可用，OrcaLab 无法正常启动。")
        msg_box.setInformativeText(guidance_text)

    msg_box.setDetailedText(detail_text)

    continue_button = msg_box.addButton("继续启动（可能无法正常渲染）", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
    exit_button = msg_box.addButton("退出", QtWidgets.QMessageBox.ButtonRole.RejectRole)
    msg_box.setDefaultButton(exit_button)

    msg_box.show()
    msg_box.resize(1200, 700)
    msg_box.exec()

    return msg_box.clickedButton() == continue_button
