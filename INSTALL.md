# OrcaLab 安装指南

## 从 PyPI 安装 (推荐)

### 安装正式版本
```bash
pip install orca-lab
```

### 安装开发版本 (从 TestPyPI)
```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ orca-lab-test
```

## 系统要求

- Python 3.12+
- pip (最新版本推荐)

## 依赖包

OrcaLab 会自动安装以下依赖：
- orca-gym
- numpy>=2.0.0
- scipy
- scipy-stubs
- grpcio==1.66.1
- grpcio-tools==1.66.1
- pyside6==6.9.2
- aiohttp
- aiofiles
- qasync
- psutil

## 验证安装

安装完成后，可以通过以下方式验证：

```python
import orcalab
print(f"OrcaLab version: {getattr(orcalab, '__version__', 'unknown')}")
```

## 常见问题

### 1. 安装失败
- 确保 Python 版本 >= 3.12
- 升级 pip: `pip install --upgrade pip`
- 检查网络连接

### 2. 依赖冲突
- 使用虚拟环境: `python -m venv orcalab_env && source orcalab_env/bin/activate`
- 清理缓存: `pip cache purge`

### 3. 从 TestPyPI 安装时找不到依赖
- 使用 `--extra-index-url` 参数从 PyPI 获取依赖
- 或者先安装依赖: `pip install orca-gym numpy scipy pyside6`

## 开发安装

如果需要开发版本或从源码安装：

```bash
git clone https://github.com/openverse-orca/OrcaLab.git
cd OrcaLab
pip install -e .
```

## 卸载

```bash
pip uninstall orca-lab
# 或
pip uninstall orca-lab-test
```
