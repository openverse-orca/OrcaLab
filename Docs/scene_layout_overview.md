# OrcaLab 中资产包 / 场景 / 布局关系说明

本说明旨在帮助团队理解 OrcaLab 在内容加载与编辑流程中如何组织「资产包（pak）」「场景（scene）」与「布局（layout）」三者之间的关系。整体而言，资产包是内容来源，场景是产品侧的逻辑关卡概念，而布局则是 OrcaLab 内部用于渲染与编辑的运行时表示。

## 概念摘要

- **资产包（Asset Package）**：通常以 `.pak` 形式储存，内部包含资产文件与 `scene_layouts.json` 等元数据。OrcaLab 在启动时会扫描缓存目录并将布局数据解压到用户目录，确保每次启动都能获取最新版本。
- **场景（Scene）**：代表可供用户选择的关卡；`scene_layouts.json` 文件中的每个 `scene` 条目记录了场景名称、spawnable 路径以及用于编辑器展示的树形结构。
- **布局（Layout）**：OrcaLab 内部的运行时结构，与界面中的 `local_scene` 与 `GroupActor/AssetActor` 对象一一对应。布局既可以来自默认生成，也可以由用户修改后保存为 `.json`。

## 数据结构关系（文本示意图）

```
┌────────────┐
│ 资产包 (.pak)│
└──────┬─────┘
       │包含 scene_layouts.json
┌──────▼─────┐
│ 场景元数据 │<─── spawnablePath (对应 .spawnable)
│ Scene Meta │──┐
└──────┬─────┘  │定义 layout 树
       │        │
┌──────▼─────┐  │
│ 布局节点    │──┘
│ LayoutNode │→ GroupActor / AssetActor
└────────────┘
```

## 启动与加载流程（字符流程图）

```
[启动 OrcaLab]
        │
        ▼
[扫描 pak 缓存]─┬─>复制/更新 pak
                │
                ▼
[提取 scene_layouts.json 至 user/scene_layouts]
                │
                ▼
[场景选择对话框]
       ├─选择空白布局→[初始化 root GroupActor]
       └─选择默认布局→[SceneLayoutConverter 生成 default_layout.json]
                │
                ▼
[load_scene_layout → create_actor_from_scene_layout]
                │
                ▼
[UndoService 建立命令栈，SceneEditService 同步远程场景]
                │
                ▼
[用户编辑 / 保存 / 另存]
```

## 运行要点

1. **资产包更新策略**：每次启动都会覆盖 `user/scene_layouts/{pak}.json`，确保布局信息与资产包版本对应。
2. **默认布局生成**：用户选择“加载默认布局”时，会以 spawnable 路径匹配场景条目并调用 `SceneLayoutConverter.convert_scene()` 生成 OrcaLab 布局。若转换失败，会提示用户转为使用空白布局。
3. **布局编辑状态**：`UndoService` 所记录的每个命令都会将当前布局标记为“已修改”。关闭窗口或打开新文件时，`_confirm_discard_changes()` 会提示用户是否保存或放弃修改。
4. **保存与另存为**：`save_scene_layout()` 会写回当前布局路径；“另存为”则更新 `current_layout_path`，并在窗口标题中显示 `[* layout]` 来提示未保存状态。

## 使用建议

- **区分资产层与布局层**：默认布局仅描述场景中资产实例的结构，不包含真实资源文件。若出现 “Spawnable not found”，需要确认资产包是否完整或 spawnable 路径是否正确。
- **保持缓存目录整洁**：建议定期清理 `Cache/linux` 与 `user/tmp`，避免旧版本的 `.pak` 或默认布局文件影响编辑体验。
- **版本管理**：文档建议始终记录场景布局的发布时间与 `.pak` 版本号，方便追踪问题；在多人协作场景中，可将 `.json` 布局纳入 Git 管理。

通过理解以上数据流与模块职责，团队成员即可更高效地调试资源加载、场景编辑以及布局保存等相关功能。

