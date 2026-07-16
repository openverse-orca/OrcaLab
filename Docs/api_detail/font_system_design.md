# OrcaLab 字体管理系统设计文档

## 1. 总体架构设计思想、假设和约束

### 1.1 设计思想

OrcaLab 字体管理系统采用 **集中配置 + 单例服务 + 回调通知** 的架构模式，将分散在各 UI 组件中的字体定义统一管理，并提供全局缩放能力。

核心设计原则：

- **配置与代码分离**：所有字体定义集中在 TOML 配置文件中，修改字体风格无需改动代码。
- **单例服务**：`FontService` 作为全局唯一的字体管理入口，所有组件通过它获取字体配置。
- **回调驱动**：缩放比例变化时，通过回调机制通知所有已注册的组件更新字体，无需组件主动轮询。
- **继承机制**：字体配置支持 `base` 继承，子配置可仅声明与基配置不同的属性，减少重复定义。
- **DPI 自适应**：以 point（pt）为基本单位，自动根据屏幕 DPI 换算像素值，确保在不同 DPI 设置下显示一致。

### 1.2 假设

- 应用程序使用 PySide6 (Qt for Python) 作为 UI 框架。
- 屏幕 DPI 通过 `QGuiApplication.primaryScreen().logicalDotsPerInch()` 获取，在运行时可能变化。
- 字体缩放比例以 10% 为步长，范围 50%~200%。
- 所有 UI 组件在初始化时主动向 FontService 注册字体更新回调。

### 1.3 约束

- 字体配置使用 TOML 格式，放置在 `ui/fonts/font_config.toml`。
- 缩放比例持久化存储在 `ConfigService` 中，键名为 `orcalab.font_scale_percent`。
- 字体继承链不允许循环引用，否则会在解析时报错并跳过。
- 使用 `bind_widget_font` 时，如果组件同时使用 `setStyleSheet` 设置样式表，需确保样式表中不包含 `font-size`、`font-family` 等字体属性，否则会覆盖 `setFont` 的设置。

---

## 2. 运行时代码流程图

### 2.1 应用启动时的字体初始化流程

```
应用启动
    │
    ▼
FontService.__new__()  ──►  _init()
    │                           │
    │                           ├─ _load_config()
    │                           │       │
    │                           │       ├─ 读取 font_config.toml
    │                           │       ├─ 解析 [fonts.*] 各配置项
    │                           │       └─ _resolve_inheritance()
    │                           │               │
    │                           │               └─ 递归解析 base 继承链
    │                           │
    │                           └─ _load_scale_factor()
    │                                   │
    │                                   └─ 从 ConfigService 读取持久化的缩放比例
    │
    ▼
各 UI 组件初始化
    │
    ├─ 调用 FontService().bind_widget_font(widget, key)
    │       │
    │       ├─ 立即调用 widget.setFont(font) 设置初始字体
    │       ├─ 注册缩放回调到 _callbacks
    │       └─ 连接 widget.destroyed 信号，自动清理回调
    │
    ├─ 或调用 FontService().bind_widget_stylesheet(widget, build_css)
    │       │
    │       ├─ 立即调用 widget.setStyleSheet(css) 设置初始样式
    │       ├─ 注册缩放回调到 _callbacks
    │       └─ 连接 widget.destroyed 信号，自动清理回调
    │
    └─ 或调用 FontService().on_scale_changed(callback)
            │
            └─ 注册自定义回调，返回 cb_id 用于后续移除
```

### 2.2 用户调整缩放比例时的更新流程

```
用户在设置面板点击 "+" / "-" / "重置"
    │
    ▼
SettingsDialog._on_font_scale_up()
    │
    ├─ FontService().increase_scale()
    │       │
    │       ├─ set_scale_percent(当前值 + 10)
    │       │       │
    │       │       ├─ 按 10% 取整、限制在 [50, 200] 范围
    │       │       ├─ 若值与上次相同则直接返回
    │       │       ├─ _save_scale_factor() ──► ConfigService 持久化
    │       │       ├─ scale_changed 信号发射
    │       │       └─ _fire_callbacks()
    │       │               │
    │       │               └─ 遍历 _callbacks，逐个执行刷新函数
    │       │                       │
    │       │                       ├─ bind_widget_font 注册的回调：
    │       │                       │       └─ widget.setFont(get_font(key))
    │       │                       │
    │       │                       ├─ bind_widget_stylesheet 注册的回调：
    │       │                       │       └─ widget.setStyleSheet(build_css())
    │       │                       │
    │       │                       └─ on_scale_changed 注册的自定义回调：
    │       │                               └─ 执行自定义刷新逻辑
    │       │
    │       └─ (返回)
    │
    └─ 更新 UI 上的百分比显示文本
```

### 2.3 组件获取字体的内部流程

```
组件调用 FontService().get_font("property_edit")
    │
    ▼
get_config("property_edit")
    │
    ├─ 在 _configs 字典中查找 key
    ├─ 若找到，返回 FontConfig 对象
    └─ 若未找到，返回默认 FontConfig(size=11)
    │
    ▼
_scaled_size(cfg.size)
    │
    └─ math.floor(base_size * scale_percent / 100)
    │
    ▼
构造 QFont 对象
    │
    ├─ 设置字体族 (family)
    ├─ 设置字号：
    │   ├─ 若 unit == "pt"：font.setPointSize(scaled)
    │   └─ 若 unit == "px"：font.setPixelSize(scaled)
    ├─ 设置字重：
    │   ├─ 若 weight > 0：font.setWeight(weight)
    │   └─ 否则：font.setBold(bold)
    └─ 设置斜体：font.setItalic(italic)
    │
    ▼
返回 QFont 对象给组件
```

---

## 3. 配置文件说明

### 3.1 文件位置

`ui/fonts/font_config.toml`

### 3.2 配置格式

每个字体配置以 `[fonts.<key>]` 表头定义，支持以下字段：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `family` | string | `""` | 字体族名称，多个用逗号分隔（如 `"Consolas, Monaco, monospace"`） |
| `size` | integer | `11` | 基础字号，单位由 `unit` 字段决定 |
| `bold` | boolean | `false` | 是否粗体 |
| `italic` | boolean | `false` | 是否斜体 |
| `weight` | integer | `0` | 字重数值（如 `600`），优先级高于 `bold` |
| `unit` | string | `"pt"` | 字号单位，`"pt"`（点）或 `"px"`（像素） |
| `base` | string | `""` | 继承的基配置键名，未显式声明的属性从基配置继承 |

### 3.3 继承机制

当配置项设置了 `base` 字段时，未在当前配置中显式声明的属性将从基配置继承。例如：

```toml
[fonts.body]
size = 11

[fonts.property_title]
base = "body"
bold = true
```

`property_title` 继承 `body` 的 `size=11`，仅覆盖 `bold=true`。等价于：

```toml
[fonts.property_title]
size = 11
bold = true
```

继承链支持多层，但禁止循环引用。

### 3.4 当前完整配置清单

| 配置键 | 用途 | 基配置 |
|--------|------|--------|
| `body` | 正文字体 | - |
| `small` | 小号字体 | - |
| `tiny` | 极小字体 | - |
| `title` | 标题字体（粗体） | - |
| `subtitle` | 副标题字体（粗体） | - |
| `button` | 按钮字体（粗体） | - |
| `button_paint` | 工具栏按钮字体 | - |
| `status_bar` | 状态栏字体（粗体） | - |
| `terminal` | 终端字体（等宽） | - |
| `terminal_status` | 终端状态字体 | - |
| `property_edit` | 属性编辑器字体 | - |
| `property_title` | 属性标题（粗体） | `body` |
| `asset_browser_label` | 资源浏览器标签 | - |
| `asset_browser_title` | 资源浏览器标题（粗体） | - |
| `setting_title` | 设置面板标题（字重600） | - |
| `setting_description` | 设置面板描述 | - |
| `setting_field` | 设置面板字段 | - |
| `dialog_title` | 对话框标题（粗体） | - |
| `sync_status` | 同步状态字体 | - |
| `thumbnail_loading` | 缩略图加载提示（粗体） | - |
| `monospace` | 等宽字体 | - |
| `monospace_small` | 小号等宽字体 | - |
| `group_title` | 分组标题（粗体） | - |
| `path_label` | 路径标签（等宽） | - |
| `installer_status` | 安装器状态（粗体） | - |
| `installer_log` | 安装器日志（等宽） | - |
| `copilot_input` | Copilot 输入框（等宽） | - |
| `copilot_log` | Copilot 日志（等宽） | - |
| `loading_dialog` | 加载对话框字体 | - |
| `hint_text` | 提示文本（斜体） | `body` |
| `group_box_title` | 分组框标题（粗体） | `body` |
| `badge_text` | 徽标文本（斜体） | `body` |
| `entity_info` | 实体信息（斜体） | `body` |
| `outline` | 大纲面板字体 | - |
| `collapsible_header` | 可折叠标题字体 | - |
| `camera_group_title` | 相机分组标题（粗体） | `body` |
| `camera_source` | 相机源文本（斜体） | `body` |
| `camera_selector` | 相机选择器字体 | - |
| `panel_title` | 面板标题（粗体） | - |
| `tree_header` | 树控件表头（粗体） | - |

---

## 4. 添加新对象的开发方法

### 4.1 添加新的字体配置项

**步骤 1**：在 `font_config.toml` 中添加配置项

```toml
[fonts.my_component]
family = "Arial, sans-serif"
size = 12
bold = false
italic = false
weight = 0
unit = "pt"
```

如果新配置与现有配置相似，可使用 `base` 继承：

```toml
[fonts.my_component]
base = "body"
bold = true
```

**步骤 2**：在代码中使用 FontService 获取字体

根据组件的渲染方式，选择以下三种方式之一：

### 4.2 方式一：使用 `bind_widget_font`（推荐，适用于标准 QWidget）

适用于直接使用 QWidget 及其子类的组件。通过 `setFont()` 设置字体，不影响样式表。

```python
from orcalab.ui.fonts.font_service import FontService

class MyWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        label = QtWidgets.QLabel("Hello")
        FontService().bind_widget_font(label, 'my_component')
        
        # 如果组件同时使用 setStyleSheet，确保样式表中不包含字体属性
        label.setStyleSheet("color: white; background: black;")
```

如果组件需要通过 CSS 设置字体（例如 QPushButton 需要完整的样式表），可使用 `use_css=True`：

```python
FontService().bind_widget_font(
    button, 'my_component',
    use_css=True,
    extra_css="QPushButton { background: blue; color: white; }",
)
```

### 4.3 方式二：使用 `bind_widget_stylesheet`（适用于动态 CSS 构建）

适用于需要根据状态动态构建完整样式表的组件。每次缩放变化时重新构建整个 CSS。

```python
class MyButton(QtWidgets.QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        FontService().bind_widget_stylesheet(self, self._build_style)
    
    def _build_style(self) -> str:
        theme = ThemeService()
        return f"""
            QPushButton {{
                background-color: {theme.get_color_hex("bg")};
                color: {theme.get_color_hex("text")};
                {FontService().get_font_css("my_component")}
            }}
        """
```

### 4.4 方式三：使用 `on_scale_changed` 注册自定义回调

适用于 QPainter 自绘组件、Delegate 等无法直接绑定 widget 的场景。

```python
class MyPainterWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._fs = FontService()
        self._fs_cb_id = self._fs.on_scale_changed(self._on_font_scale_changed)
        self._font = self._fs.get_font("my_component")
    
    def _on_font_scale_changed(self):
        self._font = self._fs.get_font("my_component")
        self.update()  # 触发重绘
    
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setFont(self._font)
        painter.drawText(self.rect(), "Hello")
    
    def destroy(self):
        self._fs.remove_on_scale_changed(self._fs_cb_id)
        super().destroy()
```

对于 QPainter 中需要基于基础字体做微调的场景（如斜体、粗体），使用 `apply_font_modifiers`：

```python
def paintEvent(self, event):
    painter = QtGui.QPainter(self)
    font = FontService().apply_font_modifiers("badge_text", painter.font())
    painter.setFont(font)
    painter.drawText(self.rect(), "badge")
```

### 4.5 字体缩放的工作原理

字体缩放功能已内置于设置面板中，用户可通过 `+` / `-` 按钮调整全局缩放比例，点击"重置"恢复 100%。其工作原理如下：

**缩放流程**：

```
用户点击 "+" 按钮
    │
    ▼
SettingsDialog._on_font_scale_up()
    │
    └─ FontService().increase_scale()
            │
            ├─ set_scale_percent(当前值 + 10)
            │       │
            │       ├─ 按 10% 取整（如 133% → 130%）
            │       ├─ 限制在 [50%, 200%] 范围
            │       ├─ 若值与上次相同则直接返回（避免无效刷新）
            │       ├─ _save_scale_factor() ──► ConfigService 持久化
            │       └─ _fire_callbacks() ──► 遍历所有回调，逐个执行刷新
            │
            └─ (返回)
```

**缩放对字号的影响**：

每个字体配置项的实际显示字号 = `floor(基础字号 × 缩放比例 / 100)`。例如：

| 基础字号 | 缩放 100% | 缩放 130% | 缩放 150% | 缩放 70% |
|---------|-----------|-----------|-----------|----------|
| 11pt    | 11pt      | 14pt      | 16pt      | 7pt      |
| 9pt     | 9pt       | 11pt      | 13pt      | 6pt      |
| 14pt    | 14pt      | 18pt      | 21pt      | 9pt      |

**缩放比例持久化**：

- 缩放比例通过 `ConfigService` 持久化存储，键名为 `orcalab.font_scale_percent`。
- 应用重启后，`FontService._load_scale_factor()` 自动恢复上次的缩放比例。
- 缩放比例独立于系统 DPI 设置，两者叠加生效：最终像素 = `floor(基础字号 × 缩放比例 / 100) × DPI / 72`。

---

## 5. 注意事项

### 5.1 样式表与 setFont 的冲突

当组件同时使用 `setStyleSheet()` 和 `setFont()` 时，Qt 的样式表机制会覆盖 `setFont()` 的设置。因此：

- **使用 `bind_widget_font` 时**：确保组件的样式表中不包含 `font-size`、`font-family`、`font-weight`、`font-style` 等字体属性。
- **使用 `bind_widget_stylesheet` 时**：通过 `get_font_css()` 将字体信息嵌入样式表字符串中，确保字体属性在样式表中正确设置。

### 5.2 回调生命周期管理

- `bind_widget_font` 和 `bind_widget_stylesheet` 会自动连接 widget 的 `destroyed` 信号，在 widget 销毁时自动移除回调。
- 使用 `on_scale_changed` 注册的自定义回调需要手动管理生命周期，在组件销毁时调用 `remove_on_scale_changed(cb_id)`。
- 回调函数中应捕获可能发生的异常，避免单个组件的刷新失败影响其他组件。

### 5.3 字体单位选择

- **优先使用 pt（点）单位**：pt 是物理单位，会自动根据屏幕 DPI 缩放，在不同分辨率的显示器上保持一致的物理尺寸。
- **px（像素）单位**：仅在需要精确像素对齐的场景下使用（如终端字体与行高严格匹配）。
- 在 CSS 中，`font-size: 11pt` 和 `font-size: 11px` 在 Qt 中的渲染行为不同，pt 会乘以 DPI/72 系数。

### 5.4 继承配置的注意事项

- 继承链解析在 `_load_config()` 阶段完成，运行时修改配置不会触发重新解析。
- 继承仅对未显式声明的属性生效。如果子配置显式声明了某个属性（即使值与基配置相同），也不会从基配置继承。
- 循环继承会在启动时检测并报错，被循环引用的配置将使用默认值。

### 5.5 缩放比例的限制

- 缩放范围：50% ~ 200%，步长 10%。
- 缩放比例会自动取整到最近的 10% 倍数。
- 缩放后的字号通过 `math.floor()` 向下取整，确保不会因四舍五入导致布局溢出。
- 缩放比例持久化存储在配置文件中，应用重启后自动恢复。

### 5.6 性能考虑

- `_fire_callbacks()` 会同步遍历所有已注册的回调，回调数量较多时可能引起短暂的界面卡顿。建议回调函数保持轻量。
- 对于频繁重建的临时 widget，确保 `destroyed` 信号正确触发，避免回调泄漏。
- `get_font_css()` 每次调用都会构造新的字符串，在频繁调用的场景（如 `paintEvent`）中建议缓存结果。

### 5.7 调试建议

- 设置日志级别为 DEBUG 可查看字体配置加载和继承解析的详细信息。
- 使用 `FontService().get_config(key)` 可检查某个配置项的最终解析结果。
- 使用 `FontService().get_scale_percent()` 可查看当前缩放比例。
