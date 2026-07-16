# OrcaLab AI 开发指南

本文件为 AI 代理（如 Trae、Cursor 等）在本仓库工作时提供强制规则。AI 代理必须严格遵守。

## 规则 1：测试与调试环境

AI 代理执行测试、调试、运行脚本时，**必须使用 `orca` conda 环境**。

```bash
# 正确
conda activate orca
python -m pytest test/...

# 错误 — 不要使用 base 或其他环境
conda activate base
python some_script.py
```

`orca` 是推荐的环境名称，已安装本项目所有依赖。使用其他环境会导致依赖缺失或版本不一致。

## 规则 2：API 隔离强制

本仓库是独立的机器人仿真应用平台，采用 `_` 前缀社区约定 + ruff SLF001 静态检查，引导 AI 和用户走公共 API，禁止穿墙访问内部私有字段。

### 禁止穿墙访问

不得访问任何自研类的 `_` 前缀内部属性（类内部合法的 `self._xxx` 委托除外）。OrcaLab 典型主干类的内部字段举例：

- `BaseActor`：`actor._parent` / `actor._children` / `actor._entity_root` — Actor 树内部状态
- `EventBus`：`EventBus._instance` / `EventBus._init()` / `proxy._connect()` — 单例与代理内部机制
- `SceneEditService` / `MetadataService` / `ConfigService`：`service._xxx` — 各 service 内部成员
- `MainWindow` / 各 UI 子组件：`widget._xxx` — UI 内部状态

### 必须使用公共 API

| 操作 | 正确 | 禁止 |
|------|------|------|
| 访问 Actor 父节点 | `actor.parent` | `actor._parent` |
| 访问 Actor 子节点 | `actor.children` / `actor.add_child(c)` / `actor.remove_child(c)` | `actor._children.append(c)` |
| 订阅事件 | `EventBus.connect(handler)` / `EventBus.disconnect(handler)` | `EventBus._instance._connect(handler)` |
| 读写 Actor 属性 | `actor.name` / `actor.transform` / `actor.is_visible` | `actor._name` / `actor._transform` |
| 调用 service 功能 | service 暴露的公共方法 | `service._internal_method(...)` |

### 必须执行 ruff

提交代码前必须执行，零报警方可提交：

    <conda-base>/envs/orca/bin/python -m ruff check --select SLF001 orcalab/

> `orcalab/protos/edit_service_pb2*.py` 为 protobuf 生成文件，已在 `pyproject.toml` 的 `exclude` 中排除，无需手工处理。

### 缺失功能时扩展公共方法

若公共 API 不满足需求，**暂停并提交用户决策**，不要穿墙访问内部属性。扩展途径：
- 在相关类（`BaseActor` / `EventBus` / 各 service / 各 UI 组件）中添加公共方法或访问器
- 跨模块协作通过已暴露的公共接口完成，不要互相伸手到 `_` 前缀字段
