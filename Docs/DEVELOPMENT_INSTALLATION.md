# OrcaLab 开发安装指南

本文档适用于想要开发或贡献 OrcaLab 的开发者。

## 开发环境安装

### 前置要求

- Python 3.12+
- pip（最新版本推荐）
- Git

### 从源码安装

1. 克隆仓库：
```bash
git clone https://github.com/openverse-orca/OrcaLab.git
cd OrcaLab
```

2. 以可编辑模式安装：
```bash
pip install -e .
```

这将在开发模式下安装 OrcaLab，允许你直接修改源代码而无需重新安装。

### 依赖包

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

## orcalab-pyside 包管理

安装 OrcaLab 后，需要安装 `orcalab-pyside` 包，该包提供额外的 UI 组件。

### 对于开发者（手动安装）

如果你正在开发 OrcaLab 并想使用本地版本的 `orcalab-pyside`：

1. 在 `orca.config.user.toml` 中配置本地路径：
```toml
[orcalab]
python_project_path = "/path/to/your/local/orcalab-pyside"
```

2. 手动运行后安装器：
```bash
orcalab-post-install
```

**开发者注意事项**：每当你在配置中更改 `python_project_path` 时，必须手动运行 `orcalab-post-install` 来更新安装。自动检测仅适用于用户模式下的版本变化，不适用于开发者模式下的本地路径变化。

### 自动安装（首次运行）

`orcalab-pyside` 包将在首次运行 OrcaLab 时自动下载并安装。系统将：
- 从配置的 OSS URL 下载包
- 解压到用户目录
- 在同一 conda 环境中以可编辑模式安装

## 从源码运行

### 标准启动

安装完成后，使用命令行启动：
```bash
orcalab
```

### 应急启动

如果 `orcalab` 命令不可用（例如打包不完整时），可以直接运行 `main.py`：

```bash
# 需要确保在项目根目录
python orcalab/main.py
```

## 验证开发安装

```python
import orcalab
print(f"OrcaLab version: {getattr(orcalab, '__version__', 'unknown')}")
```

## 常见问题

### 1. 安装失败
- 确保 Python 版本 >= 3.12
- 升级 pip: `pip install --upgrade pip`
- 检查网络连接
- 对于国内用户，可考虑配置清华源或使用梯子

### 2. 依赖冲突
- 使用虚拟环境: `python -m venv orcalab_env && source orcalab_env/bin/activate`
- 清理缓存: `pip cache purge`

### 3. 从 TestPyPI 安装开发版本时找不到依赖
- 使用 `--extra-index-url` 参数从 PyPI 获取依赖
- 或者先安装依赖: `pip install orca-gym numpy scipy pyside6`

## 卸载

```bash
pip uninstall orca-lab
# 或
pip uninstall orca-lab-test
```

