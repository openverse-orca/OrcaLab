# OrcaLab 开发常见问题

本文档整理了 OrcaLab 开发过程中常见的问题和解决方案。

## 异步函数与阻塞函数

### 问题描述

阻塞函数（如 `QDialog.exec()`）不应在异步函数中直接调用。这会以奇怪的方式停止异步循环，导致应用出现卡顿或无响应的情况。

### 解决方法

有两种推荐的解决方法：

#### 方法一：使用 `qasync.asyncWrap` 包装

```python
from qasync import asyncWrap

async def foo():
    def bloc_task():
        return dialog.exec()
    
    await asyncWrap(bloc_task)
```

#### 方法二：通过 Qt 信号调用

```python
def bloc_task():
    return dialog.exec()

some_signal.connect(bloc_task)
```

### 选择建议

- **`asyncWrap`**：适合在异步函数中需要执行阻塞操作的场景，保持代码流程的顺序性
- **信号连接**：适合与 Qt 事件系统紧密集成的场景，更符合 Qt 的事件驱动模式

## 常见开发问题

### 1. 修改源代码后需要重新安装吗？

不需要。在开发模式下安装（`pip install -e .`）会创建一个到源代码目录的符号链接，修改源代码后无需重新安装，重启应用即可生效。

### 2. 如何调试应用？

可以直接运行 `python orcalab/main.py` 来启动应用，这样可以更方便地查看错误堆栈跟踪。

### 3. orcalab-pyside 更新了怎么办？

如果使用本地开发版本的 `orcalab-pyside`，修改 `python_project_path` 后必须手动运行 `orcalab-post-install` 来更新安装。

### 4. 依赖版本冲突

使用虚拟环境隔离不同项目的依赖：
```bash
python -m venv orca_env
source orca_env/bin/activate
pip install -e .
```

## 更多问题？

如有其他开发相关问题，请参考：
- [开发安装指南](./DEVELOPMENT_INSTALLATION.md)
- [场景布局说明](./scene_layout_overview.md)

