# OrcaLab 打包发布流程设置完成

## 概述

已为 OrcaLab 项目成功设置完整的打包发布流程，包括：

- ✅ 包配置 (`pyproject.toml`)
- ✅ 构建脚本 (`Makefile` + shell scripts)
- ✅ 发布流程 (TestPyPI + PyPI)
- ✅ 测试安装流程
- ✅ 开发依赖管理
- ✅ 文档说明

## 包信息

- **正式包名**: `orca-lab` (PyPI)
- **测试包名**: `orca-lab-test` (TestPyPI)
- **当前版本**: 25.9.0

## 快速开始

### 1. 安装开发依赖
```bash
pip install build twine wheel setuptools pytest pytest-cov flake8 black mypy
```

### 2. 配置 PyPI 认证
```bash
make setup-pypirc
```

### 3. 发布到 TestPyPI（推荐先测试）
```bash
./scripts/release/release.sh test
```

### 4. 发布到 PyPI
```bash
./scripts/release/release.sh prod
```

### 5. 分步执行（可选）
```bash
# 清理、构建、检查、上传
./scripts/release/clean.sh
./scripts/release/build.sh
./scripts/release/check.sh
./scripts/release/upload_test.sh  # 或 upload_prod.sh
```

## 主要文件

### 配置文件
- `pyproject.toml` - 项目配置和依赖
- `MANIFEST.in` - 包含文件配置
- `Makefile` - 构建命令

### 脚本文件
- `scripts/release/setup_pypirc.sh` - 设置 PyPI 配置
- `scripts/release/check_pypirc.sh` - 检查 PyPI 配置
- `scripts/release/build.sh` - 构建包
- `scripts/release/upload_test.sh` - 上传到 TestPyPI
- `scripts/release/upload_prod.sh` - 上传到 PyPI
- `scripts/release/test_install.sh` - 测试安装

### 文档文件
- `README.md` - 主要文档（已更新）
- `scripts/release/README.md` - 发布流程文档
- `INSTALL.md` - 安装说明

## 依赖包说明

### 核心构建工具
- `build` - 包构建工具
- `twine` - 包上传工具
- `wheel` - Wheel 格式支持
- `setuptools` - 包设置工具

### 开发工具
- `pytest` - 测试框架
- `pytest-cov` - 测试覆盖率
- `flake8` - 代码风格检查
- `black` - 代码格式化
- `mypy` - 静态类型检查

## 可用命令

| 命令 | 说明 |
|------|------|
| `make setup-pypirc` | 设置 PyPI 配置文件 |
| `make check-pypirc` | 检查 PyPI 配置 |
| `make build` | 构建分发包 |
| `make check` | 检查包质量 |
| `make test-install` | 测试本地安装 |
| `make test-install-testpypi` | 测试 TestPyPI 安装 |
| `make test-install-pypi` | 测试 PyPI 安装 |
| `make release-test` | 发布到 TestPyPI |
| `make release-prod` | 发布到 PyPI |
| `make bump-version` | 更新版本号 |
| `make clean` | 清理构建产物 |
| `make test` | 运行测试 |
| `make format` | 格式化代码 |
| `make lint` | 代码检查 |

## 注意事项

1. **环境要求**: Python 3.12+
2. **依赖**: 需要先安装 OrcaGym
3. **认证**: 发布前需要配置 PyPI/TestPyPI 的 API token
4. **编译问题**: grpcio 和 grpcio-tools 在某些环境下可能需要编译，这是正常的

## 下一步

1. 安装开发依赖：`pip install build twine wheel setuptools pytest pytest-cov flake8 black mypy`
2. 运行 `make setup-pypirc` 配置 PyPI 认证
3. 运行 `make check-pypirc` 验证配置
4. 运行 `./scripts/release/release.sh test` 发布测试版本
5. 验证测试版本安装
6. 运行 `./scripts/release/release.sh prod` 发布正式版本

## 故障排除

### 编译错误
如果遇到 grpcio 编译错误，这是正常的，可以：
- 使用预编译的 wheel 包
- 或者忽略编译错误，专注于下载安装测试

### 依赖问题
如果遇到依赖问题：
1. 确保在正确的 conda 环境中
2. 运行 `make install-dev-deps` 安装所有依赖
3. 检查 `pyproject.toml` 中的依赖配置
