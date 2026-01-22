---
layout: default
title: API Detailed Reference - Actor Design
---

# API Detailed Reference: Actor Design

> **📖 这是什么文档？**  
> 这是 OrcaLab Actor 体系的详细设计文档，包含 Actor 的层次结构、变换系统、路径系统等核心概念。

> **💡 使用提示**  
> Actor 是 OrcaLab 场景编辑的核心，理解 Actor 的设计有助于更好地使用 CRUD API。

---

## 概述

OrcaLab 的场景由 **Actor 树**组成，每个 Actor 代表场景中的一个对象。Actor 体系设计遵循以下原则：

- **层次结构**：Actor 通过父子关系组织成树形结构
- **路径系统**：每个 Actor 都有唯一路径，类似文件系统路径
- **变换系统**：支持本地坐标和世界坐标的自动转换
- **类型系统**：通过继承实现不同类型的 Actor（Group、Asset）

---

## Actor 类型体系

### BaseActor（基类）

文件：`orcalab/actor.py`

所有 Actor 的基类，提供基础功能：

**核心属性**：

- `name`：Actor 名称（字符串，在同一父对象下唯一）
- `parent`：父 Actor（`GroupActor` 或 `None`）
- `transform`：本地变换（相对于父对象）
- `world_transform`：世界变换（缓存，自动计算）

**设计要点**：

- 名称验证：使用 `Path.is_valid_name()` 验证名称格式
- 父对象管理：设置父对象时自动更新父子关系
- 变换缓存：`world_transform` 使用缓存机制，父对象或本地变换改变时自动失效

**使用示例**：

```python
from orcalab.actor import BaseActor
from orcalab.math import Transform

# BaseActor 是抽象基类，不能直接实例化
# 应该使用 GroupActor 或 AssetActor
```

### GroupActor（组 Actor）

文件：`orcalab/actor.py`

组 Actor，用于组织其他 Actor 的容器。

**核心属性**：

- `children`：子 Actor 列表（只读副本）

**核心方法**：

- `add_child(child: BaseActor)`：添加子 Actor（追加到末尾）
- `insert_child(index: int, child: BaseActor)`：在指定位置插入子 Actor
- `remove_child(child: BaseActor)`：移除子 Actor

**设计要点**：

- 子对象管理：自动维护父子关系的双向引用
- 插入位置：支持在指定索引位置插入，`-1` 表示追加到末尾
- 唯一性检查：同一子对象不能重复添加

**使用示例**：

```python
from orcalab.actor import GroupActor, AssetActor

# 创建组
group = GroupActor("MyGroup", parent=None)

# 添加子 Actor
box = AssetActor("Box", "box")
group.add_child(box)

# 插入到指定位置
sphere = AssetActor("Sphere", "sphere")
group.insert_child(0, sphere)  # 插入到第一个位置

# 获取子对象列表
children = group.children  # 返回只读副本
print(f"组有 {len(children)} 个子对象")
```

### AssetActor（资产 Actor）

文件：`orcalab/actor.py`

资产 Actor，从资产库加载的具体对象。

**核心属性**：

- `asset_path`：资产路径（小写，无 `.spawnable` 后缀）
- `property_groups`：属性组列表

**设计要点**：

- 资产路径：使用小写、无后缀的格式（如 "box" 对应 "Box.spawnable"）
- 属性系统：支持动态属性组，用于存储 Actor 的自定义属性

**使用示例**：

```python
from orcalab.actor import AssetActor, GroupActor

# 创建资产 Actor
actor = AssetActor(
    name="MyBox",
    asset_path="box",  # 对应 "Box.spawnable"
    parent=None
)

# 设置父对象
group = GroupActor("MyGroup")
actor.parent = group  # 自动更新父子关系

# 访问属性组
property_groups = actor.property_groups
```

---

## 路径系统（Path）

文件：`orcalab/path.py`

Path 用于标识 Actor 在场景树中的位置，类似文件系统路径。

### 路径格式

- **根路径**：`/`（场景根）
- **完整路径**：`/Scene/MyBox`（从根到 Actor）
- **命名规则**：
  - 只能包含字母、数字、下划线
  - 不能以数字开头（会自动添加 `_` 前缀）
  - 路径必须从 `/` 开始

### 核心方法

- `Path(path: str = "/")`：创建路径对象
- `append(name: str) -> Path`：追加名称到路径
- `parent() -> Path | None`：获取父路径
- `name() -> str`：获取路径的最后一部分（名称）
- `is_descendant_of(parent_path: Path) -> bool`：判断是否为子路径
- `string() -> str`：获取路径字符串

### 使用示例

```python
from orcalab.path import Path

# 创建路径
root = Path("/")
scene_path = root.append("Scene")
box_path = scene_path.append("MyBox")

# 或使用除法运算符
box_path = Path("/") / "Scene" / "MyBox"

# 获取父路径
parent = box_path.parent()  # Path("/Scene")

# 获取名称
name = box_path.name()  # "MyBox"

# 判断是否为子路径
is_child = box_path.is_descendant_of(scene_path)  # True

# 转换为字符串
path_str = box_path.string()  # "/Scene/MyBox"
```

---

## 变换系统（Transform）

文件：`orcalab/math.py`

Transform 表示 Actor 的变换信息（位置、旋转、缩放）。

### Transform 结构

```python
class Transform:
    position: np.ndarray  # 位置 [x, y, z] (3个元素)
    rotation: np.ndarray  # 旋转四元数 [w, x, y, z] (4个元素，单位四元数)
    scale: float          # 缩放（标量）
```

### 核心操作

- `transform1 * transform2`：组合变换（先 transform2 后 transform1）
- `transform.inverse()`：逆变换
- `transform.transform_point(point)`：变换点（缩放→旋转→平移）
- `transform.transform_vector(vector)`：变换向量（缩放→旋转，忽略平移）
- `transform.transform_direction(direction)`：变换方向（仅旋转，忽略平移和缩放）

### 使用示例

```python
from orcalab.math import Transform
import numpy as np

# 创建变换
transform = Transform(
    position=np.array([1.0, 2.0, 3.0]),
    rotation=np.array([1.0, 0.0, 0.0, 0.0]),  # 无旋转
    scale=1.0
)

# 组合变换
transform1 = Transform(position=np.array([1, 0, 0]), ...)
transform2 = Transform(position=np.array([0, 1, 0]), ...)
combined = transform1 * transform2  # 先 transform2 后 transform1

# 逆变换
inverse = transform.inverse()

# 变换点
point = np.array([0.0, 0.0, 0.0])
transformed_point = transform.transform_point(point)
```

---

## Actor 的变换系统

### 本地坐标 vs 世界坐标

Actor 支持两种坐标系统：

- **本地坐标（Local）**：相对于父对象的坐标
- **世界坐标（World）**：世界坐标系中的坐标

### 自动转换

Actor 的 `world_transform` 会自动计算：

```python
if parent is None:
    world_transform = transform
else:
    world_transform = parent.world_transform * transform
```

设置 `world_transform` 时，会自动计算本地变换：

```python
if parent is None:
    transform = world_transform
else:
    transform = parent.world_transform.inverse() * world_transform
```

### 缓存机制

`world_transform` 使用缓存机制：

- 当 `transform` 改变时，`world_transform` 缓存失效
- 当 `parent` 改变时，`world_transform` 缓存失效
- 首次访问时自动计算并缓存

### 使用示例

```python
from orcalab.actor import AssetActor, GroupActor
from orcalab.math import Transform
import numpy as np

# 创建父子关系
parent = GroupActor("Parent")
child = AssetActor("Child", "box", parent=parent)

# 设置父对象的变换
parent.transform = Transform(
    position=np.array([1.0, 0.0, 0.0]),
    rotation=np.array([1.0, 0.0, 0.0, 0.0]),
    scale=1.0
)

# 设置子对象的本地变换
child.transform = Transform(
    position=np.array([0.0, 1.0, 0.0]),  # 相对于父对象
    rotation=np.array([1.0, 0.0, 0.0, 0.0]),
    scale=1.0
)

# 获取子对象的世界变换（自动计算）
world = child.world_transform
print(f"世界位置: {world.position}")  # [1.0, 1.0, 0.0]

# 设置子对象的世界变换（自动计算本地变换）
child.world_transform = Transform(
    position=np.array([2.0, 2.0, 0.0]),  # 世界坐标
    rotation=np.array([1.0, 0.0, 0.0, 0.0]),
    scale=1.0
)
print(f"本地位置: {child.transform.position}")  # 自动计算
```

---

## Actor 的父子关系

### 双向引用

Actor 的父子关系是双向的：

- 设置 `child.parent = parent` 时：
  - 自动从旧父对象移除子对象
  - 自动添加到新父对象的子列表
  - 自动更新子对象的 `_parent` 引用

### 路径更新

当 Actor 的父对象改变时，路径会自动更新：

```python
# Actor 在 /Scene/Box
actor_path = Path("/Scene/Box")

# 移动到新父对象 /Scene/Group
new_parent_path = Path("/Scene/Group")
await SceneEditRequestBus().reparent_actor(actor_path, new_parent_path, row=0)

# 新路径变为 /Scene/Group/Box
new_path = Path("/Scene/Group/Box")
```

### 使用示例

```python
from orcalab.actor import GroupActor, AssetActor

# 创建父子关系
parent = GroupActor("Parent")
child = AssetActor("Child", "box")

# 方法1：通过 parent 属性设置
child.parent = parent

# 方法2：通过 GroupActor 的方法添加
parent.add_child(child)

# 移除子对象
parent.remove_child(child)
# 或
child.parent = None
```

---

## Actor 的属性系统

### ActorProperty

Actor 的属性通过 `ActorProperty` 表示：

```python
class ActorProperty:
    name: str                    # 属性名称
    display_name: str           # 显示名称
    value_type: ActorPropertyType  # 属性类型（BOOL/INTEGER/FLOAT/STRING）
    value: Any                  # 属性值
    original_value: Any         # 原始值（用于检测修改）
    read_only: bool             # 是否只读
    editor_hint: str            # 编辑器提示
```

### ActorPropertyGroup

属性按组组织：

```python
class ActorPropertyGroup:
    prefix: str                 # 组前缀
    name: str                   # 组名称
    display_name: str           # 显示名称
    hint: str                   # 提示信息
    properties: List[ActorProperty]  # 属性列表
```

### ActorPropertyKey

属性通过 `ActorPropertyKey` 唯一标识：

```python
class ActorPropertyKey:
    actor_path: Path            # Actor 路径
    group_prefix: str           # 组前缀
    property_name: str          # 属性名称
    property_type: ActorPropertyType  # 属性类型
```

### 使用示例

```python
from orcalab.actor_property import ActorPropertyKey, ActorPropertyType
from orcalab.path import Path

# 创建属性键
property_key = ActorPropertyKey(
    actor_path=Path("/Scene/MyBox"),
    group_prefix="Transform",
    property_name="Position",
    property_type=ActorPropertyType.FLOAT
)

# 设置属性值
await SceneEditRequestBus().set_property(
    property_key,
    [1.0, 2.0, 3.0],
    undo=True,
    source="script"
)
```

---

## LocalScene 中的 Actor 管理

### 路径映射

`LocalScene` 维护路径到 Actor 的映射：

```python
class LocalScene:
    root_actor: GroupActor           # 根 Actor
    _actors: Dict[Path, BaseActor]   # 路径到 Actor 的映射
    selection: List[Path]            # 选中的 Actor 路径列表
```

### 核心操作

- `find_actor_by_path(path: Path) -> BaseActor | None`：通过路径查找 Actor
- `get_actor_path(actor: BaseActor) -> Path | None`：获取 Actor 的路径
- `get_actor_and_path(actor: BaseActor | Path) -> Tuple[BaseActor, Path]`：获取 Actor 和路径
- `add_actor(actor: BaseActor, parent_path: Path)`：添加 Actor
- `delete_actor(actor: BaseActor | Path)`：删除 Actor

### 使用示例

```python
from orcalab.application_bus import ApplicationRequestBus
from orcalab.path import Path

# 获取本地场景
output = []
ApplicationRequestBus().get_local_scene(output)
if output:
    local_scene = output[0]
    
    # 通过路径查找 Actor
    actor_path = Path("/Scene/MyBox")
    actor = local_scene.find_actor_by_path(actor_path)
    
    # 获取 Actor 的路径
    path = local_scene.get_actor_path(actor)
    
    # 获取选中的 Actor
    selection = local_scene.selection
    for path in selection:
        actor = local_scene.find_actor_by_path(path)
```

---

## 设计模式与最佳实践

### 1. Actor 创建模式

```python
# ✅ 推荐：先创建 Actor，再添加到场景
actor = AssetActor("MyBox", "box")
await SceneEditRequestBus().add_actor(actor, parent_path)

# ❌ 不推荐：直接操作 LocalScene（绕过 Event Bus）
local_scene.add_actor(actor, parent_path)  # 不会触发通知
```

### 2. 变换设置模式

```python
# ✅ 推荐：通过 Event Bus 设置变换（支持撤销）
await SceneEditRequestBus().set_transform(
    actor_path,
    transform,
    local=False,
    undo=True
)

# ❌ 不推荐：直接修改 Actor.transform（不会触发通知）
actor.transform = transform  # 不会触发 on_transform_changed
```

### 3. 路径使用模式

```python
# ✅ 推荐：使用 Path 对象
actor_path = Path("/Scene/MyBox")

# ❌ 不推荐：使用字符串路径
actor_path = "/Scene/MyBox"  # 类型错误
```

### 4. 父子关系管理

```python
# ✅ 推荐：通过 Event Bus 改变父对象（支持撤销）
await SceneEditRequestBus().reparent_actor(
    actor_path,
    new_parent_path,
    row=0,
    undo=True
)

# ❌ 不推荐：直接修改 parent 属性（不会触发通知）
actor.parent = new_parent  # 不会触发 on_actor_reparented
```

---

## 注意事项

1. **路径唯一性**：同一父对象下不能有同名 Actor
2. **变换缓存**：`world_transform` 使用缓存，修改 `transform` 或 `parent` 时自动失效
3. **深拷贝**：`transform` 属性返回深拷贝，修改不会影响原始值
4. **异步操作**：所有通过 Event Bus 的操作都是异步的，需要使用 `await`
5. **撤销支持**：通过 Event Bus 的操作默认支持撤销，设置 `undo=False` 可以禁用

---

## 相关接口

- `BaseActor` / `GroupActor` / `AssetActor`：Actor 类型
- `Path`：路径系统
- `Transform`：变换系统
- `LocalScene`：场景管理
- `SceneEditRequestBus`：场景编辑请求
- `SceneEditNotificationBus`：场景编辑通知

