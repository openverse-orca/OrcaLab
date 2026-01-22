---
layout: default
title: OrcaLab API Reference
---

# OrcaLab API Reference

> 本文件是 **OrcaLab API Reference**，用于开发者快速查接口，也便于 AI 检索与引用。  
> 文档范围以 `orcalab` 里 **相对稳定的核心架构（Event Bus + Actor + CRUD + 元数据）** 为主。

## 0. 文档导航（索引/细节）

本仓库的 API 文档分为两层，本文件属于"摘要 + 关键链路（Recipes）"。需要全量符号索引、完整签名与详细说明时，跳转到下列文档：

- **API Detail（细节参考）**：每个符号包含 **签名 + 详细说明 + 使用示例**（用于工具无法读代码时的"离线参考"）  
  - [api_detail/INDEX.md](INDEX.md)

## 目录

- [OrcaLab API Reference](#orcalab-api-reference)
  - [0. 文档导航（索引/细节）](#0-文档导航索引细节)
  - [目录](#目录)
  - [1. 总览](#1-总览)
  - [2. 关键概念与术语](#2-关键概念与术语)
    - [2.1 Actor 体系](#21-actor-体系)
    - [2.2 Event Bus 架构](#22-event-bus-架构)
    - [2.3 路径系统](#23-路径系统)
  - [3. 顶层公共入口 (`orcalab`)](#3-顶层公共入口-orcalab)
  - [4. Core API](#4-core-api)
    - [4.1 Event Bus 系统](#41-event-bus-系统)
      - [4.1.1 方法字典（按主题分组）](#411-方法字典按主题分组)
        - [A) 创建与连接](#a-创建与连接)
        - [B) 调用方法](#b-调用方法)
        - [C) 返回值处理](#c-返回值处理)
    - [4.2 Actor 体系](#42-actor-体系)
      - [4.2.1 常见字段（概念上，非完整列表）](#421-常见字段概念上非完整列表)
      - [4.2.2 常用方法（按用途分组）](#422-常用方法按用途分组)
        - [A) 创建 Actor](#a-创建-actor)
        - [B) 父子关系管理](#b-父子关系管理)
        - [C) 变换操作](#c-变换操作)
    - [4.3 Path 系统](#43-path-系统)
    - [4.4 Transform 系统](#44-transform-系统)
    - [4.5 LocalScene（场景管理）](#45-localscene场景管理)
  - [5. CRUD API](#5-crud-api)
    - [5.1 SceneEditRequestBus（场景编辑请求）](#51-sceneeditrequestbus场景编辑请求)
      - [5.1.1 方法字典（CRUD 操作）](#511-方法字典crud-操作)
        - [A) 创建操作](#a-创建操作)
        - [B) 读取操作](#b-读取操作)
        - [C) 更新操作](#c-更新操作)
        - [D) 删除操作](#d-删除操作)
        - [E) 选择操作](#e-选择操作)
        - [F) 编辑模式](#f-编辑模式)
    - [5.2 SceneEditNotificationBus（场景编辑通知）](#52-sceneeditnotificationbus场景编辑通知)
  - [6. 元数据 API](#6-元数据-api)
    - [6.1 MetadataServiceRequestBus（本地元数据）](#61-metadataservicerequestbus本地元数据)
    - [6.2 HttpServiceRequestBus（远程元数据）](#62-httpservicerequestbus远程元数据)
  - [7. 典型调用链（Recipes）](#7-典型调用链recipes)
    - [7.1 Actor 创建链：从资产到场景](#71-actor-创建链从资产到场景)
    - [7.2 Actor 变换链：本地坐标与世界坐标](#72-actor-变换链本地坐标与世界坐标)
    - [7.3 选择与操作链：多选、拖拽、属性编辑](#73-选择与操作链多选拖拽属性编辑)
    - [7.4 元数据查询链：从服务器到本地缓存](#74-元数据查询链从服务器到本地缓存)
    - [7.5 撤销/重做链：操作历史管理](#75-撤销重做链操作历史管理)
  - [8. 常见问题自检表](#8-常见问题自检表)

---

## 1. 总览

OrcaLab 的核心形态是：**Event Bus 驱动的场景编辑系统**，通过 **gRPC** 与 OrcaSim 服务端通信，并通过 **HTTP** 与 SimAssets 服务器同步资产元数据。

最常见的对象关系：

- `local_scene: LocalScene`：本地场景对象，管理 Actor 树和选择状态
- `SceneEditRequestBus`：场景编辑请求总线，执行 CRUD 操作
- `SceneEditNotificationBus`：场景编辑通知总线，监听编辑事件
- `MetadataServiceRequestBus`：元数据服务请求总线，查询资产信息
- `HttpServiceRequestBus`：HTTP 服务请求总线，与服务器同步元数据

---

## 2. 关键概念与术语

- **Actor**：场景中的对象，分为 `BaseActor`（基类）、`AssetActor`（资产 Actor）、`GroupActor`（组 Actor）
- **Path**：Actor 在场景树中的路径，格式为 `/Scene/ActorName`，类似文件系统路径
- **Transform**：Actor 的变换信息，包含位置（pos）、旋转（quat）、缩放（scale）
- **本地坐标 vs 世界坐标**：Actor 的变换可以是相对于父对象的（本地）或世界坐标系的（世界）
- **Event Bus**：事件总线系统，用于解耦组件间通信，支持多处理器注册
- **撤销/重做**：所有编辑操作默认支持撤销，通过 `UndoService` 管理
- **元数据**：资产的描述信息，包括名称、ID、路径、图片 URL 等

### 2.1 Actor 体系

OrcaLab 的场景由 **Actor 树**组成，每个 Actor 都有：

- **名称**：唯一标识符（在同一父对象下唯一）
- **路径**：从根到该 Actor 的完整路径（如 `/Scene/MyBox`）
- **变换**：位置、旋转、缩放（本地或世界坐标）
- **父对象**：父 Actor（`GroupActor` 或 `None`）
- **子对象**：子 Actor 列表（仅 `GroupActor` 有）

**Actor 类型**：

- `BaseActor`：所有 Actor 的基类，提供名称、路径、变换等基础功能
- `GroupActor`：组 Actor，可以包含子 Actor，用于组织场景结构
- `AssetActor`：资产 Actor，从资产库加载的具体对象，包含资产路径和属性组

### 2.2 Event Bus 架构

Event Bus 采用**发布-订阅模式**，核心特点：

- **单例模式**：每个接口只有一个 Event Bus 实例
- **多处理器支持**：可以注册多个处理器，调用时所有处理器都会被调用
- **同步/异步支持**：自动识别同步和异步方法
- **输出参数**：由于支持多处理器，返回值会被忽略，需要通过输出参数获取结果

**常见 Event Bus**：

- `SceneEditRequestBus`：场景编辑请求（CRUD 操作）
- `SceneEditNotificationBus`：场景编辑通知（事件监听）
- `MetadataServiceRequestBus`：元数据服务请求（本地查询）
- `HttpServiceRequestBus`：HTTP 服务请求（远程同步）
- `AssetServiceRequestBus`：资产服务请求（下载）

### 2.3 路径系统

Path 用于标识 Actor 在场景树中的位置，类似文件系统路径：

- **根路径**：`/`（场景根）
- **完整路径**：`/Scene/MyBox`（从根到 Actor）
- **路径操作**：`append()`、`parent()`、`name()`、`is_descendant_of()`

路径命名规则：

- 只能包含字母、数字、下划线
- 不能以数字开头（会自动添加 `_` 前缀）
- 路径必须从 `/` 开始

---

## 3. 顶层公共入口 (`orcalab`)

文件：`orcalab/__init__.py`

主要模块：

- `orcalab.actor`：Actor 体系（`BaseActor`、`GroupActor`、`AssetActor`）
- `orcalab.path`：路径系统（`Path`）
- `orcalab.math`：数学工具（`Transform`）
- `orcalab.event_bus`：事件总线（`create_event_bus`）
- `orcalab.scene_edit_bus`：场景编辑总线
- `orcalab.metadata_service_bus`：元数据服务总线
- `orcalab.local_scene`：本地场景（`LocalScene`）

---

## 4. Core API

### 4.1 Event Bus 系统

文件：`orcalab/event_bus.py`

用途：

- 提供事件总线的基础实现
- 支持多处理器注册和调用
- 自动处理同步和异步方法

核心 API：

- `create_event_bus(interface)`：创建事件总线
- `bus.connect(handler)`：连接处理器
- `bus.disconnect(handler)`：断开处理器

#### 4.1.1 方法字典（按主题分组）

##### A) 创建与连接

- `create_event_bus(interface: Type[T]) -> EventBusProxy[T]`：创建单例事件总线
- `bus.connect(handler: T)`：注册处理器
- `bus.disconnect(handler: T)`：移除处理器

##### B) 调用方法

- `bus.sync_method(*args, **kwargs)`：调用同步方法（所有处理器）
- `await bus.async_method(*args, **kwargs)`：调用异步方法（所有处理器）

##### C) 返回值处理

- 使用输出参数：`output = []` → `bus.get_value(output)` → `value = output[0]`

**详细说明**：见 [event_bus.md](event_bus.md)

---

### 4.2 Actor 体系

文件：`orcalab/actor.py`

用途：

- 定义场景中的对象（Actor）
- 管理 Actor 的层次结构（父子关系）
- 处理 Actor 的变换（位置、旋转、缩放）

#### 4.2.1 常见字段（概念上，非完整列表）

**BaseActor**：

- `name`：Actor 名称（字符串，在同一父对象下唯一）
- `parent`：父 Actor（`GroupActor` 或 `None`）
- `transform`：本地变换（相对于父对象）
- `world_transform`：世界变换（缓存，自动计算）

**GroupActor**：

- `children`：子 Actor 列表（只读副本）

**AssetActor**：

- `asset_path`：资产路径（小写，无 `.spawnable` 后缀）
- `property_groups`：属性组列表

#### 4.2.2 常用方法（按用途分组）

##### A) 创建 Actor

- `AssetActor(name, asset_path, parent=None)`：创建资产 Actor
- `GroupActor(name, parent=None)`：创建组 Actor

##### B) 父子关系管理

- `parent`（property）：获取/设置父 Actor（自动更新双向引用）
- `GroupActor.add_child(child)`：添加子 Actor
- `GroupActor.insert_child(index, child)`：插入子 Actor
- `GroupActor.remove_child(child)`：移除子 Actor

##### C) 变换操作

- `transform`（property）：本地变换（相对于父对象，返回深拷贝）
- `world_transform`（property）：世界变换（自动计算，缓存机制）

**详细说明**：见 [actor_design.md](actor_design.md)

---

### 4.3 Path 系统

文件：`orcalab/path.py`

核心方法：`Path(path="/")` / `append(name)` / `parent()` / `name()` / `is_descendant_of(parent_path)` / `string()`

**详细说明**：见 [actor_design.md](actor_design.md#路径系统path)

---

### 4.4 Transform 系统

文件：`orcalab/math.py`

核心字段：`position`（3元素） / `rotation`（4元素，单位四元数） / `scale`（标量）

核心操作：`transform1 * transform2`（组合） / `transform.inverse()`（逆变换）

**详细说明**：见 [actor_design.md](actor_design.md#变换系统transform)

---

### 4.5 LocalScene（场景管理）

文件：`orcalab/local_scene.py`

核心字段：`root_actor`（根 Actor） / `_actors`（路径映射） / `selection`（选中列表）

核心方法：`find_actor_by_path(path)` / `get_actor_path(actor)` / `get_actor_and_path(actor)` / `add_actor()` / `delete_actor()` / `rename_actor()` / `reparent_actor()`

**详细说明**：见 [actor_design.md](actor_design.md#localscene-中的-actor-管理)

---

## 5. CRUD API

### 5.1 SceneEditRequestBus（场景编辑请求）

文件：`orcalab/scene_edit_bus.py`

用途：

- 执行场景编辑操作（创建、读取、更新、删除）
- 所有操作都支持撤销/重做
- 操作会触发相应的通知事件

#### 5.1.1 方法字典（CRUD 操作）

##### A) 创建操作

- `async add_actor(actor, parent_actor, undo=True, source="")`：添加 Actor 到场景

##### B) 读取操作

- 通过 `LocalScene`：`find_actor_by_path(path)` / `get_actor_path(actor)` / `selection`

##### C) 更新操作

- `async rename_actor(actor, new_name, undo=True, source="")`：重命名 Actor
- `async reparent_actor(actor, new_parent, row, undo=True, source="")`：改变父对象
- `async set_transform(actor, transform, local, undo=True, source="")`：设置变换
- `async set_property(property_key, value, undo, source="")`：设置属性

##### D) 删除操作

- `async delete_actor(actor, undo=True, source="")`：删除 Actor（不能删除正在编辑的）

##### E) 选择操作

- `async set_selection(selection, undo=True, source="")`：设置选中列表

##### F) 编辑模式

- `start_change_transform(actor)` / `end_change_transform(actor)`：变换编辑（拖拽模式）
- `start_change_property(property_key)` / `end_change_property(property_key)`：属性编辑（拖拽模式）

**详细说明**：见 [crud_operations.md](crud_operations.md)

---

### 5.2 SceneEditNotificationBus（场景编辑通知）

文件：`orcalab/scene_edit_bus.py`

用途：

- 监听场景编辑事件
- 用于 UI 更新、远程同步等

主要事件：

- `on_selection_changed(old_selection, new_selection, source)`
- `on_actor_added(actor, parent_actor_path, source)`
- `on_actor_deleted(actor_path, source)`
- `on_actor_renamed(actor_path, new_name, source)`
- `on_transform_changed(actor_path, transform, local, source)`
- `on_property_changed(property_key, value, source)`

---

## 6. 元数据 API

### 6.1 MetadataServiceRequestBus（本地元数据）

文件：`orcalab/metadata_service_bus.py`

主要方法：

- `reload_metadata()`：重新加载元数据文件
- `get_asset_info(asset_path, output)`：获取资产信息
- `get_asset_map(output)`：获取所有资产映射
- `update_asset_info(asset_path, asset_info)`：更新资产信息

### 6.2 HttpServiceRequestBus（远程元数据）

文件：`orcalab/http_service/http_bus.py`

主要方法：

- `async get_all_metadata(output)`：获取所有元数据
- `async get_subscription_metadata(output)`：获取订阅元数据
- `async get_subscriptions(output)`：获取订阅列表
- `async get_image_url(asset_id)`：获取图片 URL

**详细说明**：见 [metadata_api.md](metadata_api.md)

---

## 7. 典型调用链（Recipes）

本节是"开发者真正怎么把这些 API 串起来"的最小闭环，重点解决：

- **什么时候 Actor 被创建？什么时候路径被更新？**
- **本地坐标和世界坐标如何转换？**
- **如何查询和同步元数据？**

### 7.1 Actor 创建链：从资产到场景

典型顺序：

```
查询元数据 → 创建 AssetActor → 添加到场景
  MetadataServiceRequestBus().get_asset_info("box", output)
  actor = AssetActor("MyBox", "box")
  await SceneEditRequestBus().add_actor(actor, parent_path)
```

**详细代码**：见 [crud_operations.md](crud_operations.md#创建操作-create)

### 7.2 Actor 变换链：本地坐标与世界坐标

典型顺序：

```
设置本地变换 → 获取世界变换（自动计算）
  actor.transform = Transform(...)  # 本地坐标
  world = actor.world_transform     # 自动：parent.world_transform * transform

设置世界变换 → 自动计算本地变换
  actor.world_transform = Transform(...)  # 世界坐标
  # 自动：local = parent.world_transform.inverse() * world_transform
```

**核心机制**：`world_transform` 使用缓存，修改 `transform` 或 `parent` 时自动失效。

**详细说明**：见 [actor_design.md](actor_design.md#actor-的变换系统)

### 7.3 选择与操作链：多选、拖拽、属性编辑

典型顺序（拖拽模式）：

```
设置选择 → 开始编辑 → 多次更新（undo=False） → 最后更新（undo=True） → 结束编辑
  set_selection([path1, path2])
  start_change_transform(actor_path)
  set_transform(..., undo=False)  # 多次
  set_transform(..., undo=True)   # 最后一次
  end_change_transform(actor_path)
```

**拖拽模式**：避免每次中间更新都记录撤销，只在结束时记录一次。

**详细说明**：见 [crud_operations.md](crud_operations.md#更新操作-update)

### 7.4 元数据查询链：从服务器到本地缓存

典型顺序：

```
服务器获取 → 解析更新 → 本地查询
  await HttpServiceRequestBus().get_subscription_metadata(output)
  metadata = json.loads(output[0])
  for asset_info in metadata[...]['children']:
      asset_path = asset_info['assetPath'].removesuffix('.spawnable').lower()
      MetadataServiceRequestBus().update_asset_info(asset_path, asset_info)
  MetadataServiceRequestBus().get_asset_info("box", output)
```

**详细代码**：见 [metadata_api.md](metadata_api.md#完整使用流程)

### 7.5 撤销/重做链：操作历史管理

典型顺序：

```
执行操作（undo=True） → 自动记录 → 撤销/重做
  await SceneEditRequestBus().add_actor(..., undo=True)
  # 内部：UndoRequestBus().add_command(command)
  UndoRequestBus().undo()  # 或 .redo()
```

**默认行为**：所有 CRUD 操作默认 `undo=True`，自动记录到撤销栈。

**详细说明**：见 [crud_operations.md](crud_operations.md#撤销重做)

---

## 8. 常见问题自检表

若出现"Actor 找不到 / 路径不对 / 变换异常"，优先检查：

- 是否使用了正确的路径格式（从 `/` 开始）？
- 是否在设置变换后正确更新了缓存（`world_transform` 会自动失效）？
- 是否在异步操作中使用了 `await`？
- 是否在查询元数据时使用了输出参数？

---

