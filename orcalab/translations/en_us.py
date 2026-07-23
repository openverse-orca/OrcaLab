TRANSLATIONS = {
    "OrcaLab 启动器\n\n": "OrcaLab launcher\n\n",
    ("已运行图形界面时，可用「orcalab-cli …」在终端调用 MCP 工具（参见 orcalab-cli -h）。\n\n"): (
        'When the GUI is already running, use "orcalab-cli ..." in a terminal to call '
        "MCP tools (see orcalab-cli -h).\n\n"
    ),
    (
        "控制台日志等级（支持 DEBUG/INFO/WARNING/ERROR/CRITICAL），默认输出 WARNING "
        "及以上，日志文件会记录 INFO 及以上的全部日志。"
    ): (
        "Console log level (DEBUG/INFO/WARNING/ERROR/CRITICAL). Defaults to WARNING and "
        "above; log files record INFO and above."
    ),
    "工作目录，默认为当前目录": "Workspace directory. Defaults to the current directory.",
    "初始化配置文件并退出": "Initialize the config file and exit",
    "输出所有信息到终端": "Print all messages to the terminal",
    "设置并保存界面语言（zh_CN 或 en_US），后续启动继续使用该设置。": (
        "Set and save the UI language (zh_CN or en_US) for subsequent launches."
    ),
    "指定要加载的场景文件。不指定会弹出场景选择界面。": (
        "Specify the scene file to load. If omitted, the scene selection dialog opens."
    ),
    "指定要加载的布局文件。'default', 'blank' 或者布局文件路径。不指定会加载默认布局。": (
        "Specify the layout file to load: 'default', 'blank', or a layout path. If "
        "omitted, the default layout is loaded."
    ),
    (
        "指定要加载的仿真配置名称，必须在配置文件中存在。如果是'external'则使用外部程序模式启动。"
        "        不指定会弹出配置选择界面。这个参数只有在'--full-screen'模式下才会生效。"
    ): (
        "Specify the simulation config name. It must exist in the config file. Use "
        "'external' to launch in external program mode. If omitted, the config selection "
        "dialog opens. This option only takes effect with '--full-screen'."
    ),
    "以全屏模式启动应用": "Launch in full-screen mode",
    "URL服务端口号（默认：50651）。如果端口被占用，程序会自动尝试其他端口。": (
        "URL service port (default: 50651). If occupied, OrcaLab automatically tries another port."
    ),
    "强制指定 GPU 适配器名称（子串匹配，不区分大小写），例如 NVIDIA、RTX、MTT": (
        "Force a GPU adapter by name (case-insensitive substring match), such as NVIDIA, RTX, or MTT."
    ),
    "当 --force-adapter 匹配到多个 GPU 时，选择第几个（默认 0）": (
        "When --force-adapter matches multiple GPUs, choose the index to use (default: 0)."
    ),
    "工作目录无效: {workspace} ({error})": "Invalid workspace: {workspace} ({error})",
    "工作目录不是文件夹: {path}": "Workspace is not a directory: {path}",
    "工作目录不可读: {path}": "Workspace is not readable: {path}",
    "工作目录不可写（无法初始化配置）: {path}": "Workspace is not writable (cannot initialize config): {path}",
    "工作目录不存在: {path}": "Workspace does not exist: {path}",
    "工作目录的父路径不存在或不是文件夹: {path}": "Workspace parent path does not exist or is not a directory: {path}",
    "父目录无写权限，无法创建工作目录: {path}": "Parent directory is not writable; cannot create workspace: {path}",
    "设置": "Settings",
    "相机移动灵敏度": "Camera Move Sensitivity",
    "控制相机平移时的移动速度 (范围: 0.1-10)": "Controls camera pan speed (range: 0.1-10)",
    "相机旋转灵敏度": "Camera Rotation Sensitivity",
    "控制相机旋转时的旋转速度 (范围: 0.1-10)": "Controls camera rotation speed (range: 0.1-10)",
    "帧率限制": "Frame Rate Limit",
    "限制视口渲染帧率以降低 GPU 负载": "Limit viewport rendering FPS to reduce GPU load",
    "垂直同步 (VSync)": "Vertical Sync (VSync)",
    "开启 VSync 可防止画面撕裂，关闭可提高帧率。需重启生效": (
        "Enable VSync to prevent tearing, or disable it for higher FPS. Restart required."
    ),
    "界面语言": "Interface Language",
    "选择 OrcaLab 的界面语言。重启应用后生效": (
        "Choose the language used by the OrcaLab interface. Restart required."
    ),
    "英语": "English",
    "简体中文": "Simplified Chinese",
    "自动": "Auto",
    "重置": "Reset",
    "界面字体缩放": "UI Font Scale",
    "调整全局字体大小百分比，按 10% 步进，范围 50%-200%": "Adjust the global UI font size in 10% steps, range 50%-200%",
    "发送用户环境统计数据可以帮助改进OrcaLab。": "Sending anonymous environment statistics helps improve OrcaLab.",
    "确定": "OK",
    "取消": "Cancel",
    "保存": "Save",
    "图形设置": "Graphics Settings",
    "质量预设": "Quality Preset",
    "全局图形质量等级，影响阴影、纹理等（需重启生效）": (
        "Global graphics quality level, affects shadows, textures, etc. (restart required)"
    ),
    "抗锯齿模式": "Anti-Aliasing Mode",
    "MSAA 为多重采样，TAA 为时域抗锯齿，SMAA 为子像素形态学抗锯齿": (
        "MSAA = multi-sampling, TAA = temporal AA, SMAA = sub-pixel morphological AA"
    ),
    "MSAA 采样数": "MSAA Sample Count",
    "仅在抗锯齿模式为 MSAA 时生效。采样数越高画质越好但性能越低": (
        "Only effective when AA mode is MSAA. Higher sample count = better quality but lower performance"
    ),
    "阴影过滤方法": "Shadow Filtering Method",
    "方向光阴影的过滤算法。EsmPcf 质量最高，Pcf 次之": (
        "Directional light shadow filtering algorithm. EsmPcf has highest quality, Pcf next"
    ),
    "阴影采样数": "Shadow Sample Count",
    "阴影采样点数量。采样越多阴影越柔和但性能越低": (
        "Number of shadow samples. More samples = softer shadows but lower performance"
    ),
    "纹理质量": "Texture Quality",
    "控制纹理流式加载的 mip 偏移。高质量加载完整纹理，低质量节省显存": (
        "Controls texture streaming mip bias. High quality loads full textures, low quality saves VRAM"
    ),
    "Bloom (泛光)": "Bloom",
    "高亮区域的辉光效果": "Glow effect on bright areas",
    "景深 (DOF)": "Depth of Field",
    "模拟相机镜头的景深模糊效果": "Simulates camera lens depth-of-field blur",
    "雾效": "Fog",
    "场景中的体积雾与距离雾": "Volumetric and distance fog in the scene",
    "低": "Low",
    "中": "Medium",
    "高": "High",
    "超高": "Ultra",
    "关闭": "Off",
    "默认": "Default",
    "无": "None",
    "图形设置已保存，需要重启应用才能生效。": "Graphics settings saved. Restart required to take effect.",
    "自定义": "Custom",
    "全局图形质量等级，自动调整下方关联设置。单独修改任一设置将切换为自定义": (
        "Global graphics quality level, auto-adjusts related settings below. "
        "Modifying any individual setting switches to Custom"
    ),
    "Culling 任务粒度": "Culling Task Granularity",
    "每 Job 处理的 Culling 条目数。值越大派发次数越少，负载越集中": (
        "Culling entries per Job. Larger value = fewer dispatches, more concentrated load"
    ),
    "限制视口渲染帧率以降低 GPU 负载。0 为自动跟随屏幕刷新率": (
        "Limit viewport render FPS to reduce GPU load. 0 = auto-follow screen refresh rate"
    ),
    "选择场景": "Select Scene",
    "请选择场景：": "Please select a scene:",
    "布局选项": "Layout Options",
    "加载默认布局": "Load Default Layout",
    "空白布局": "Blank Layout",
    "打开": "Open",
    "场景加载中": "Loading Scene",
    "保存场景布局": "Save Scene Layout",
    "新建场景布局": "New Scene Layout",
    "打开场景布局": "Open Scene Layout",
    "布局文件 (*.json);;所有文件 (*)": "Layout Files (*.json);;All Files (*)",
    "未保存的修改": "Unsaved Changes",
    "当前布局有未保存的修改": "The current layout has unsaved changes.",
    "放弃修改": "Discard Changes",
    "保存修改": "Save Changes",
    "场景布局加载错误": "Scene Layout Load Error",
    "场景布局加载警告": "Scene Layout Load Warning",
    "加载默认布局失败": "Failed to Load Default Layout",
    "所选场景的默认布局加载失败。\n": "The default layout for the selected scene could not be loaded.\n",
    "所选场景的默认布局加载失败。\n请复制下方错误信息寻求帮助，并重新启动程序选择“空白布局”。\n\n": (
        "The default layout for the selected scene could not be loaded.\n"
        "Copy the error details below when asking for help, then restart the application "
        'and select "Blank Layout".\n\n'
    ),
    "加载场景布局时产生 {count} 条警告：": "The scene layout loaded with {count} warnings:",
    "布局文件路径无效": "Invalid layout file path",
    "布局文件格式错误": "Invalid layout file format",
    "布局文件版本号缺失": "The layout file version is missing",
    "加载旧版(v1.0/v2.0)场景布局，建议重新保存以升级到 v3.0 格式": (
        "This scene uses the legacy v1.0/v2.0 layout format. Save it again to upgrade to v3.0."
    ),
    "布局文件版本号 {version} 不支持": "Layout file version {version} is not supported",
    "加载布局文件 {filename} 时出错: {error}": "Error loading layout file {filename}: {error}",
    "创建 Actor {name} 失败: {error}, asset_path: {asset_path}": (
        "Failed to create Actor {name}: {error}, asset_path: {asset_path}"
    ),
    "创建 Actor {name} 失败: {error}": "Failed to create Actor {name}: {error}",
    "创建 Actor {name} 后处理失败: {error}, asset_path: {asset_path}": (
        "Post-processing failed for Actor {name}: {error}, asset_path: {asset_path}"
    ),
    "跳过 Actor {name}: 资产不存在, asset_path: {asset_path}": (
        "Skipped Actor {name}: asset does not exist, asset_path: {asset_path}"
    ),
    "场景布局(v3)版本不匹配，期望 {expected}，实际 {actual}": (
        "Scene layout (v3) version mismatch: expected {expected}, got {actual}"
    ),
    "场景布局(v3)文件格式错误": "Invalid scene layout (v3) file format",
    "跳过 {name}, Actor名称{name}非法。": "Skipped {name}: invalid Actor name {name}.",
    "跳过 {path}, 资产{asset_path}不存在。": ("Skipped {path}: asset {asset_path} does not exist."),
    "文件": "File",
    "编辑": "Edit",
    "运行": "Run",
    "帮助": "Help",
    "用户": "User",
    "插件": "Plugins",
    "新建布局…": "New Layout...",
    "打开布局…": "Open Layout...",
    "保存布局": "Save Layout",
    "另存为…": "Save As...",
    "退出": "Exit",
    "关于 OrcaLab": "About OrcaLab",
    "版权所有": "Copyright",
    "公司主页": "Company Website",
    "GitHub 仓库": "GitHub Repository",
    "松应科技": "Songying Technology",
    "云原生机器人仿真平台，提供先进的UI和资产管理功能": (
        "A cloud-native robotics simulation platform with advanced UI and asset management capabilities"
    ),
    "撤销": "Undo",
    "重做": "Redo",
    "复制": "Copy",
    "删除": "Delete",
    "恢复视角": "Restore View",
    "配置": "Settings",
    "开始模拟": "Start Simulation",
    "停止模拟": "Stop Simulation",
    "查看XML": "View XML",
    "安装插件…": "Install Plugin...",
    "管理插件…": "Manage Plugins...",
    "退出登录": "Log Out",
    "未登录": "Not Signed In",
    "当前用户: {username}": "Current User: {username}",
    "确定要退出登录吗？\n退出后需要重新启动应用程序。": (
        "Are you sure you want to log out?\nRestart the application after logging out."
    ),
    "退出登录成功": "Logged Out Successfully",
    "已成功退出登录。\n请重新启动应用程序以完成登录。": (
        "You have been logged out successfully.\nRestart the application to sign in again."
    ),
    "插件管理": "Plugin Manager",
    "安装插件": "Install Plugin",
    "已安装的插件": "Installed Plugins",
    "启用": "Enabled",
    "名称": "Name",
    "版本": "Version",
    "描述": "Description",
    "修改启用状态后需重启 OrcaLab 生效": "Restart OrcaLab after changing the enabled state.",
    "卸载选中插件": "Uninstall Selected Plugin",
    "编辑配置": "Edit Configuration",
    "插件系统未初始化": "Plugin system is not initialized",
    "插件配置 - {name}": "Plugin Configuration - {name}",
    "配置文件:": "Configuration File:",
    "在外部编辑器打开": "Open in External Editor",
    "保存": "Save",
    "重新加载": "Reload",
    (
        "此插件未声明配置文件。\n\n在 plugin.toml 中添加 config_files 字段即可支持配置编辑：\n"
        '  config_files = ["bundleMcp.yaml", "config/settings.toml"]'
    ): (
        "This plugin does not declare any configuration files.\n\n"
        "Add a config_files field to plugin.toml to enable configuration editing:\n"
        '  config_files = ["bundleMcp.yaml", "config/settings.toml"]'
    ),
    "已加载: {path}": "Loaded: {path}",
    "加载失败: {error}": "Failed to load: {error}",
    "已保存: {path}": "Saved: {path}",
    "保存成功": "Saved Successfully",
    "配置文件已保存:\n{path}": "Configuration file saved:\n{path}",
    "保存失败": "Save Failed",
    "保存失败: {error}": "Failed to save: {error}",
    "无法保存配置文件:\n{error}": "Unable to save the configuration file:\n{error}",
    "选择插件压缩包 (.tar.xz / .tar.gz)": "Select a plugin archive (.tar.xz / .tar.gz)",
    "浏览…": "Browse...",
    "请选择插件压缩包": "Select a plugin archive",
    "安装": "Install",
    "选择插件压缩包": "Select Plugin Archive",
    "插件压缩包 (*.tar.xz *.tar.gz *.tgz);;所有文件 (*)": ("Plugin Archives (*.tar.xz *.tar.gz *.tgz);;All Files (*)"),
    "点击「安装」开始安装": 'Click "Install" to begin installation',
    "文件不存在: {path}": "File does not exist: {path}",
    "安装完成: {plugin_name} v{version}": "Installation complete: {plugin_name} v{version}",
    "✓ 插件 {plugin_name} 安装成功": "✓ Plugin {plugin_name} installed successfully",
    "插件 {plugin_name} v{version} 安装成功！\n请在插件管理中启用后重启 OrcaLab 生效。": (
        "Plugin {plugin_name} v{version} was installed successfully.\n"
        "Enable it in Plugin Manager, then restart OrcaLab."
    ),
    "完成": "Done",
    "安装失败: {error}": "Installation failed: {error}",
    "开始安装: {archive_name}": "Starting installation: {archive_name}",
    "压缩包不存在: {path}": "Archive does not exist: {path}",
    "解压压缩包…": "Extracting archive...",
    "查找插件清单…": "Locating plugin manifest...",
    "插件: {plugin_name} v{version}": "Plugin: {plugin_name} v{version}",
    "复制文件到 {path}…": "Copying files to {path}...",
    "注册插件…": "Registering plugin...",
    "插件 {plugin_name} 安装完成": "Plugin {plugin_name} installation complete",
    "压缩包中未找到 plugin.toml: {path}": "plugin.toml was not found in the archive: {path}",
    "执行初始化脚本: {script}…": "Running initialization script: {script}...",
    "无初始化脚本，跳过": "No initialization script; skipping",
    "从 requirements.txt 安装 Python 依赖…": ("Installing Python dependencies from requirements.txt..."),
    "安装 Python 依赖…": "Installing Python dependencies...",
    "无 Python 依赖，跳过": "No Python dependencies; skipping",
    "无法执行 init.sh（bash 不可用）: {error}": ("Unable to run init.sh (bash is unavailable): {error}"),
    "init.sh 执行失败 (退出码 {return_code}): {error}": ("init.sh failed (exit code {return_code}): {error}"),
    "Python 依赖安装失败 (退出码 {return_code}): {error}": (
        "Python dependency installation failed (exit code {return_code}): {error}"
    ),
    "requirements.txt 依赖安装失败 (退出码 {return_code}): {error}": (
        "requirements.txt dependency installation failed (exit code {return_code}): {error}"
    ),
    "plugin.toml 解析失败: {error}": "Failed to parse plugin.toml: {error}",
    "卸载插件": "Uninstall Plugin",
    "请先选择要卸载的插件": "Select a plugin to uninstall first",
    "确定要卸载插件 {plugin_name} 吗？\n这将删除插件目录和所有文件。": (
        "Are you sure you want to uninstall {plugin_name}?\nThis will delete the plugin directory and all of its files."
    ),
    "卸载完成": "Uninstall Complete",
    "插件 {plugin_name} 已卸载": "Plugin {plugin_name} was uninstalled",
    "卸载失败": "Uninstall Failed",
    "插件 {plugin_name} 卸载失败，请查看日志": (
        "Failed to uninstall plugin {plugin_name}. Check the logs for details."
    ),
    "提示": "Notice",
    "请先选择一个插件": "Select a plugin first",
    "无配置文件": "No Configuration Files",
    (
        "插件 {plugin_name} 未声明配置文件。\n\n插件可选两种方式提供配置 UI:\n"
        "1. 覆写 PluginBase.create_config_widget() 返回自定义控件\n"
        "2. 在 plugin.toml 中添加 config_files 字段使用通用编辑器"
    ): (
        "Plugin {plugin_name} does not declare any configuration files.\n\n"
        "A plugin can provide configuration UI in either of these ways:\n"
        "1. Override PluginBase.create_config_widget() and return a custom widget\n"
        "2. Add a config_files field to plugin.toml to use the generic editor"
    ),
    "无法保存插件 {plugin_name} 的启用状态:\n{error}": (
        "Unable to save the enabled state for plugin {plugin_name}:\n{error}"
    ),
    "plugin.toml 缺少 [plugin].name: {path}": ("plugin.toml is missing [plugin].name: {path}"),
    "plugin.toml 缺少 [plugin].version: {path}": ("plugin.toml is missing [plugin].version: {path}"),
    "plugin.toml [plugin].entry 必须为 'module.path:ClassName' 格式: {path}": (
        "plugin.toml [plugin].entry must use the 'module.path:ClassName' format: {path}"
    ),
    "● 运行时模式 (RunTime)": "● Runtime Mode",
    "请稍候": "Please Wait",
    "正在初始化引擎，请稍候...   ": "Initializing engine, please wait...   ",
    "大纲": "Outline",
    "属性": "Properties",
    "资产": "Assets",
    "资产分类": "Asset Categories",
    "路径": "Path",
    "小O": "Copilot",
    "终端": "Terminal",
    "相机": "Camera",
    "描述你需要的场景\n例如: “一个卧室有一个白色的床和一个沙发”\n使用 Ctrl+Enter 发送": (
        'Describe the scene you need\nExample: "A bedroom with a white bed and a sofa"\nPress Ctrl+Enter to send'
    ),
    "发送": "Send",
    "开始": "Start",
    "停止": "Stop",
    "移动(快捷键:1)": "Move (Shortcut: 1)",
    "旋转(快捷键:2)": "Rotate (Shortcut: 2)",
    "缩放(快捷键:3)": "Scale (Shortcut: 3)",
    "相机移动(快捷键:4)": "Camera Move (Shortcut: 4)",
    "相机旋转(快捷键:5)": "Camera Rotate (Shortcut: 5)",
    "相机缩放(快捷键:6)": "Camera Zoom (Shortcut: 6)",
    "测距离": "Measure Distance",
    "测角度": "Measure Angle",
    "显示物理(F4)": "Show Physics (F4)",
    "枢轴点:中位点": "Pivot: Median Point",
    "枢轴点:各自中心": "Pivot: Individual Origins",
    "枢轴点:包围盒中心": "Pivot: Bounding Box Center",
    "枢轴点:激活的物体": "Pivot: Active Actor",
    "各自中心": "Individual Origins",
    "包围盒中心": "Bounding Box Center",
    "中位点": "Median Point",
    "激活的物体": "Active Actor",
    "仿真时可用": "Available During Simulation",
    "递归显示": "Show Recursively",
    "仿真时无法缩放物体": "Objects cannot be scaled during simulation",
    "仿真时不可用": "Unavailable During Simulation",
    "抓取(F3)": "Grab (F3)",
    "搜索实体...": "Search entities...",
    "显示变换": "Show Transform",
    "没有选中任何对象": "No object selected",
    "变换": "Transform",
    "网格": "Mesh",
    "方向光源": "Directional Light",
    "区域光源": "Area Light",
    "材质": "Material",
    "碰撞体": "Geometry",
    "刚体": "Rigid Body",
    "肌腱": "Tendon",
    "关节": "Joint",
    "标记点": "Site",
    "执行器": "Actuator",
    "传感器": "Sensor",
    "未加载": "Not Loaded",
    "自定义": "Custom",
    "钢铁": "Steel",
    "铝合金": "Aluminum Alloy",
    "木头": "Wood",
    "塑料": "Plastic",
    "橡胶": "Rubber",
    "石头": "Stone",
    "玻璃": "Glass",
    "冰": "Ice",
    "泡沫": "Foam",
    "选择纹理": "Select Texture",
    "搜索纹理...": "Search textures...",
    "清除": "Clear",
    "共 {total} 个纹理": "{total} textures",
    "显示 {count} / {total} 个纹理": "Showing {count} / {total} textures",
    "选择机器人:": "Select robot:",
    "选择机器人后点击「查看 XML」...": 'Select a robot, then click "View XML"...',
    "查看 XML": "View XML",
    "加载中...": "Loading...",
    "刷新 XML": "Refresh XML",
    "生成 XML": "Generate XML",
    "MuJoCo XML 查看器": "MuJoCo XML Viewer",
    "（场景中无 AssetActor）": "(No AssetActor in the scene)",
    "获取XML失败": "Failed to retrieve XML",
    "获取失败": "Retrieval Failed",
    "无法获取 XML：\n{error}": "Unable to retrieve XML:\n{error}",
    "未知错误": "Unknown error",
    "启动仿真引擎失败": "Failed to start the simulation engine",
    "引擎返回错误（status={status}）：{error}": "Engine error (status={status}): {error}",
    "复制path": "Copy Path",
    "添加组": "Add Group",
    "重命名": "Rename",
    "递归展开": "Expand Recursively",
    "递归折叠": "Collapse Recursively",
    "重命名关节": "Rename Joint",
    "当前名称: {name}": "Current Name: {name}",
    "确认": "Confirm",
    "名称不能为空。": "Name cannot be empty.",
    "名称只能包含ASCII字符。": "Name may only contain ASCII characters.",
    "名称只能包含字母、数字和下划线，且不能以数字开头。": (
        "Name may only contain letters, numbers, and underscores, and cannot start with a number."
    ),
    "关节名称 '{name}' 已存在，无法使用重复名称。": (
        "Joint name '{name}' already exists. Duplicate names are not allowed."
    ),
    "包含:": "Include:",
    "输入要包含的文本...": "Text to include...",
    "排除:": "Exclude:",
    "输入要排除的文本...": "Text to exclude...",
    "渲染缩略图": "Render Thumbnails",
    "渲染资产缩略图": "Render asset thumbnails",
    "打开资产库": "Open Asset Store",
    "在浏览器中打开资产库": "Open the Asset Store in your browser",
    "正在加载资产缩略图...": "Loading asset thumbnails...",
    "渲染中...": "Rendering...",
    "全部显示": "Show All",
    "DataLink 认证": "DataLink Authentication",
    "DataLink 用户认证": "DataLink User Authentication",
    "初始化中...": "Initializing...",
    "请在浏览器中完成登录。\n如果浏览器没有自动打开，请检查浏览器设置。": (
        "Please complete login in your browser.\n"
        "If the browser did not open automatically, check your browser settings."
    ),
    "关闭": "Close",
    "浏览器未正常打开": "Browser Did Not Open",
    "不建议使用 root 用户": "Running as root is not recommended",
    "等待浏览器认证已超过 60 秒，浏览器可能没有正常弹出，或认证页没有成功打开。\n\n": (
        "Browser authentication has been waiting for over 60 seconds. The browser may "
        "not have opened, or the authentication page may not have loaded.\n\n"
    ),
    "建议尝试：\n": "Try the following:\n",
    "1. 检查默认浏览器是否可正常启动。\n": "1. Check that your default browser can launch normally.\n",
    "2. 检查是否被弹窗拦截、远程桌面会话限制或系统安全策略阻止。\n": (
        "2. Check whether pop-up blocking, remote desktop restrictions, or system security policies blocked it.\n"
    ),
    "3. 复制下面地址到浏览器中手动打开后继续登录：\n": (
        "3. Copy this address into your browser to open it manually, then continue signing in:\n"
    ),
    "检测到当前使用 root 用户运行 OrcaLab。\n\n": "OrcaLab is currently running as the root user.\n\n",
    "不建议使用 root 用户启动 OrcaLab，这可能导致浏览器沙箱报错，认证页面无法正常打开。\n": (
        "Running OrcaLab as root is not recommended. It may trigger browser sandbox "
        "errors and prevent the authentication page from opening correctly.\n"
    ),
    "建议切换到普通用户后重新启动。": "Switch to a regular user and restart OrcaLab.",
    "认证成功: {username}": "Authentication succeeded: {username}",
    "认证失败或超时": "Authentication failed or timed out",
    "认证出错: {error}": "Authentication error: {error}",
    "正在获取认证 nonce...": "Requesting an authentication nonce...",
    "获取 nonce 失败": "Failed to retrieve the nonce",
    "正在打开浏览器进行认证...": "Opening your browser for authentication...",
    "无法打开浏览器": "Unable to open the browser",
    "请在浏览器中完成认证...": "Complete authentication in your browser...",
    "等待浏览器认证超过 60 秒，请检查浏览器后重试": (
        "Browser authentication has been waiting for over 60 seconds. "
        "Check your browser and try again."
    ),
    "资产包同步": "Asset Package Sync",
    "正在同步资产包...": "Syncing asset packages...",
    "元数据同步": "Metadata Sync",
    "正在准备同步元数据... (待更新 {total} 个包)": "Preparing metadata sync... ({total} packages to update)",
    "正在获取远端元数据列表...": "Fetching remote metadata list...",
    "正在扫描远端元数据... ({count}/{total})": "Scanning remote metadata... ({count}/{total})",
    "元数据已是最新，无需同步": "Metadata is up to date. No sync needed.",
    "元数据同步完成 (更新 {count}/{total} 个包)": "Metadata sync complete ({count}/{total} packages updated)",
    "准备同步...": "Preparing sync...",
    "停止同步": "Stop Sync",
    "离线启动": "Start Offline",
    "继续": "Continue",
    "删除本地": "Delete Local",
    "已是最新": "Up to Date",
    "已最新": "Up to Date",
    "待删除": "Pending Delete",
    "待下载": "Pending Download",
    "下载中...": "Downloading...",
    "下载完成": "Download Complete",
    "下载失败": "Download Failed",
    "已下线": "Offline",
    "不兼容": "Incompatible",
    "云端已删除": "Deleted in Cloud",
    "文件下载不完整": "Incomplete Download",
    "无资产包": "No asset packages",
    "总计: {total} 个资产包 | {stats_text}": "Total: {total} asset packages | {stats_text}",
    "元数据同步准备中: 待更新 {total} 个包": "Metadata sync preparing: {total} packages to update",
    "元数据同步进度: 正在获取远端列表...": "Metadata sync: fetching remote list...",
    "元数据同步进度: 已扫描 {count}/{total}": "Metadata sync: scanned {count}/{total}",
    "元数据同步进度: 正在扫描...": "Metadata sync: scanning...",
    "元数据同步完成: 无需更新": "Metadata sync complete: no updates needed",
    "元数据同步完成: {count}/{total}": "Metadata sync complete: {count}/{total}",
    "同步完成！用时 {elapsed:.1f} 秒": "Sync complete in {elapsed:.1f} seconds",
    "同步失败：{message}": "Sync failed: {message}",
    "同步失败": "Sync failed",
    "继续 ({seconds})": "Continue ({seconds})",
    "同步尚未完成，是否停止同步？": "Sync is not complete. Stop syncing?",
    "退出程序：结束 OrcaLab\n离线继续：使用本地已有资产包启动": (
        "Exit: close OrcaLab\nContinue offline: start with existing local asset packages"
    ),
    "继续同步": "Continue Sync",
    "离线继续": "Continue Offline",
    "退出程序": "Exit OrcaLab",
    "认证失败": "Authentication Failed",
    "DataLink 认证失败或已取消。": "DataLink authentication failed or was canceled.",
    "连接资产库失败": "Failed to Connect to Asset Store",
    "无法连接到资产服务器，请检查网络连接。": "Unable to connect to the asset server. Check your network connection.",
    "重新认证失败": "Re-authentication Failed",
    "DataLink 重新认证失败。": "DataLink re-authentication failed.",
    "Token 已过期": "Token Expired",
    "访问令牌已过期，请重新登录。": "The access token has expired. Please sign in again.",
    "资产同步失败": "Asset Sync Failed",
    "资产同步过程中发生错误。": "An error occurred during asset sync.",
    "是否以离线模式继续启动？\n\n点击「是」使用现有资产包继续启动\n点击「否」退出程序": (
        "Continue startup in offline mode?\n\nClick Yes to continue with existing asset packages.\nClick No to exit."
    ),
    "同步过程中无法连接到资产服务器，请检查网络连接。": (
        "The connection to the asset server was lost during synchronization. Check your network connection."
    ),
    "连接资产库失败，进入离线模式": ("Failed to connect to the Asset Store; continuing in offline mode"),
    "用户已取消": "Canceled by user",
    "选择仿真程序": "Select Simulation Program",
    "选择要启动的仿真程序": "Select the simulation program to launch",
    "仿真程序": "Simulation Program",
    "其他选项": "Other Options",
    "无仿真程序（手动启动）": "No simulation program (manual launch)",
    "不启动任何仿真程序，用户需要手动启动": "Do not launch a simulation program; you will start it manually",
    "程序详情": "Program Details",
    "启动": "Launch",
    "未配置仿真程序": "No simulation programs configured",
    "将不启动任何仿真程序。\n用户需要手动启动仿真程序并通过其他方式连接到OrcaLab。": (
        "No simulation program will be launched.\n"
        "You need to start the simulation program manually and connect it to OrcaLab "
        "another way."
    ),
    "名称: {name}\n": "Name: {name}\n",
    "命令: {command}\n": "Command: {command}\n",
    "参数: {args}\n": "Arguments: {args}\n",
    "描述: {description}": "Description: {description}",
    "程序名称: {name}": "Program Name: {name}",
    "显示名称: {name}": "Display Name: {name}",
    "执行命令: {command}": "Command: {command}",
    "命令行参数: {args}": "Command-line Arguments: {args}",
    "启动物理仿真循环": "Start the physics simulation loop",
    "用户体验改进计划": "User Experience Improvement Program",
    (
        "允许 OrcaLab 收集匿名使用数据以优化产品性能与用户体验？我们不会收集代码内容、"
        "文件路径或个人身份信息。所有数据均经脱敏处理并遵循"
        '<a href="https://datalink.orca3d.cn/privacy">《隐私政策》</a>进行存储。'
    ): (
        "Allow OrcaLab to collect anonymous usage data to improve product performance and "
        "user experience? We do not collect code content, file paths, or personally "
        "identifiable information. All data is anonymized and stored according to the "
        '<a href="https://datalink.orca3d.cn/privacy">Privacy Policy</a>.'
    ),
    "同意参与": "Join",
    "暂不参与": "Not Now",
    "GPU 驱动异常": "GPU Driver Issue",
    "未检测到 GPU 硬件，OrcaLab 无法启动。": "No GPU hardware was detected. OrcaLab cannot start.",
    "GPU 驱动未安装或不可用，OrcaLab 无法正常启动。": (
        "The GPU driver is not installed or unavailable. OrcaLab cannot start normally."
    ),
    (
        "未检测到任何 GPU 硬件。\n\nOrcaLab 需要独立显卡才能运行。请确认：\n"
        "1. 您的电脑已安装独立显卡\n"
        "2. 显卡已正确插入 PCIe 插槽\n"
        "3. 显示器已连接到独立显卡的输出接口\n\n"
        "最低 GPU 要求：NVIDIA RTX 3060 或同等性能显卡"
    ): (
        "No GPU hardware was detected.\n\n"
        "OrcaLab requires a dedicated graphics card. Verify that:\n"
        "1. A dedicated graphics card is installed\n"
        "2. The graphics card is seated correctly in its PCIe slot\n"
        "3. The monitor is connected to an output on the dedicated graphics card\n\n"
        "Minimum GPU requirement: NVIDIA RTX 3060 or equivalent"
    ),
    "检测到 GPU 硬件但驱动未安装或不可用：\n": (
        "GPU hardware was detected, but its driver is not installed or is unavailable:\n"
    ),
    "  检测工具: {tool}": "  Detection tool: {tool}",
    "  驱动状态: {status}": "  Driver status: {status}",
    "  安装方式 (Ubuntu): {instructions}": ("  Installation instructions (Ubuntu): {instructions}"),
    "  通用安装: {instructions}": "  General installation: {instructions}",
    "  驱动下载: {url}": "  Driver download: {url}",
    "  安装后验证: {command}": "  Verify after installation: {command}",
    "安装驱动后请重启电脑，然后重新启动 OrcaLab。": (
        "After installing the driver, restart your computer and then restart OrcaLab."
    ),
    "未检测到 GPU 设备": "No GPU devices detected",
    "厂商: {vendor}": "Vendor: {vendor}",
    "设备名: {device}": "Device: {device}",
    "PCI 地址: {address}": "PCI address: {address}",
    "驱动状态: {status}": "Driver status: {status}",
    "驱动版本: {version}": "Driver version: {version}",
    "检测工具: {tool}": "Detection tool: {tool}",
    "显存: {memory} MB": "Video memory: {memory} MB",
    "正常": "Working",
    "未安装": "Not Installed",
    "异常": "Error",
    "未知": "Unknown",
    "OrcaLab 需要独立显卡才能运行。\n\n请确认已安装独立显卡并正确连接，然后重新启动 OrcaLab。": (
        "OrcaLab requires a dedicated graphics card.\n\n"
        "Make sure a dedicated graphics card is installed and connected correctly, then "
        "restart OrcaLab."
    ),
    "继续启动（可能无法正常渲染）": "Continue Startup (Rendering May Fail)",
    "sudo apt install nvidia-driver-535\n或访问官网下载 .run 安装包": (
        "sudo apt install nvidia-driver-535\nor download the .run installer from NVIDIA's website"
    ),
    "访问 NVIDIA 官网下载对应驱动": "Download the appropriate driver from NVIDIA's website",
    "sudo apt install amdgpu-pro-install\n或安装 ROCm: https://rocm.docs.amd.com/": (
        "sudo apt install amdgpu-pro-install\nor install ROCm: https://rocm.docs.amd.com/"
    ),
    "访问 AMD 官网下载对应驱动": "Download the appropriate driver from AMD's website",
    "amd-smi 或 rocm-smi": "amd-smi or rocm-smi",
    "sudo apt install intel-media-va-driver\n或安装 Compute Runtime: https://github.com/intel/compute-runtime": (
        "sudo apt install intel-media-va-driver\nor install Compute Runtime: https://github.com/intel/compute-runtime"
    ),
    "访问 Intel 官网下载对应驱动": "Download the appropriate driver from Intel's website",
    "intel_gpu_top 或 xpu-smi": "intel_gpu_top or xpu-smi",
    "xpu-smi 或 intel_gpu_top": "xpu-smi or intel_gpu_top",
    " 或 ": " or ",
    "摩尔线程": "Moore Threads",
    "参考摩尔线程官方文档安装 MTGPU 驱动": (
        "Follow the official Moore Threads documentation to install the MTGPU driver"
    ),
    "访问摩尔线程官网下载驱动": "Download the driver from the Moore Threads website",
    "瀚博": "Corerise",
    "参考瀚博官方文档安装 Ventus 驱动": ("Follow the official Corerise documentation to install the Ventus driver"),
    "访问瀚博官网下载驱动": "Download the driver from the Corerise website",
    "天数智芯": "Iluvatar",
    "参考天数智芯官方文档安装驱动": ("Follow the official Iluvatar documentation to install the driver"),
    "访问天数智芯官网下载驱动": "Download the driver from the Iluvatar website",
    "沐曦": "MetaX",
    "参考沐曦官方文档安装驱动": ("Follow the official MetaX documentation to install the driver"),
    "访问沐曦官网下载驱动": "Download the driver from the MetaX website",
    "未知厂商": "Unknown Vendor",
    "请联系显卡厂商获取驱动": "Contact the graphics card vendor to obtain a driver",
    "OrcaLab 安装进度": "OrcaLab Installation Progress",
    "准备安装...": "Preparing installation...",
    "正在准备安装...": "Preparing installation...",
    "使用本地开发路径...": "Using local development path...",
    "本地路径: {path}": "Local path: {path}",
    "检测到版本: {version}": "Detected version: {version}",
    "正在下载 python-project...": "Downloading python-project...",
    "下载完成: {name}": "Download complete: {name}",
    "开始下载: {url}": "Starting download: {url}",
    "已下载: {size:.1f}MB": "Downloaded: {size:.1f} MB",
    "正在校验文件完整性...": "Verifying file integrity...",
    "SHA256 mismatch! 文件下载不完整，请重新安装\nexpected: {expected}\nactual:   {actual}": (
        "SHA256 mismatch! The download is incomplete; reinstall the package.\nexpected: {expected}\nactual:   {actual}"
    ),
    "SHA256 校验通过": "SHA256 verification passed",
    "正在解压 python-project...": "Extracting python-project...",
    "解压: {member} ({current}/{total})": "Extracting: {member} ({current}/{total})",
    "开始解压到: {path}": "Starting extraction to: {path}",
    "解压完成": "Extraction complete",
    "正在安装 Python 包...": "Installing Python package...",
    "运行 pip install -e ...": "Running pip install -e ...",
    "安装可编辑包: {path}": "Installing editable package: {path}",
    "包安装完成": "Package installation complete",
    "检测到 {count} 个 pak 文件需要下载": "Detected {count} pak files to download",
    "pak 文件已存在，跳过: {filename}": "pak file already exists; skipping: {filename}",
    "正在下载 pak 文件 ({current}/{total})...": ("Downloading pak file ({current}/{total})..."),
    "开始下载 pak 文件: {filename}": "Starting pak file download: {filename}",
    "pak 文件下载完成: {filename}": "pak file download complete: {filename}",
    "pak 文件下载失败: {filename}": "pak file download failed: {filename}",
    "优化程序集...": "Warming up the engine...",
    "优化程序集, 提高响应速度": "Warming up the engine for faster response times.",
    "安装完成！": "Installation Complete!",
    "请重新运行 OrcaLab": "Restart OrcaLab",
    "所有安装步骤已完成": "All installation steps are complete",
    "错误: {error}": "Error: {error}",
    "下载资源时无法连接代理服务器。": ("Unable to connect to the proxy server while downloading resources."),
    "请检查系统或终端环境变量中的代理配置（如 HTTP_PROXY、HTTPS_PROXY）。": (
        "Check the proxy settings in your system or terminal environment variables, such as HTTP_PROXY and HTTPS_PROXY."
    ),
    "检测到当前代理指向本机地址，可能是代理软件未启动，或端口配置不正确。": (
        "The current proxy points to a local address. The proxy application may not be "
        "running, or its port may be configured incorrectly."
    ),
    "如果当前网络不需要代理，请关闭代理后重试。": (
        "If this network does not require a proxy, disable the proxy and try again."
    ),
    "下载资源时 HTTPS 证书校验失败。": ("HTTPS certificate verification failed while downloading resources."),
    "请检查系统时间是否正确、网络是否经过 HTTPS 代理，或当前系统证书是否完整。": (
        "Check that the system time is correct, whether the network uses an HTTPS proxy, "
        "and whether the system certificate store is complete."
    ),
    "下载资源超时，当前网络可能较慢或连接不稳定。": (
        "The resource download timed out. The network may be slow or unstable."
    ),
    "请确认可以访问网络后重试，必要时切换网络或稍后再试。": (
        "Verify network access and try again. Switch networks or try again later if needed."
    ),
    "下载地址不存在或文件已被移除。": ("The download address does not exist or the file has been removed."),
    "下载地址无访问权限，可能是权限策略或鉴权配置有误。": (
        "Access to the download address was denied. The permission policy or authentication "
        "configuration may be incorrect."
    ),
    "下载服务器暂时不可用，请稍后重试。": ("The download server is temporarily unavailable. Try again later."),
    "下载服务器返回异常状态码。": "The download server returned an unexpected status code.",
    "域名解析失败，请检查 DNS 或当前网络是否可以正常访问网络。": (
        "Domain name resolution failed. Check DNS settings and network access."
    ),
    "网络连接失败，目标地址不可达或对应端口未开启。": (
        "The network connection failed. The destination is unreachable or its port is not open."
    ),
    "建立网络连接失败，请检查网络、代理或防火墙设置。": (
        "Unable to establish a network connection. Check network, proxy, and firewall settings."
    ),
    "下载资源时发生网络错误，请检查网络连接和代理配置。": (
        "A network error occurred while downloading resources. Check the network connection and proxy settings."
    ),
    "安装过程中出现错误，请根据下方信息排查。": (
        "An error occurred during installation. Use the details below to troubleshoot it."
    ),
    "原始错误: {error}": "Original error: {error}",
    "安装完成": "Installation Complete",
    "orcalab初始化完成, 请重新运行orcalab": "OrcaLab initialization is complete. Please restart OrcaLab.",
    "安装失败": "Installation Failed",
    "源文件sha256: {source}\n下载文件sha256: {downloaded}": (
        "Source file SHA-256: {source}\nDownloaded file SHA-256: {downloaded}"
    ),
    "pak 下载不完整, 请重新启动 orcalab": ("The pak download is incomplete. Restart OrcaLab."),
    "清空": "Clear",
    "就绪": "Ready",
    "启动失败": "Failed to Start",
    "已停止": "Stopped",
    "运行中 (PID: {pid})": "Running (PID: {pid})",
    "启动进程: {command}\n": "Starting process: {command}\n",
    "工作目录: {working_dir}\n": "Working directory: {working_dir}\n",
    "启动进程失败: {error}\n": "Failed to start process: {error}\n",
    "正在停止进程...\n": "Stopping process...\n",
    "进程已强制终止\n": "Process was forcibly terminated\n",
    "进程已正常终止\n": "Process terminated normally\n",
    "停止进程时出错: {error}\n": "Error stopping process: {error}\n",
    "\n[输入失败: 进程已关闭]\n": "\n[Input failed: process is closed]\n",
    "\n进程退出，返回码: {return_code}\n": ("\nProcess exited with return code: {return_code}\n"),
    "读取输出时出错: {error}\n": "Error reading process output: {error}\n",
    "输出已清空\n": "Output cleared\n",
    "已复制到剪贴板": "Copied to clipboard",
    "退出应用": "Exit Application",
    "是否退出 OrcaLab？": "Exit OrcaLab?",
    "按Esc键退出": "Press Esc to exit",
    "检测到正在运行的 OrcaLab 进程": "Running OrcaLab Process Detected",
    "当前系统上已存在正在运行的 OrcaLab 实例。": ("An OrcaLab instance is already running on this system."),
    (
        "OrcaLab 不支持在同一台电脑同时运行多个实例。\n\n"
        '选择"终止并继续"将尝试结束所有已发现的 OrcaLab 进程后再继续启动。\n'
        '选择"退出"将直接退出当前启动。\n\n'
        "若 5 秒内未操作，将自动终止已有进程并继续启动。"
    ): (
        "OrcaLab does not support running multiple instances on the same computer.\n\n"
        'Select "Terminate and Continue" to attempt to stop all detected OrcaLab '
        "processes before continuing startup.\n"
        'Select "Exit" to cancel this startup.\n\n'
        "If you do not respond within 5 seconds, the existing processes will be "
        "terminated automatically and startup will continue."
    ),
    "未获取到进程信息": "No process information is available",
    "终止并继续": "Terminate and Continue",
    "终止并继续（{seconds}s）": "Terminate and Continue ({seconds}s)",
    "无法终止所有 OrcaLab 进程": "Unable to Terminate All OrcaLab Processes",
    "部分 OrcaLab 进程无法自动终止。": ("Some OrcaLab processes could not be terminated automatically."),
    "请手动结束以下进程后重新启动 OrcaLab:\n{pids}": (
        "Manually stop the following processes, then restart OrcaLab:\n{pids}"
    ),
    "OrcaLab 不支持在同一台电脑同时运行多个实例。\n\n请根据详细信息关闭已有实例后再继续启动。\n": (
        "OrcaLab does not support running multiple instances on the same computer.\n\n"
        "Use the details below to close the existing instance before continuing startup.\n"
    ),
    "外部程序 {program_name} 启动失败，请检查命令配置或日志输出。": (
        "External program {program_name} failed to start. Check its command configuration or log output."
    ),
    "已切换到运行模式，等待外部程序连接...": (
        "Switched to runtime mode; waiting for the external program to connect..."
    ),
    "模拟地址: {address}": "Simulation address: {address}",
    "请手动启动外部程序并连接到上述地址": ("Start the external program manually and connect it to the address above"),
    "注意：当前运行的是虚拟等待进程，可以手动停止": (
        "Note: a placeholder waiting process is currently running and can be stopped manually"
    ),
    "启动进程: {command}": "Starting process: {command}",
    "工作目录: {path}": "Working directory: {path}",
    "启动进程失败: {error}": "Failed to start process: {error}",
    "pywinpty 未安装，请运行: pip install pywinpty": ("pywinpty is not installed. Run: pip install pywinpty"),
    "读取输出时出错: {error}": "Error reading process output: {error}",
    "进程退出，返回码: {return_code}": "Process exited with return code: {return_code}",
    "正在停止进程...": "Stopping process...",
    "进程已终止": "Process terminated",
    "进程已正常终止": "Process terminated normally",
    "进程已强制终止": "Process was forcibly terminated",
}
