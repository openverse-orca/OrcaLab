---
layout: default
title: API Detailed Reference - Event Bus System
---

# API Detailed Reference: Event Bus System

> **📖 这是什么文档？**  
> 这是 OrcaLab 事件总线（Event Bus）系统的详细 API 参考，包含事件总线的设计原理、使用方法和所有相关的 CRUD 和元数据操作接口。

> **💡 使用提示**  
> Event Bus 是 OrcaLab 的核心架构模式，用于解耦组件之间的通信。所有服务都通过 Event Bus 进行交互。

---

## 事件总线架构

### 设计原理

Event Bus 采用**发布-订阅模式**，允许多个处理器（Handler）注册到同一个接口，当调用接口方法时，所有注册的处理器都会被调用。

**核心特点**:
- **单例模式**: 每个接口只有一个 Event Bus 实例
- **多处理器支持**: 可以注册多个处理器
- **同步/异步支持**: 自动识别同步和异步方法
- **类型安全**: 通过接口定义确保类型安全

### 返回值处理

由于 Event Bus 支持多个处理器，接口方法的返回值会被忽略（返回 `None`）。如果需要返回值，可以通过**输出参数**的方式：

```python
def get_value(self, output: List[str] = None) -> str:
    pass
```

调用时传入一个列表，结果会被收集到列表中：

```python
output = []
bus.get_value(output)
value = output[0] if output else None
```

---

## 核心 API

### create_event_bus

创建事件总线。

**函数签名**:
```python
def create_event_bus[T](interface: Type[T]) -> EventBusProxy[T]
```

**参数**:
- `interface`: 接口类（必须是一个类）

**返回**:
- `EventBusProxy[T]`: 事件总线代理对象

**说明**:
- 为指定的接口创建一个单例的事件总线
- 自动识别接口中的同步和异步方法
- 返回的代理对象可以调用接口中定义的所有方法

**使用示例**:
```python
from orcalab.event_bus import create_event_bus

class MyInterface:
    def sync_method(self, arg: str) -> None:
        pass
    
    async def async_method(self, arg: int) -> None:
        pass

MyBus = create_event_bus(MyInterface)
```

---

## 事件总线操作

### connect

连接处理器到事件总线。

**方法签名**:
```python
@classmethod
def connect(cls, handler: T) -> None
```

**参数**:
- `handler`: 实现了接口的处理器对象

**说明**:
- 将处理器注册到事件总线
- 处理器必须实现接口中定义的所有方法
- 可以注册多个处理器

**使用示例**:
```python
class MyHandler(MyInterface):
    def sync_method(self, arg: str) -> None:
        print(f"处理: {arg}")
    
    async def async_method(self, arg: int) -> None:
        print(f"异步处理: {arg}")

handler = MyHandler()
MyBus.connect(handler)
```

### disconnect

从事件总线断开处理器。

**方法签名**:
```python
@classmethod
def disconnect(cls, handler: T) -> None
```

**参数**:
- `handler`: 要断开的处理器对象

**说明**:
- 从事件总线移除处理器
- 如果处理器未注册，操作会被忽略

**使用示例**:
```python
MyBus.disconnect(handler)
```

### 调用方法

通过事件总线调用接口方法。

**同步方法**:
```python
bus.sync_method("参数")
```

**异步方法**:
```python
await bus.async_method(123)
```

**说明**:
- 所有注册的处理器都会被调用
- 调用顺序与注册顺序相同
- 如果某个处理器抛出异常，不会影响其他处理器的执行

---

## 场景编辑 Event Bus

### SceneEditRequestBus

场景编辑请求总线，用于执行场景编辑操作（CRUD）。

**接口**: `SceneEditRequest`

**主要操作**:
- Actor 的创建、删除、重命名、重父化
- 选择操作
- 变换设置
- 属性修改

**使用示例**:
```python
from orcalab.scene_edit_bus import SceneEditRequestBus
from orcalab.actor import AssetActor
from orcalab.path import Path

# 添加 Actor
actor = AssetActor("Box", "box")
parent_path = Path("/Scene")
await SceneEditRequestBus().add_actor(actor, parent_path, undo=True, source="script")

# 删除 Actor
actor_path = Path("/Scene/Box")
await SceneEditRequestBus().delete_actor(actor_path, undo=True, source="script")

# 设置选择
selection = [Path("/Scene/Box1"), Path("/Scene/Box2")]
await SceneEditRequestBus().set_selection(selection, undo=True, source="script")
```

### SceneEditNotificationBus

场景编辑通知总线，用于监听场景编辑事件。

**接口**: `SceneEditNotification`

**主要事件**:
- `on_selection_changed`: 选择改变
- `on_actor_added`: Actor 添加
- `on_actor_deleted`: Actor 删除
- `on_actor_renamed`: Actor 重命名
- `on_transform_changed`: 变换改变
- `on_property_changed`: 属性改变

**使用示例**:
```python
from orcalab.scene_edit_bus import SceneEditNotificationBus
from orcalab.path import Path

class MyListener(SceneEditNotification):
    async def on_actor_added(self, actor, parent_actor_path, source):
        print(f"Actor {actor.name} 已添加到 {parent_actor_path}")
    
    async def on_selection_changed(self, old_selection, new_selection, source):
        print(f"选择从 {old_selection} 变为 {new_selection}")

listener = MyListener()
SceneEditNotificationBus().connect(listener)
```

---

## 元数据 Event Bus

### MetadataServiceRequestBus

元数据服务请求总线，用于查询和管理资产元数据。

**接口**: `MetadataServiceRequest`

**主要操作**:
- `reload_metadata()`: 重新加载元数据
- `get_asset_info()`: 获取资产信息
- `get_asset_map()`: 获取所有资产映射
- `update_asset_info()`: 更新资产信息

**使用示例**:
```python
from orcalab.metadata_service_bus import MetadataServiceRequestBus

# 获取资产信息
output = []
asset_info = MetadataServiceRequestBus().get_asset_info("box", output)
if output:
    print(f"资产名称: {output[0]['name']}")

# 获取所有资产映射
output = []
asset_map = MetadataServiceRequestBus().get_asset_map(output)
if output:
    for path, info in output[0].items():
        print(f"{path}: {info['name']}")

# 更新资产信息
new_info = {
    "id": "asset_123",
    "name": "My Box",
    "assetPath": "Box.spawnable"
}
MetadataServiceRequestBus().update_asset_info("box", new_info)
```

---

## HTTP 服务 Event Bus

### HttpServiceRequestBus

HTTP 服务请求总线，用于与 SimAssets 服务器通信。

**接口**: `HttpServiceRequest`

**主要操作**:
- `get_all_metadata()`: 获取所有元数据
- `get_subscription_metadata()`: 获取订阅元数据
- `get_subscriptions()`: 获取订阅列表
- `get_image_url()`: 获取图片 URL
- `post_asset_thumbnail()`: 上传缩略图

**使用示例**:
```python
from orcalab.http_service.http_bus import HttpServiceRequestBus

# 获取所有元数据
output = []
metadata_json = await HttpServiceRequestBus().get_all_metadata(output)
if output:
    import json
    metadata = json.loads(output[0])
    print(f"共有 {len(metadata)} 个资产包")

# 获取订阅元数据
output = []
subscription_metadata = await HttpServiceRequestBus().get_subscription_metadata(output)
if output:
    import json
    data = json.loads(output[0])
    print(f"订阅了 {len(data)} 个资产包")
```

---

## 资产服务 Event Bus

### AssetServiceRequestBus

资产服务请求总线，用于下载资产。

**接口**: `AssetServiceRequest`

**主要操作**:
- `download_asset_to_file()`: 下载资产到文件
- `download_asset_to_cache()`: 下载资产到缓存

**使用示例**:
```python
from orcalab.asset_service_bus import AssetServiceRequestBus

# 下载资产到缓存
url = "https://simassets.orca3d.cn/api/assets/123/download"
await AssetServiceRequestBus().download_asset_to_cache(url)
```

### AssetServiceNotificationBus

资产服务通知总线，用于监听资产下载事件。

**接口**: `AssetServiceNotification`

**主要事件**:
- `on_asset_downloaded`: 资产下载完成

**使用示例**:
```python
from orcalab.asset_service_bus import AssetServiceNotificationBus

class MyListener(AssetServiceNotification):
    async def on_asset_downloaded(self, file: str) -> None:
        print(f"资产已下载到: {file}")

listener = MyListener()
AssetServiceNotificationBus().connect(listener)
```

---

## 应用 Event Bus

### ApplicationRequestBus

应用请求总线，用于获取应用级别的资源。

**接口**: `ApplicationRequest`

**主要操作**:
- `get_local_scene()`: 获取本地场景
- `get_remote_scene()`: 获取远程场景
- `get_widget()`: 获取 UI 组件
- `add_item_to_scene()`: 添加项目到场景

**使用示例**:
```python
from orcalab.application_bus import ApplicationRequestBus

# 获取本地场景
output = []
ApplicationRequestBus().get_local_scene(output)
if output:
    local_scene = output[0]
    print(f"场景根路径: {local_scene.root_actor.name}")

# 获取远程场景
output = []
ApplicationRequestBus().get_remote_scene(output)
if output:
    remote_scene = output[0]
    # 使用远程场景...
```

---

## 完整使用示例

### 场景编辑完整流程

```python
import asyncio
from orcalab.scene_edit_bus import (
    SceneEditRequestBus,
    SceneEditNotificationBus,
    SceneEditNotification
)
from orcalab.actor import AssetActor
from orcalab.path import Path
from orcalab.math import Transform

# 1. 创建监听器
class MySceneListener(SceneEditNotification):
    async def on_actor_added(self, actor, parent_actor_path, source):
        print(f"✓ Actor {actor.name} 已添加到 {parent_actor_path}")
    
    async def on_actor_deleted(self, actor_path, source):
        print(f"✓ Actor {actor_path} 已删除")
    
    async def on_selection_changed(self, old_selection, new_selection, source):
        print(f"✓ 选择已改变: {len(new_selection)} 个对象")

listener = MySceneListener()
SceneEditNotificationBus().connect(listener)

# 2. 执行 CRUD 操作
async def main():
    # 创建 Actor
    actor = AssetActor("Box", "box")
    parent_path = Path("/Scene")
    await SceneEditRequestBus().add_actor(actor, parent_path, undo=True, source="script")
    
    # 设置变换
    transform = Transform(
        pos=[1.0, 2.0, 3.0],
        quat=[1.0, 0.0, 0.0, 0.0],
        scale=1.0
    )
    actor_path = Path("/Scene/Box")
    await SceneEditRequestBus().set_transform(actor_path, transform, local=False, undo=True)
    
    # 设置选择
    await SceneEditRequestBus().set_selection([actor_path], undo=True, source="script")
    
    # 删除 Actor
    await SceneEditRequestBus().delete_actor(actor_path, undo=True, source="script")

asyncio.run(main())
```

### 元数据查询完整流程

```python
import asyncio
import json
from orcalab.metadata_service_bus import MetadataServiceRequestBus
from orcalab.http_service.http_bus import HttpServiceRequestBus

async def main():
    # 1. 从服务器获取元数据
    output = []
    metadata_json = await HttpServiceRequestBus().get_subscription_metadata(output)
    
    if output:
        metadata = json.loads(output[0])
        print(f"从服务器获取了 {len(metadata)} 个资产包")
    
    # 2. 查询本地元数据
    output = []
    asset_info = MetadataServiceRequestBus().get_asset_info("box", output)
    if output:
        info = output[0]
        print(f"资产名称: {info.get('name', 'Unknown')}")
        print(f"资产 ID: {info.get('id', 'Unknown')}")
    
    # 3. 获取所有资产映射
    output = []
    asset_map = MetadataServiceRequestBus().get_asset_map(output)
    if output:
        print(f"本地共有 {len(output[0])} 个资产")

asyncio.run(main())
```

---

## 最佳实践

### 1. 使用输出参数获取返回值

```python
# ✅ 正确：使用输出参数
output = []
value = bus.get_value(output)
result = output[0] if output else None

# ❌ 错误：直接使用返回值（会得到 None）
value = bus.get_value()  # 返回 None
```

### 2. 处理异步方法

```python
# ✅ 正确：使用 await
await bus.async_method(arg)

# ❌ 错误：忘记 await
bus.async_method(arg)  # 返回协程对象，不会执行
```

### 3. 错误处理

```python
try:
    await SceneEditRequestBus().add_actor(actor, parent_path)
except Exception as e:
    print(f"添加 Actor 失败: {e}")
```

### 4. 监听器生命周期管理

```python
class MyService:
    def __init__(self):
        self.listener = MyListener()
        SceneEditNotificationBus().connect(self.listener)
    
    def destroy(self):
        SceneEditNotificationBus().disconnect(self.listener)
```

---

## 注意事项

1. **单例模式**: 每个 Event Bus 都是单例，多次调用 `create_event_bus` 返回同一个实例
2. **处理器顺序**: 处理器的调用顺序与注册顺序相同
3. **异常处理**: 如果某个处理器抛出异常，不会影响其他处理器的执行
4. **类型检查**: 处理器必须实现接口中定义的所有方法
5. **异步支持**: Event Bus 自动识别同步和异步方法，无需手动处理

---

## 相关接口

- `SceneEditRequest` / `SceneEditNotification`: 场景编辑
- `MetadataServiceRequest`: 元数据服务
- `HttpServiceRequest`: HTTP 服务
- `AssetServiceRequest` / `AssetServiceNotification`: 资产服务
- `ApplicationRequest`: 应用服务

