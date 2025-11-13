# OrcaLab

OrcaLab 是 OrcaGym 的前端界面，提供场景组装和仿真的用户界面。

## 功能特性

- TODO

## 系统要求

- Python 3.12 或更高版本
- [OrcaGym](https://github.com/your-org/OrcaGym)（必需依赖）
- 其他依赖项请参见 `pyproject.toml`


## 安装

1. 安装 OrcaGym（必需）：
	```bash
	# 请按照 OrcaGym 的安装说明进行安装
	```
2. 克隆此仓库并以可编辑模式安装 OrcaLab：
	```bash
	git clone https://github.com/openverse-orca/OrcaLab.git
	cd OrcaLab
	pip install -e .
	```

### 安装后设置

安装 OrcaLab 后，需要安装 `orcalab-pyside` 包，该包提供额外的 UI 组件。此包不在 PyPI 上提供，必须单独安装。

#### 对于最终用户（自动安装）
`orcalab-pyside` 包将在首次运行 OrcaLab 时自动下载并安装。系统将：
- 从配置的 OSS URL 下载包
- 解压到用户目录
- 在同一 conda 环境中以可编辑模式安装

#### 对于开发者（手动安装）
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

## 使用方法

### 启动方式

安装后使用命令行启动：
```bash
orcalab
```

### 应急启动方式

如果 `orcalab` 命令不可用（例如打包不完整时），可以直接运行 `main.py`：

```bash
# 需要确保在项目根目录
python orcalab/main.py
```


## 发布流程

详细的发布流程和脚本说明请参见 [scripts/release/README.md](scripts/release/README.md)。

## 注意事项

- 阻塞函数（如 QDialog.exec()）不应在异步函数中直接调用。这会以奇怪的方式停止异步循环。有两种解决方法：
	- 用 `qasync.asyncWrap` 包装
	- 通过 qt 信号调用

``` python
# 用 `qasync.asyncWrap` 包装

async def foo():
	def bloc_task():
		return dialog.exec()

	await asyncWrap(bloc_task)	

# 通过 qt 信号调用

def bloc_task():
	return dialog.exec()

some_signal.connect(bloc_task)

```

## 常见问题

TODO

## 许可证

本项目采用 [LICENSE](LICENSE) 文件中规定的许可证条款。