# Release Scripts

这个目录包含了 OrcaLab 发布到 PyPI 的所有脚本。

## 环境要求

- Python 3.12+
- pip

### 核心构建工具
```bash
pip install build twine wheel setuptools
```

### 开发工具（可选）
```bash
pip install pytest pytest-cov flake8 black mypy
```

### 快速开发环境设置
```bash
# 安装开发依赖
pip install build twine wheel setuptools pytest pytest-cov flake8 black mypy

# 或使用项目的可选依赖
pip install -e "[dev]"
```

### 各命令的包依赖

| 命令 | 必需的 pip 包 | 说明 |
|------|-------------|------|
| `make build` | `build`, `setuptools`, `wheel` | 构建分发包 |
| `make check` | `twine` | 检查包质量 |
| `make test-install` | `build`, `setuptools`, `wheel` | 测试本地安装 |
| `make test-install-testpypi` | `build`, `setuptools`, `wheel` | 测试 TestPyPI 安装 |
| `make test-install-pypi` | `build`, `setuptools`, `wheel` | 测试 PyPI 安装 |
| `make release-test` | `build`, `twine`, `setuptools`, `wheel` | 发布到 TestPyPI |
| `make release-prod` | `build`, `twine`, `setuptools`, `wheel` | 发布到 PyPI |
| `make bump-version` | 无（使用 sed） | 更新版本号 |
| `make setup-pypirc` | 无 | 设置 PyPI 配置文件 |
| `make check-pypirc` | 无 | 检查 PyPI 配置 |
| `make clean` | 无 | 清理构建产物 |
| `make test` | `pytest`, `pytest-cov` | 运行测试 |
| `make format` | `black` | 格式化代码 |
| `make lint` | `flake8`, `mypy` | 代码检查 |

## 包名说明

- **正式包**: `orca-lab` - 发布到 PyPI
- **测试包**: `orca-lab` - 发布到 TestPyPI (使用相同包名以便完整测试)

## 环境配置差异

构建脚本会自动处理不同环境的配置：

| 环境 | 目录 | 配置URL |
|------|------|---------|
| **生产环境** (PyPI) | `dist/` | `https://simassets.orca3d.cn/` |
| **测试环境** (TestPyPI) | `dist-test/` | `http://47.100.47.219/` |

测试包在构建时会自动替换 `orca.config.toml` 中的以下配置：
- `[datalink].base_url`: `https://simassets.orca3d.cn/api` → `http://47.100.47.219/api`
- `[datalink].web_server_url`: `https://simassets.orca3d.cn/` → `http://47.100.47.219/`

## 🚀 快速开始

### 1. 首次发布到 TestPyPI

```bash
# 完整流程（推荐）
./scripts/release/release.sh test

# 或者分步执行
./scripts/release/clean.sh
./scripts/release/build.sh
./scripts/release/check.sh
./scripts/release/upload_test.sh
```

### 2. 测试安装

```bash
# 从本地 dist/ 测试
./scripts/release/test_install.sh local

# 从 TestPyPI 测试
./scripts/release/test_install.sh test

# 从正式 PyPI 测试
./scripts/release/test_install.sh prod
```

### 3. 发布到正式 PyPI

```bash
./scripts/release/release.sh prod
```

### 4. 使用 Make 命令（便捷方式）

```bash
# 配置 PyPI 认证
make setup-pypirc

# 完整发布流程
make release-test  # 发布到 TestPyPI
make release-prod  # 发布到 PyPI

# 分步执行
make clean
make build
make check
make test-install
make release-test
```

## 版本管理

### 更新版本号
```bash
make bump-version VERSION=25.9.1
```

### 手动更新版本
编辑 `pyproject.toml` 文件中的 `version` 字段。

## 脚本说明

### 核心脚本

- **`build.sh`**: 构建正式包和测试包
  - 正式包（dist/）: 使用生产环境配置
  - 测试包（dist-test/）: 自动将配置中的 `https://simassets.orca3d.cn/` 替换为 `http://47.100.47.219/`
- **`upload_test.sh`**: 上传到 TestPyPI
- **`upload_prod.sh`**: 上传到 PyPI
- **`release.sh`**: 完整的发布流程

### 辅助脚本

- **`clean.sh`**: 清理构建文件
- **`check.sh`**: 检查包质量
- **`bump_version.sh`**: 更新版本号
- **`test_install.sh`**: 测试本地安装
- **`test_download_install.sh`**: 测试下载安装

## 配置文件

### pyproject.toml
包含项目的所有元数据和依赖配置。

### MANIFEST.in
控制哪些文件被包含在分发包中。

## 发布前检查清单

1. ✅ 更新版本号
2. ✅ 更新 CHANGELOG.md (如果有)
3. ✅ 提交所有更改
4. ✅ 创建 git tag
5. ✅ 运行测试
6. ✅ 构建包
7. ✅ 检查包质量
8. ✅ 测试安装
9. ✅ 发布到 TestPyPI
10. ✅ 验证 TestPyPI 安装
11. ✅ 发布到 PyPI


## PyPI 认证配置

### 自动配置（推荐）
```bash
# 使用提供的脚本自动设置
make setup-pypirc
```

### 手动配置

#### 1. 复制配置文件
```bash
cp scripts/release/.pypirc.example ~/.pypirc
```

#### 2. 编辑配置文件
```bash
vim ~/.pypirc
```

#### 3. 设置权限
```bash
chmod 600 ~/.pypirc
```

### 获取 API Token

#### TestPyPI
1. 访问 https://test.pypi.org/manage/account/token/
2. 创建 API token
3. 使用 `__token__` 作为用户名，token 作为密码

### PyPI
1. 访问 https://pypi.org/manage/account/token/
2. 创建 API token
3. 使用 `__token__` 作为用户名，token 作为密码

## 故障排除

### 构建失败
- 检查 `pyproject.toml` 配置
- 确保所有依赖都可用
- 检查 `MANIFEST.in` 文件

### 上传失败
- 检查网络连接
- 验证认证信息
- 确保包名唯一

### 安装测试失败
- 检查依赖版本兼容性
- 验证包内容完整性

## 下载安装测试

### 测试从 TestPyPI 下载安装
```bash
make test-download-testpypi
```

### 测试从 PyPI 下载安装
```bash
make test-download-pypi
```

### 手动测试安装命令

#### 从 TestPyPI 安装
```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ orca-lab
```

#### 从 PyPI 安装
```bash
pip install orca-lab
```

## 示例工作流

```bash
# 1. 更新版本
make bump-version VERSION=25.9.1

# 2. 提交更改
git add .
git commit -m "Bump version to 25.9.1"
git tag -a v25.9.1 -m "Release v25.9.1"
git push && git push --tags

# 3. 发布到 TestPyPI
make release-test

# 4. 测试从 TestPyPI 下载安装
make test-download-testpypi

# 5. 发布到 PyPI
make release-prod

# 6. 测试从 PyPI 下载安装
make test-download-pypi
```

## 注意事项

- 发布到 PyPI 是不可逆的操作
- 建议先在 TestPyPI 上测试
- 确保版本号遵循语义化版本规范
- 保持 `orca-lab` 包名在 PyPI 和 TestPyPI 上的一致性
