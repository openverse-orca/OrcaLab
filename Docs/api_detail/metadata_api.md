---
layout: default
title: API Detailed Reference - Metadata API
---

# API Detailed Reference: Metadata API

> **📖 这是什么文档？**  
> 这是 OrcaLab 元数据服务的详细 API 参考，包含资产元数据的查询、更新和管理接口。所有操作都通过 `MetadataServiceRequestBus` 和 `HttpServiceRequestBus` 执行。

> **💡 使用提示**  
> 元数据服务分为两部分：本地元数据（通过 `MetadataServiceRequestBus`）和远程元数据（通过 `HttpServiceRequestBus`）。

---

## 概述

OrcaLab 的元数据系统管理资产的信息，包括：

- **资产基本信息**: 名称、ID、路径等
- **资产包信息**: 资产所属的包
- **图片信息**: 缩略图和预览图 URL
- **订阅信息**: 用户订阅的资产包

元数据分为两个层次：
1. **远程元数据**: 存储在 SimAssets 服务器，通过 HTTP 服务获取
2. **本地元数据**: 缓存在本地 `metadata.json` 文件，通过元数据服务管理

---

## 元数据格式

### AssetMetadata

资产元数据是一个字典（`Mapping[str, Any]`），包含以下字段：

```python
{
    "id": "asset_123",                    # 资产 ID
    "name": "Box",                        # 资产名称
    "assetPath": "Box.spawnable",         # 资产路径（带 .spawnable 后缀）
    "parentPackageId": "package_123",     # 所属资产包 ID
    "pictures": {                         # 图片信息
        "thumbnail": "https://...",       # 缩略图 URL
        "preview": "https://..."          # 预览图 URL
    },
    # ... 其他字段
}
```

### AssetMap

资产映射表是一个字典，键为资产路径（小写，无 `.spawnable` 后缀），值为 `AssetMetadata`：

```python
{
    "box": {
        "id": "asset_123",
        "name": "Box",
        "assetPath": "Box.spawnable",
        ...
    },
    "sphere": {
        "id": "asset_456",
        "name": "Sphere",
        "assetPath": "Sphere.spawnable",
        ...
    }
}
```

---

## 本地元数据 API

### MetadataServiceRequestBus

本地元数据服务请求总线，用于查询和管理本地缓存的元数据。

---

### reload_metadata

重新加载元数据文件。

**方法签名**:
```python
def reload_metadata(self) -> None
```

**说明**:
- 从 `{cache_folder}/metadata.json` 文件重新加载元数据
- 如果文件不存在则直接返回
- 加载后会重建内部 `_asset_map` 映射表

**使用示例**:
```python
from orcalab.metadata_service_bus import MetadataServiceRequestBus

# 重新加载元数据（例如文件被外部更新后）
MetadataServiceRequestBus().reload_metadata()
```

---

### get_asset_info

获取指定资产的元数据信息。

**方法签名**:
```python
def get_asset_info(
    self,
    asset_path: str,
    output: list[AssetMetadata] = None
) -> AssetMetadata
```

**参数**:
- `asset_path`: 资产路径（如 "box" 对应 "Box.spawnable"）
- `output` (可选): 用于接收结果的列表

**返回**:
- `AssetMetadata` 对象，如果不存在则返回 `None`

**说明**:
- 资产路径会自动转换为小写并移除 `.spawnable` 后缀
- 从内部 `_asset_map` 字典中查找
- 使用输出参数获取返回值

**使用示例**:
```python
from orcalab.metadata_service_bus import MetadataServiceRequestBus

# 获取资产信息
output = []
asset_info = MetadataServiceRequestBus().get_asset_info("box", output)

if output:
    info = output[0]
    print(f"资产名称: {info.get('name', 'Unknown')}")
    print(f"资产 ID: {info.get('id', 'Unknown')}")
    print(f"资产路径: {info.get('assetPath', 'Unknown')}")
else:
    print("资产不存在")
```

---

### get_asset_map

获取所有资产的映射表。

**方法签名**:
```python
def get_asset_map(
    self,
    output: List[AssetMap] = None
) -> AssetMap
```

**参数**:
- `output` (可选): 用于接收结果的列表

**返回**:
- `AssetMap` 字典，键为资产路径，值为 `AssetMetadata`

**说明**:
- 返回所有资产的映射表
- 键为资产路径（小写，无 `.spawnable` 后缀）
- 值为资产的元数据信息

**使用示例**:
```python
from orcalab.metadata_service_bus import MetadataServiceRequestBus

# 获取所有资产映射
output = []
asset_map = MetadataServiceRequestBus().get_asset_map(output)

if output:
    asset_map = output[0]
    print(f"共有 {len(asset_map)} 个资产")
    
    # 遍历所有资产
    for asset_path, asset_info in asset_map.items():
        print(f"{asset_path}: {asset_info.get('name', 'Unknown')}")
```

---

### update_asset_info

更新或添加资产信息。

**方法签名**:
```python
def update_asset_info(
    self,
    asset_path: str,
    asset_info: AssetMetadata
) -> None
```

**参数**:
- `asset_path`: 资产路径
- `asset_info`: 资产元数据信息

**说明**:
- 更新或添加资产信息到内部映射表
- 不会立即保存到文件，需要在服务销毁时调用 `_save_metadata`
- 通常由 HTTP 服务同步元数据时调用

**使用示例**:
```python
from orcalab.metadata_service_bus import MetadataServiceRequestBus

# 更新资产信息
asset_info = {
    "id": "asset_123",
    "name": "My Box",
    "assetPath": "MyBox.spawnable",
    "parentPackageId": "package_1",
    "pictures": {
        "thumbnail": "https://example.com/thumb.png",
        "preview": "https://example.com/preview.png"
    }
}

MetadataServiceRequestBus().update_asset_info("mybox", asset_info)
```

---

## 远程元数据 API

### HttpServiceRequestBus

HTTP 服务请求总线，用于与 SimAssets 服务器通信获取元数据。

---

### get_all_metadata

获取所有资产元数据（包括已发布和未发布的）。

**方法签名**:
```python
async def get_all_metadata(self, output: List[str] = None) -> str
```

**参数**:
- `output` (可选): 用于接收结果的列表

**返回**:
- JSON 字符串，包含所有资产的元数据

**说明**:
- 需要在线状态（已登录）
- 返回已发布和未发布的所有资产元数据
- 格式为 JSON 字符串

**使用示例**:
```python
import json
import asyncio
from orcalab.http_service.http_bus import HttpServiceRequestBus

async def main():
    output = []
    metadata_json = await HttpServiceRequestBus().get_all_metadata(output)
    
    if output:
        metadata = json.loads(output[0])
        print(f"共有 {len(metadata)} 个资产包")
        
        # 遍历资产包
        for package in metadata:
            print(f"包: {package.get('name', 'Unknown')}")
            print(f"  ID: {package.get('id', 'Unknown')}")
            print(f"  资产数: {len(package.get('children', []))}")

asyncio.run(main())
```

---

### get_subscription_metadata

获取订阅的资产包元数据。

**方法签名**:
```python
async def get_subscription_metadata(self, output: List[str] = None) -> str
```

**参数**:
- `output` (可选): 用于接收结果的列表

**返回**:
- JSON 字符串，包含订阅的资产包及其子资产元数据

**说明**:
- 需要在线状态（已登录）
- 返回用户订阅的资产包及其包含的所有资产
- 包含资产的图片 URL 信息
- 格式为嵌套的 JSON 结构

**使用示例**:
```python
import json
import asyncio
from orcalab.http_service.http_bus import HttpServiceRequestBus

async def main():
    output = []
    subscription_metadata = await HttpServiceRequestBus().get_subscription_metadata(output)
    
    if output:
        data = json.loads(output[0])
        print(f"订阅了 {len(data)} 个资产包")
        
        # 遍历订阅的资产包
        for package_id, package_info in data.items():
            print(f"\n包: {package_info.get('name', 'Unknown')}")
            print(f"  ID: {package_id}")
            
            # 遍历包中的资产
            children = package_info.get('children', [])
            print(f"  资产数: {len(children)}")
            for asset in children:
                print(f"    - {asset.get('name', 'Unknown')}")
                print(f"      路径: {asset.get('assetPath', 'Unknown')}")

asyncio.run(main())
```

---

### get_subscriptions

获取用户的订阅列表。

**方法签名**:
```python
async def get_subscriptions(self, output: List[str] = None) -> str
```

**参数**:
- `output` (可选): 用于接收结果的列表

**返回**:
- JSON 字符串，包含订阅列表

**说明**:
- 需要在线状态（已登录）
- 返回用户订阅的资产包 ID 列表
- 包含版本和平台信息

**使用示例**:
```python
import json
import asyncio
from orcalab.http_service.http_bus import HttpServiceRequestBus

async def main():
    output = []
    subscriptions_json = await HttpServiceRequestBus().get_subscriptions(output)
    
    if output:
        subscriptions = json.loads(output[0])
        print(f"订阅了 {len(subscriptions.get('subscriptions', []))} 个资产包")
        
        for sub in subscriptions.get('subscriptions', []):
            print(f"  - {sub.get('assetPackageId', 'Unknown')}")

asyncio.run(main())
```

---

### get_image_url

获取资产的图片 URL。

**方法签名**:
```python
async def get_image_url(self, asset_id: str) -> str
```

**参数**:
- `asset_id`: 资产 ID

**返回**:
- JSON 字符串，包含资产的图片 URL 信息

**说明**:
- 需要在线状态（已登录）
- 返回资产的缩略图和预览图 URL

**使用示例**:
```python
import json
import asyncio
from orcalab.http_service.http_bus import HttpServiceRequestBus

async def main():
    asset_id = "asset_123"
    image_url_json = await HttpServiceRequestBus().get_image_url(asset_id)
    
    if image_url_json:
        image_data = json.loads(image_url_json)
        print(f"缩略图: {image_data.get('pictures', {}).get('thumbnail', 'N/A')}")
        print(f"预览图: {image_data.get('pictures', {}).get('preview', 'N/A')}")

asyncio.run(main())
```

---

## 完整使用流程

### 1. 从服务器同步元数据到本地

```python
import json
import asyncio
from orcalab.http_service.http_bus import HttpServiceRequestBus
from orcalab.metadata_service_bus import MetadataServiceRequestBus

async def sync_metadata():
    # 1. 从服务器获取订阅元数据
    output = []
    subscription_metadata = await HttpServiceRequestBus().get_subscription_metadata(output)
    
    if not output:
        print("获取元数据失败")
        return
    
    metadata = json.loads(output[0])
    print(f"从服务器获取了 {len(metadata)} 个资产包")
    
    # 2. 更新到本地元数据服务
    for package_id, package_info in metadata.items():
        # 更新包信息（如果需要）
        # ...
        
        # 更新包中的资产信息
        for asset_info in package_info.get('children', []):
            asset_path = asset_info['assetPath'].removesuffix('.spawnable').lower()
            MetadataServiceRequestBus().update_asset_info(asset_path, asset_info)
    
    print("元数据已同步到本地")

asyncio.run(sync_metadata())
```

### 2. 查询本地元数据

```python
from orcalab.metadata_service_bus import MetadataServiceRequestBus

# 查询单个资产
output = []
asset_info = MetadataServiceRequestBus().get_asset_info("box", output)

if output:
    info = output[0]
    print(f"资产: {info.get('name')}")
    print(f"  ID: {info.get('id')}")
    print(f"  路径: {info.get('assetPath')}")
    print(f"  包 ID: {info.get('parentPackageId')}")

# 查询所有资产
output = []
asset_map = MetadataServiceRequestBus().get_asset_map(output)

if output:
    print(f"\n本地共有 {len(output[0])} 个资产")
    for path, info in output[0].items():
        print(f"  {path}: {info.get('name')}")
```

### 3. 搜索资产

```python
from orcalab.metadata_service_bus import MetadataServiceRequestBus

def search_assets(keyword: str):
    """根据关键词搜索资产"""
    output = []
    asset_map = MetadataServiceRequestBus().get_asset_map(output)
    
    if not output:
        return []
    
    results = []
    keyword_lower = keyword.lower()
    
    for asset_path, asset_info in output[0].items():
        name = asset_info.get('name', '').lower()
        if keyword_lower in name or keyword_lower in asset_path:
            results.append((asset_path, asset_info))
    
    return results

# 使用示例
results = search_assets("box")
for path, info in results:
    print(f"{path}: {info.get('name')}")
```

---

## 元数据文件格式

本地元数据存储在 `{cache_folder}/metadata.json` 文件中：

```json
{
  "package_id_1": {
    "id": "package_id_1",
    "name": "Package Name",
    "children": [
      {
        "id": "asset_id_1",
        "name": "Box",
        "assetPath": "Box.spawnable",
        "parentPackageId": "package_id_1",
        "pictures": {
          "thumbnail": "https://...",
          "preview": "https://..."
        }
      }
    ]
  }
}
```

---

## 注意事项

1. **路径格式**: 资产路径会自动转换为小写并移除 `.spawnable` 后缀
2. **输出参数**: 所有返回值的操作都需要使用输出参数
3. **异步操作**: HTTP 服务的方法都是异步的，需要使用 `await`
4. **在线状态**: HTTP 服务需要在线状态（已登录），离线时会返回 `None`
5. **数据同步**: 本地元数据不会自动同步，需要手动调用同步流程
6. **文件保存**: 元数据在服务销毁时自动保存，不需要手动调用

---

## 错误处理

```python
import asyncio
from orcalab.http_service.http_bus import HttpServiceRequestBus
from orcalab.metadata_service_bus import MetadataServiceRequestBus

async def safe_get_metadata():
    try:
        output = []
        metadata_json = await HttpServiceRequestBus().get_all_metadata(output)
        
        if not output or not output[0]:
            print("获取元数据失败：服务离线或请求失败")
            return None
        
        import json
        return json.loads(output[0])
    except Exception as e:
        print(f"获取元数据异常: {e}")
        return None

async def safe_get_asset_info(asset_path: str):
    try:
        output = []
        asset_info = MetadataServiceRequestBus().get_asset_info(asset_path, output)
        
        if not output:
            print(f"资产 {asset_path} 不存在")
            return None
        
        return output[0]
    except Exception as e:
        print(f"查询资产信息异常: {e}")
        return None

asyncio.run(safe_get_metadata())
```

