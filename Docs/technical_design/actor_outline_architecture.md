# 大纲视图（Actor Outline）架构设计文档

> 本文档用于指导大纲视图支持更复杂层级结构的架构调整。

---

## 第一部分：现状分析

### 1. 架构与设计哲学

#### 1.1 整体架构

大纲视图采用经典的 **MVC（Model-View-Controller）分层架构**，并通过 **事件总线（Event Bus）** 实现模块间解耦：

```
┌─────────────────────────────────────────────────────────────┐
│                        UI Layer                              │
│  ┌─────────────────┐        ┌───────────────────────────┐   │
│  │  ActorOutline   │◄──────►│   ActorOutlineDelegate    │   │
│  │   (QTreeView)   │        │   (Custom Item Delegate)  │   │
│  └────────┬────────┘        └───────────────────────────┘   │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────┐                                        │
│  │ ActorOutlineModel│                                       │
│  │(QAbstractItemModel)                                      │
│  └────────┬────────┘                                        │
└───────────┼──────────────────────────────────────────────────┘
            │
            ▼ Event Bus (SceneEditNotificationBus)
┌─────────────────────────────────────────────────────────────┐
│                    Service Layer                             │
│  ┌─────────────────┐        ┌───────────────────────────┐   │
│  │ SceneEditService │◄──────►│      LocalScene           │   │
│  │  (Command Bus)   │        │   (In-Memory Scene Graph) │   │
│  └────────┬────────┘        └───────────────────────────┘   │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────┐        ┌───────────────────────────┐   │
│  │   RemoteScene    │        │    UndoService            │   │
│  │  (gRPC Sync)     │        │   (Command Pattern)       │   │
│  └─────────────────┘        └───────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

#### 1.2 设计哲学

| 设计原则 | 具体体现 |
|---------|---------|
| **单一职责** | `ActorOutline` 只负责渲染和交互；`ActorOutlineModel` 只负责数据模型；`SceneEditService` 只负责业务逻辑 |
| **命令模式** | 所有场景修改都封装为 `Command` 对象，支持撤销/重做 |
| **异步安全** | `SceneEditService` 使用 `_edit_lock`（`asyncio.Lock`）防止并发编辑导致状态混乱 |
| **本地优先** | 先在 `LocalScene` 修改，再同步到 `RemoteScene`，确保 UI 响应即时性 |
| **路径寻址** | 所有 Actor 通过 `Path` 对象唯一标识，支持重命名和重排后路径变更 |
| **来源追踪** | 每个操作携带 `source` 参数（如 `"actor_outline"`），避免循环通知 |

#### 1.3 核心类职责

| 类 | 职责 | 关键文件 |
|---|------|---------|
| `ActorOutline` | 树形视图渲染、鼠标/键盘交互、上下文菜单、拖拽发起 | `ui/actor_outline.py` |
| `ActorOutlineDelegate` | 自定义绘制：Actor 名称 + 显隐按钮 + 锁定按钮 | `ui/actor_outline.py` |
| `ActorOutlineModel` | `QAbstractItemModel` 实现，管理树形数据结构，处理拖放接收 | `ui/actor_outline_model.py` |
| `SceneEditService` | 场景编辑的核心服务，封装所有修改操作并协调本地/远程同步 | `scene_edit_service.py` |
| `LocalScene` | 内存中的场景图，维护 Actor 层级结构和路径索引 | `local_scene.py` |
| `RemoteScene` | 通过 gRPC 与后端引擎通信，同步场景变更 | `remote_scene.py` |
| `SceneEditRequestBus` / `SceneEditNotificationBus` | 事件总线，解耦 UI 与 Service | `scene_edit_bus.py` |

---

### 2. 主业务流程

#### 2.1 Actor 创建流程

```
用户操作（右键菜单 Add Group / 拖拽 Asset）
        │
        ▼
┌───────────────┐
│ ActorOutline  │  ──► 构造 Actor 对象（GroupActor / AssetActor）
└───────┬───────┘
        │
        ▼
┌───────────────────────┐
│ SceneEditRequestBus   │  ──► add_actor(actor, parent, undo=True, source="actor_outline")
└───────┬───────────────┘
        │
        ▼
┌───────────────────────┐
│   SceneEditService    │  ──► 获取 _edit_lock
│                       │  ──► 调用 local_scene.can_add_actor() 预检
│                       │  ──► 调用 local_scene.add_actor() 本地修改
│                       │  ──► 调用 remote_scene.add_actor_batch() 远程同步
└───────┬───────────────┘
        │
        ▼
┌───────────────────────┐
│ SceneEditNotificationBus │  ──► before_actor_added → on_actor_added
└───────┬───────────────┘
        │
        ▼
┌───────────────────────┐
│   ActorOutlineModel   │  ──► beginInsertRows / endInsertRows 通知视图更新
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│     UndoService       │  ──► 创建 AddActorCommand 加入撤销栈
└───────────────────────┘
```

#### 2.2 Actor 删除流程

```
用户操作（右键菜单 Delete）
        │
        ▼
┌───────────────┐
│ ActorOutline  │  ──► 获取选中 Actor 路径列表
└───────┬───────┘
        │
        ▼
┌───────────────────────┐
│ SceneEditRequestBus   │  ──► delete_actors(actor_paths)
└───────┬───────────────┘
        │
        ▼
┌───────────────────────┐
│   SceneEditService    │  ──► 预检（不能删除 root、不能删除编辑中 Actor）
│                       │  ──► 从 selection / active_actor 中移除被删 Actor
│                       │  ──► local_scene.delete_actors() 本地删除
│                       │  ──► remote_scene.delete_actor_batch() 远程同步
└───────┬───────────────┘
        │
        ▼
┌───────────────────────┐
│ SceneEditNotificationBus │  ──► before_actors_deleted → on_actors_deleted
└───────┬───────────────┘
        │
        ▼
┌───────────────────────┐
│   ActorOutlineModel   │  ──► beginResetModel / endResetModel（批量删除）
└───────────────────────┘
```

#### 2.3 Actor 重排（Reparent / Move）流程

```
用户操作（拖拽 Actor 到目标 Group）
        │
        ▼
┌───────────────┐
│ ActorOutline  │  ──► 鼠标按下记录当前 Actor
│               │  ──► 鼠标移动超过阈值时启动拖拽
│               │  ──► 构造 MIME 数据：application/x-orca-actor-reparent
└───────┬───────┘
        │
        ▼
┌───────────────────────┐
│ ActorOutlineModel     │  ──► dropMimeData() 接收拖放
│                       │  ──► prepare_reparent_data() 解析目标位置和父级
│                       │  ──► local_scene.can_move_actors() 预检
└───────┬───────────────┘
        │
        ▼
┌───────────────────────┐
│ SceneEditRequestBus   │  ──► move_actors(actor_paths, new_parent_paths, insert_positions)
└───────┬───────────────┘
        │
        ▼
┌───────────────────────┐
│   SceneEditService    │  ──► 更新 selection / active_actor 路径
│                       │  ──► local_scene.move_actors() 本地重排
│                       │  ──► remote_scene.move_actor_batch() 远程同步
│                       │  ──► refresh_subtree_parent_visibility_lock() 刷新显隐/锁定状态
└───────┬───────────────┘
        │
        ▼
┌───────────────────────┐
│ SceneEditNotificationBus │  ──► before_actor_reparented → on_actor_reparented
└───────┬───────────────┘
        │
        ▼
┌───────────────────────┐
│   ActorOutlineModel   │  ──► beginResetModel / endResetModel（树形结构变更）
└───────────────────────┘
```

#### 2.4 显隐 / 锁定切换流程

```
用户操作（点击行右侧 eye / lock 图标）
        │
        ▼
┌───────────────┐
│ ActorOutline  │  ──► mouseReleaseEvent 检测点击区域
│               │  ──► _toggle_actor_visibile() / _toggle_actor_locked()
└───────┬───────┘
        │
        ▼
┌───────────────────────┐
│ SceneEditRequestBus   │  ──► set_actor_visible() / set_actor_locked()
└───────┬───────────────┘
        │
        ▼
┌───────────────────────┐
│   SceneEditService    │  ──► 修改 actor.is_visible / is_locked
│                       │  ──► 远程同步 actor_visible_change / actor_locked_change
└───────┬───────────────┘
        │
        ▼
┌───────────────────────┐
│ SceneEditNotificationBus │  ──► on_actor_visible_changed / on_actor_locked_changed
└───────┬───────────────┘
        │
        ▼
┌───────────────────────┐
│   ActorOutlineModel   │  ──► dataChanged.emit(index, index) 局部刷新
└───────────────────────┘
```

---

### 3. 主要数据结构

#### 3.1 Actor 类层次

```python
# orcalab/actor.py

class BaseActor:
    def __init__(self, name: str, parent: ParentActor):
        self._name = ""
        self._parent = None
        self._transform = Transform()          # 局部变换
        self._world_transform = None           # 世界变换（缓存）
        self.name = name
        self.parent = parent
        self._is_visible = True                # 自身显隐
        self._is_locked = False                # 自身锁定
        self._is_parent_visible = True         # 父级显隐影响
        self._is_parent_locked = False         # 父级锁定影响

class GroupActor(BaseActor):
    def __init__(self, name: str, parent: ParentActor = None):
        self._children: List[BaseActor] = []   # 子 Actor 列表
        super().__init__(name, parent)

class AssetActor(BaseActor):
    def __init__(self, name: str, asset_path: str, parent: GroupActor | None = None):
        super().__init__(name, parent)
        self._asset_path = asset_path          # 资产路径
        self.property_groups: List[ActorPropertyGroup] = []  # 属性组
```

#### 3.2 LocalScene 场景图

```python
# orcalab/local_scene.py

class LocalScene:
    def __init__(self):
        self.root_actor = GroupActor(name="root", parent=None)  # 伪根节点
        self._actors: Dict[Path, BaseActor] = {}                # Path → Actor 索引
        self._actors[Path.root_path()] = self.root_actor
        self._selection: List[Path] = []                        # 当前选中路径（有序）
        self._active_actor: Path | None = None                  # 当前激活 Actor
```

**关键设计**：
- `root_actor` 是伪根节点，路径为 `"/"`，不可见、不可删除、不可重命名
- `_actors` 字典提供 O(1) 的路径到 Actor 查找
- `Path` 类封装层级路径（如 `/group1/group2/actor`），支持 `parent()`、`is_descendant_of()` 等操作

#### 3.3 ActorOutlineModel 树模型

```python
# orcalab/ui/actor_outline_model.py

class ActorOutlineModel(QAbstractItemModel, SceneEditNotification):
    def __init__(self, local_scene: LocalScene, parent=None):
        self.column_count = 1
        self.m_root_group: GroupActor | None = None   # 模型根节点
        self.reparent_mime = "application/x-orca-actor-reparent"
        self.local_scene = local_scene
```

**模型索引映射**：
- `QModelIndex()`（无效索引）→ `m_root_group`
- `createIndex(row, col, actor)` → 对应 Actor 节点
- `parent()` 通过 `actor.parent` 回溯父级
- `rowCount()` 通过 `group.children` 获取子级数量

#### 3.4 撤销/重做命令

```python
# orcalab/undo_service/command.py

class AddActorCommand(BaseCommand):
    def __init__(self, requests: List[AddActorRequest]):
        self.requests = requests                # 保存创建请求，用于撤销时删除

class DeleteActorCommand(BaseCommand):
    def __init__(self, actors: List[BaseActor], paths: List[Path], rows: List[int]):
        self.actors = actors                    # 保存被删 Actor 作为模板，用于撤销时恢复
        self.parent_paths = paths
        self.rows = rows

class MoveActorCommand(BaseCommand):
    def __init__(self, actor_paths, old_rows, new_parent_paths, new_rows):
        self.actor_paths = actor_paths
        self.old_rows = old_rows
        self.new_parent_paths = new_parent_paths
        self.new_rows = new_rows

class RenameActorCommand(BaseCommand):
    def __init__(self):
        self.old_path: Path = Path()
        self.new_path: Path = Path()
```

**关键设计**：命令中不保存 Actor 对象引用，而是保存 `Path`，因为 Actor 可能被删除和重建。

---

### 4. 典型用户操作的代码实现流程

#### 4.1 创建 Group

**触发**：右键点击 Actor → 选择 "Add Group"

```python
# orcalab/ui/actor_outline.py

@QtCore.Slot()
def show_context_menu(self, position):
    # ... 构造菜单 ...
    action_add_group = QtGui.QAction("Add Group")
    connect(action_add_group.triggered, self._add_group)
    menu.addAction(action_add_group)

async def _add_group(self):
    parent_actor = self._current_actor
    parent_actor_path = self._current_actor_path

    # 如果当前 Actor 不是 Group，则在其父级 Group 下创建
    if not isinstance(parent_actor, GroupActor):
        parent_actor = parent_actor.parent
        parent_actor_path = parent_actor_path.parent()

    # 自动生成唯一名称
    new_group_name = make_unique_name("group", parent_actor)
    actor = GroupActor(name=new_group_name)

    # 通过总线发送创建请求
    await SceneEditRequestBus().add_actor(
        actor, parent_actor, undo=True, source="actor_outline"
    )
```

**Service 端处理**：

```python
# orcalab/scene_edit_service.py

async def add_actor(self, actor, parent_actor, undo=True, source=""):
    _, parent_actor_path = self.local_scene.normalize_actor(parent_actor)
    request = AddActorRequest(actor, parent_actor_path, -1)
    await self.add_actors([request], undo, source)

async def _add_actors(self, requests, undo=True, source=""):
    ok, err = self.local_scene.can_add_actors(requests)
    if not ok:
        raise Exception(err)

    bus = SceneEditNotificationBus()
    await bus.before_actor_added_batch()

    err = self.local_scene.add_actor_batch(requests)
    if err == "":
        suceess, errors = await self.remote_scene.add_actor_batch(requests, True)
        if suceess:
            await bus.on_actor_added_batch("")
        else:
            # 回滚本地修改
            self.local_scene.delete_actors([r.actor for r in requests])
            await bus.on_actor_added_failed("")

    if undo:
        command = AddActorCommand(requests)
        UndoRequestBus().add_command(command)
```

#### 4.2 删除 Actor

**触发**：右键点击 Actor → 选择 "Delete"

```python
# orcalab/ui/actor_outline.py

async def _delete_actor(self):
    selection = self._selected_actor_paths()
    if self._current_actor_path in selection:
        # 批量删除选中的 Actor
        await SceneEditRequestBus().delete_actors(selection)
    else:
        # 删除当前右键点击的 Actor
        await SceneEditRequestBus().delete_actor(
            self._current_actor, undo=True, source="actor_outline"
        )
```

**Service 端处理**：

```python
# orcalab/scene_edit_service.py

async def _delete_actors(self, actors, undo=True, source=""):
    _actors, _actor_paths = self.normalize_and_clean_actors(actors)

    # 预检
    ok, err = self.local_scene.can_delete_actors(_actor_paths)
    if not ok:
        logger.error("Cannot delete actor: %s", err)
        return

    # 保存父级路径和索引，用于撤销时恢复位置
    parent_paths = []
    indexes = []
    for _actor in _actors:
        parent_actor = _actor.parent
        index = parent_actor.children.index(_actor)
        parent_paths.append(self.local_scene.get_actor_path(parent_actor))
        indexes.append(index)

    # 从 selection / active_actor 中移除
    if in_selection:
        await self._set_selection(new_selection, undo=False, source=source)
    if active_actor in _actor_paths:
        await self._set_active_actor(None, undo=False, source=source)

    # 本地删除 + 远程同步
    await bus.before_actors_deleted(_actor_paths, source)
    self.local_scene.delete_actors(_actors)
    await self.remote_scene.delete_actor_batch(_actor_paths)
    await bus.on_actors_deleted(_actor_paths, source)

    # 加入撤销栈
    delete_command = DeleteActorCommand(_actors, parent_paths, indexes)
    UndoRequestBus().add_command(command_group)
```

#### 4.3 拖拽重排（Reparent）

**触发**：鼠标拖拽 Actor 到另一个 Group

```python
# orcalab/ui/actor_outline.py

def mouseMoveEvent(self, event):
    # ... 检测拖拽距离 ...

    # 构造 MIME 数据，包含被拖拽 Actor 的路径
    data_string = ";".join(str(p) for p in actor_paths)
    mime_data = QtCore.QMimeData()
    mime_data.setData("application/x-orca-actor-reparent", data_string.encode("utf-8"))

    drag = QtGui.QDrag(self)
    drag.setMimeData(mime_data)
    drag.exec(QtCore.Qt.DropAction.CopyAction)
```

**Model 端接收**：

```python
# orcalab/ui/actor_outline_model.py

def dropMimeData(self, data, action, row, column, parent):
    if data.hasFormat(self.reparent_mime):
        ok, reparent_data = self.prepare_reparent_data(data, action, row, column, parent)
        if not ok:
            return False

        # 批量重排
        new_parent_paths = [reparent_data.parent_path] * len(reparent_data.actor_paths)
        insert_positions = [row] * len(reparent_data.actor_paths)

        async def _do_reparent():
            await SceneEditRequestBus().move_actors(
                reparent_data.actor_paths,
                new_parent_paths,
                insert_positions,
                undo=True,
                source="actor_outline",
            )
        asyncio.create_task(_do_reparent())
        return True
```

#### 4.4 重命名 Actor

**触发**：右键点击 Actor → 选择 "Rename"

```python
# orcalab/ui/actor_outline.py

def _open_rename_dialog(self):
    dialog = RenameDialog(self._current_actor_path, can_rename_actor, self)
    if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
        asyncio.create_task(
            SceneEditRequestBus().rename_actor(
                self._current_actor,
                dialog.new_name,
                undo=True,
                source="actor_outline",
            )
        )
```

**Service 端处理**：

```python
# orcalab/scene_edit_service.py

async def _rename_actor(self, actor, new_name, undo=True, source=""):
    ok, err = self.local_scene.can_rename_actor(actor, new_name)
    if not ok:
        raise Exception(err)

    actor, actor_path = self.local_scene.get_actor_and_path(actor)
    old_path = actor_path
    new_path = actor_path.parent() / new_name

    # 更新 selection / active_actor 中的路径
    if actor_path in self.local_scene.selection:
        new_selection.remove(actor_path)
        new_selection.append(new_path)
    if actor_path == self.local_scene.active_actor:
        new_active_actor = new_path

    # 本地重命名
    await bus.before_actor_renamed(actor_path, new_name, source)
    self.local_scene.rename_actor(actor, new_name)
    await bus.on_actor_renamed(actor_path, new_name, source)

    # 更新 selection / active_actor
    if deselect_command:
        await self._set_selection(new_selection, False, source)
    if deactive_command:
        await self._set_active_actor(new_active_actor, False, source)

    # 加入撤销栈
    rename_command = RenameActorCommand()
    rename_command.old_path = old_path
    rename_command.new_path = new_path
    UndoRequestBus().add_command(command_group)
```

---

### 5. 现有设计约束

#### 5.1 层级结构约束

| 约束 | 说明 |
|------|------|
| **仅 GroupActor 可作为父级** | `BaseActor.parent` 的 setter 强制要求 `GroupActor` 类型；`AssetActor` 不能拥有子级 |
| **名称唯一性** | 同一父级下 Actor 名称必须唯一，由 `LocalScene.can_add_actor()` 和 `can_rename_actor()` 保证 |
| **根节点不可操作** | `root_actor`（路径 `"/"`）不可删除、不可重命名、不可重排 |
| **路径变更级联** | 重命名或重排父级时，所有子级的 `Path` 都需要通过 `_replace_path()` 级联更新 |

#### 5.2 拖拽约束

| 约束 | 说明 |
|------|------|
| **多选拖拽限制** | 多选 Actor 拖拽时，要求所有选中 Actor 必须在同一父级下（`mouseMoveEvent` 中检查） |
| **不能拖拽到自身** | `can_move_actors()` 检查 `actor_path == new_parent_path` |
| **不能拖拽到后代** | `can_move_actors()` 检查 `new_parent_path.is_descendant_of(actor_path)` |
| **仅支持 CopyAction** | `setDefaultDropAction(Qt.DropAction.CopyAction)`，拖拽时创建副本而非移动 |

#### 5.3 撤销/重做约束

| 约束 | 说明 |
|------|------|
| **命令粒度** | 批量操作（如批量删除）封装为 `CommandGroup`，内部包含多个子命令 |
| **不保存 Actor 引用** | `DeleteActorCommand` 保存 Actor 作为模板，但撤销时是重新创建而非恢复原始对象 |
| **显隐/锁定不入栈** | `set_actor_visible` 和 `set_actor_locked` 默认 `undo=False`，不加入撤销栈 |

#### 5.4 同步约束

| 约束 | 说明 |
|------|------|
| **本地优先** | 先在 `LocalScene` 修改，再同步到 `RemoteScene`；远程失败时回滚本地修改 |
| **编辑锁** | `_edit_lock` 保证同一时刻只有一个编辑操作在进行，防止状态竞争 |
| **来源过滤** | `source == "remote_scene"` 的消息在编辑锁持有时被忽略，防止循环同步 |

#### 5.5 UI 约束

| 约束 | 说明 |
|------|------|
| **单列表头隐藏** | `setHeaderHidden(True)`，大纲视图不显示列头 |
| **自定义绘制** | 使用 `ActorOutlineDelegate` 绘制每行的 eye/lock 按钮，不通过标准 `QTreeView` 分支控件实现 |
| **选择延迟** | 鼠标左键抬起时才更新选择（而非按下时），避免拖拽过程中误选 |
| **模型重置策略** | 删除和重排操作使用 `beginResetModel/endResetModel`，而非细粒度的 `beginRemoveRows/beginInsertRows` |

---

## 第二部分：架构调整目标（待补充）

> 本节将在后续迭代中补充，用于定义支持更复杂层级结构的具体改造方案。
