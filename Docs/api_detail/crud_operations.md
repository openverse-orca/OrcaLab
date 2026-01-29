---
layout: default
title: API Detailed Reference - CRUD Operations
---

# API Detailed Reference: CRUD Operations

> **📖 这是什么文档？**  
> 这是 OrcaLab 场景编辑 CRUD（创建、读取、更新、删除）操作的详细 API 参考，所有操作都通过 `SceneEditRequestBus` 执行。

> **💡 使用提示**  
> CRUD 操作支持撤销/重做，所有操作都是异步的，需要通过 `await` 调用。

---

## 概述

OrcaLab 的场景编辑系统提供了完整的 CRUD 操作接口，用于管理场景中的 Actor（对象）。所有操作都通过 `SceneEditRequestBus` 执行，并支持：

- **撤销/重做**: 所有操作默认支持撤销（`undo=True`）
- **事件通知**: 操作会触发相应的通知事件
- **来源标识**: 通过 `source` 参数标识操作来源，避免反馈循环

---

## Actor 类型

### BaseActor

所有 Actor 的基类。

### AssetActor

资产 Actor，从资产库加载的 Actor。

**创建**:
```python
from orcalab.actor import AssetActor

actor = AssetActor(
    name="MyBox",      # Actor 名称
    asset_path="box"  # 资产路径（小写，无 .spawnable 后缀）
)
```

### GroupActor

组 Actor，用于组织其他 Actor 的容器。

**创建**:
```python
from orcalab.actor import GroupActor

group = GroupActor(name="MyGroup", parent=None)
```

---

## 创建操作 (Create)

### add_actor

添加 Actor 到场景中。

**方法签名**:
```python
async def add_actor(
    self,
    actor: BaseActor,
    parent_actor: GroupActor | Path,
    undo: bool = True,
    source: str = "",
) -> None
```

**参数**:
- `actor`: 要添加的 Actor 对象（`AssetActor` 或 `GroupActor`）
- `parent_actor`: 父 Actor 对象或路径（`GroupActor` 或 `Path`）
- `undo`: 是否记录到撤销栈（默认 `True`）
- `source`: 操作来源标识（用于日志和避免反馈循环）

**说明**:
- 添加前会检查是否可以添加（通过 `can_add_actor`）
- 会触发 `before_actor_added` 和 `on_actor_added` 通知
- 如果添加失败（如远程同步失败），会触发 `on_actor_added_failed` 并自动回滚

**使用示例**:
```python
from orcalab.scene_edit_bus import SceneEditRequestBus
from orcalab.actor import AssetActor, GroupActor
from orcalab.path import Path

# 添加资产 Actor
actor = AssetActor("Box", "box")
parent_path = Path("/Scene")
await SceneEditRequestBus().add_actor(actor, parent_path, undo=True, source="script")

# 添加组 Actor
group = GroupActor("MyGroup", None)
await SceneEditRequestBus().add_actor(group, parent_path, undo=True, source="script")
```

**完整示例**:
```python
import asyncio
from orcalab.scene_edit_bus import SceneEditRequestBus, SceneEditNotificationBus, SceneEditNotification
from orcalab.actor import AssetActor
from orcalab.path import Path

class ActorListener(SceneEditNotification):
    async def on_actor_added(self, actor, parent_actor_path, source):
        print(f"✓ Actor {actor.name} 已添加到 {parent_actor_path}")

listener = ActorListener()
SceneEditNotificationBus().connect(listener)

async def main():
    # 创建并添加 Actor
    actor = AssetActor("MyBox", "box")
    parent = Path("/Scene")
    await SceneEditRequestBus().add_actor(actor, parent, undo=True, source="script")

asyncio.run(main())
```

---

## 读取操作 (Read)

### 获取 Actor

通过 `LocalScene` 获取 Actor：

```python
from orcalab.application_bus import ApplicationRequestBus
from orcalab.path import Path

# 获取本地场景
output = []
ApplicationRequestBus().get_local_scene(output)
if output:
    local_scene = output[0]
    
    # 通过路径获取 Actor
    actor_path = Path("/Scene/MyBox")
    actor = local_scene.find_actor_by_path(actor_path)
    if actor:
        print(f"找到 Actor: {actor.name}")
    
    # 获取所有 Actor
    for path, actor in local_scene._actors.items():
        print(f"{path}: {actor.name}")
```

### 获取选择

```python
from orcalab.application_bus import ApplicationRequestBus

output = []
ApplicationRequestBus().get_local_scene(output)
if output:
    local_scene = output[0]
    selection = local_scene.selection
    print(f"当前选择了 {len(selection)} 个对象")
    for path in selection:
        print(f"  - {path}")
```

---

## 更新操作 (Update)

### rename_actor

重命名 Actor。

**方法签名**:
```python
async def rename_actor(
    self,
    actor: BaseActor,
    new_name: str,
    undo: bool = True,
    source: str = "",
) -> None
```

**参数**:
- `actor`: 要重命名的 Actor 对象
- `new_name`: 新名称
- `undo`: 是否记录到撤销栈（默认 `True`）
- `source`: 操作来源标识

**说明**:
- 重命名前会检查是否可以重命名（通过 `can_rename_actor`）
- 如果名称相同则直接返回
- 如果 Actor 在选中列表中，会更新选择路径
- 会触发 `before_actor_renamed` 和 `on_actor_renamed` 通知

**使用示例**:
```python
from orcalab.scene_edit_bus import SceneEditRequestBus
from orcalab.application_bus import ApplicationRequestBus
from orcalab.path import Path

# 获取 Actor
output = []
ApplicationRequestBus().get_local_scene(output)
if output:
    local_scene = output[0]
    actor = local_scene.find_actor_by_path(Path("/Scene/MyBox"))
    if actor:
        await SceneEditRequestBus().rename_actor(actor, "NewBox", undo=True, source="script")
```

### reparent_actor

改变 Actor 的父对象（移动 Actor 到新的父对象下）。

**方法签名**:
```python
async def reparent_actor(
    self,
    actor: BaseActor | Path,
    new_parent: BaseActor | Path,
    row: int,
    undo: bool = True,
    source: str = "",
) -> None
```

**参数**:
- `actor`: 要移动的 Actor 对象或路径
- `new_parent`: 新的父 Actor 对象或路径
- `row`: 在新父对象中的插入位置（索引）
- `undo`: 是否记录到撤销栈（默认 `True`）
- `source`: 操作来源标识

**说明**:
- 重父化前会检查是否可以重父化（通过 `can_reparent_actor`）
- `row` 参数指定在新父对象中的位置（0 表示第一个位置）
- 会触发 `before_actor_reparented` 和 `on_actor_reparented` 通知

**使用示例**:
```python
from orcalab.scene_edit_bus import SceneEditRequestBus
from orcalab.path import Path

actor_path = Path("/Scene/MyBox")
new_parent_path = Path("/Scene/MyGroup")
await SceneEditRequestBus().reparent_actor(
    actor_path, 
    new_parent_path, 
    row=0,  # 插入到第一个位置
    undo=True, 
    source="script"
)
```

### set_transform

设置 Actor 的变换（位置、旋转、缩放）。

**方法签名**:
```python
async def set_transform(
    self,
    actor: BaseActor | Path,
    transform: Transform,
    local: bool,
    undo: bool = True,
    source: str = "",
) -> None
```

**参数**:
- `actor`: Actor 对象或路径
- `transform`: 变换对象（`Transform`）
- `local`: 是否使用本地坐标系（`True` 为本地，`False` 为世界）
- `undo`: 是否记录到撤销栈（默认 `True`）
- `source`: 操作来源标识

**Transform 结构**:
```python
from orcalab.math import Transform

transform = Transform(
    pos=[x, y, z],           # 位置 (3个元素)
    quat=[w, x, y, z],       # 旋转四元数 (4个元素)
    scale=1.0                # 缩放
)
```

**使用示例**:
```python
from orcalab.scene_edit_bus import SceneEditRequestBus
from orcalab.math import Transform
from orcalab.path import Path

# 设置世界坐标变换
transform = Transform(
    pos=[1.0, 2.0, 3.0],
    quat=[1.0, 0.0, 0.0, 0.0],  # 无旋转
    scale=1.0
)
actor_path = Path("/Scene/MyBox")
await SceneEditRequestBus().set_transform(
    actor_path, 
    transform, 
    local=False,  # 世界坐标
    undo=True, 
    source="script"
)

# 设置本地坐标变换
local_transform = Transform(
    pos=[0.5, 0.0, 0.0],  # 相对于父对象
    quat=[1.0, 0.0, 0.0, 0.0],
    scale=1.0
)
await SceneEditRequestBus().set_transform(
    actor_path, 
    local_transform, 
    local=True,  # 本地坐标
    undo=True
)
```

### set_property

设置 Actor 的属性值。

**方法签名**:
```python
async def set_property(
    self,
    property_key: ActorPropertyKey,
    value: Any,
    undo: bool,
    source: str = "",
) -> None
```

**参数**:
- `property_key`: 属性键（`ActorPropertyKey`）
- `value`: 属性值（类型取决于属性类型）
- `undo`: 是否记录到撤销栈
- `source`: 操作来源标识

**属性编辑模式**:

**非拖拽模式**（直接设置）:
```python
await SceneEditRequestBus().set_property(property_key, value, undo=True)
```

**拖拽模式**（连续修改）:
```python
# 开始编辑
SceneEditRequestBus().start_change_property(property_key)

# 多次修改（不记录撤销）
await SceneEditRequestBus().set_property(property_key, value1, undo=False)
await SceneEditRequestBus().set_property(property_key, value2, undo=False)

# 最后一次修改（记录撤销）
await SceneEditRequestBus().set_property(property_key, value3, undo=True)

# 结束编辑
SceneEditRequestBus().end_change_property(property_key)
```

**使用示例**:
```python
from orcalab.scene_edit_bus import SceneEditRequestBus
from orcalab.actor_property import ActorPropertyKey
from orcalab.path import Path

property_key = ActorPropertyKey(
    actor_path=Path("/Scene/MyBox"),
    group_prefix="Transform",
    property_name="Position",
    property_type=PropertyType.Float
)

# 设置属性值
new_value = [1.0, 2.0, 3.0]
await SceneEditRequestBus().set_property(property_key, new_value, undo=True, source="script")
```

---

## 删除操作 (Delete)

### delete_actor

删除场景中的 Actor。

**方法签名**:
```python
async def delete_actor(
    self,
    actor: BaseActor | Path,
    undo: bool = True,
    source: str = "",
) -> None
```

**参数**:
- `actor`: 要删除的 Actor 对象或路径
- `undo`: 是否记录到撤销栈（默认 `True`）
- `source`: 操作来源标识

**说明**:
- 删除前会检查是否可以删除（通过 `can_delete_actor`）
- 不能删除正在编辑的 Actor（正在编辑变换或属性）
- 如果 Actor 在选中列表中，会先取消选择
- 会触发 `before_actor_deleted` 和 `on_actor_deleted` 通知

**使用示例**:
```python
from orcalab.scene_edit_bus import SceneEditRequestBus
from orcalab.path import Path

# 通过路径删除
actor_path = Path("/Scene/MyBox")
await SceneEditRequestBus().delete_actor(actor_path, undo=True, source="script")

# 通过对象删除
from orcalab.application_bus import ApplicationRequestBus

output = []
ApplicationRequestBus().get_local_scene(output)
if output:
    local_scene = output[0]
    actor = local_scene.find_actor_by_path(Path("/Scene/MyBox"))
    if actor:
        await SceneEditRequestBus().delete_actor(actor, undo=True, source="script")
```

---

## 选择操作

### set_selection

设置场景中的选中对象。

**方法签名**:
```python
async def set_selection(
    self,
    selection: List[Path],
    undo: bool = True,
    source: str = "",
) -> None
```

**参数**:
- `selection`: Actor 路径列表（空列表表示清除选择）
- `undo`: 是否记录到撤销栈（默认 `True`）
- `source`: 操作来源标识

**说明**:
- 如果选择列表与当前相同则直接返回
- 会触发 `on_selection_changed` 通知
- `source` 参数用于避免反馈循环（如果通知来源是自己，可以忽略）

**使用示例**:
```python
from orcalab.scene_edit_bus import SceneEditRequestBus
from orcalab.path import Path

# 选择单个对象
selection = [Path("/Scene/MyBox")]
await SceneEditRequestBus().set_selection(selection, undo=True, source="script")

# 选择多个对象
selection = [
    Path("/Scene/Box1"),
    Path("/Scene/Box2"),
    Path("/Scene/Box3")
]
await SceneEditRequestBus().set_selection(selection, undo=True, source="script")

# 清除选择
await SceneEditRequestBus().set_selection([], undo=True, source="script")
```

---

## 完整 CRUD 示例

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

class CRUDListener(SceneEditNotification):
    async def on_actor_added(self, actor, parent_actor_path, source):
        print(f"✓ 创建: {actor.name} 在 {parent_actor_path}")
    
    async def on_actor_renamed(self, actor_path, new_name, source):
        print(f"✓ 重命名: {actor_path} -> {new_name}")
    
    async def on_actor_deleted(self, actor_path, source):
        print(f"✓ 删除: {actor_path}")
    
    async def on_selection_changed(self, old_selection, new_selection, source):
        print(f"✓ 选择: {len(new_selection)} 个对象")

listener = CRUDListener()
SceneEditNotificationBus().connect(listener)

async def main():
    parent_path = Path("/Scene")
    
    # Create: 创建 Actor
    actor = AssetActor("MyBox", "box")
    await SceneEditRequestBus().add_actor(actor, parent_path, undo=True, source="script")
    actor_path = Path("/Scene/MyBox")
    
    # Read: 读取 Actor（通过 LocalScene）
    from orcalab.application_bus import ApplicationRequestBus
    output = []
    ApplicationRequestBus().get_local_scene(output)
    if output:
        local_scene = output[0]
        actor = local_scene.find_actor_by_path(actor_path)
        print(f"读取: {actor.name if actor else 'Not found'}")
    
    # Update: 更新变换
    transform = Transform(
        pos=[1.0, 2.0, 3.0],
        quat=[1.0, 0.0, 0.0, 0.0],
        scale=1.0
    )
    await SceneEditRequestBus().set_transform(actor_path, transform, local=False, undo=True)
    
    # Update: 重命名
    await SceneEditRequestBus().rename_actor(actor, "NewBox", undo=True, source="script")
    new_path = Path("/Scene/NewBox")
    
    # Update: 选择
    await SceneEditRequestBus().set_selection([new_path], undo=True, source="script")
    
    # Delete: 删除
    await SceneEditRequestBus().delete_actor(new_path, undo=True, source="script")

asyncio.run(main())
```

---

## 撤销/重做

所有支持 `undo=True` 的操作都会自动记录到撤销栈：

```python
from orcalab.undo_service.undo_service_bus import UndoRequestBus

# 撤销
UndoRequestBus().undo()

# 重做
UndoRequestBus().redo()
```

---

## 注意事项

1. **异步操作**: 所有 CRUD 操作都是异步的，需要使用 `await`
2. **路径格式**: 路径使用 `Path` 对象，格式为 `/Scene/ActorName`
3. **撤销支持**: 默认所有操作都支持撤销，设置 `undo=False` 可以禁用
4. **来源标识**: 使用 `source` 参数标识操作来源，避免反馈循环
5. **错误处理**: 操作可能失败，建议使用 try-except 处理异常

