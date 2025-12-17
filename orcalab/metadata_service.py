import json
from orcalab.metadata_service_bus import MetadataServiceRequest, MetadataServiceRequestBus
from typing import List, override
from orcalab.metadata_service_bus import AssetMetadata, AssetMap
from orcalab.project_util import get_cache_folder

class MetadataService(MetadataServiceRequest):

    def __init__(self):
        super().__init__()
        MetadataServiceRequestBus.connect(self)
        self._metadata: AssetMap = {}
        self._asset_map: AssetMap = {}
        cache_folder = get_cache_folder()
        self._metadata_path = cache_folder / "metadata.json"
        self.reload_metadata()

    def destroy(self):
        MetadataServiceRequestBus.disconnect(self)
        self._save_metadata()

    @override
    def reload_metadata(self) -> None:

        if not self._metadata_path.exists():
            return
        with open(self._metadata_path, 'r', encoding='utf-8') as f:
            self._metadata = json.load(f)
        self._build_asset_map()

    @override
    def get_asset_info(self, asset_path: str, output: list[AssetMetadata] = None) -> AssetMetadata:
        if output is not None:
            output.append(self._asset_map.get(asset_path, None))
        return self._asset_map.get(asset_path, None)

    @override
    def get_asset_map(self, output: List[AssetMap] = None) -> AssetMap:
        if output is not None:
            output.append(self._asset_map)
        return self._asset_map

    @override
    def update_asset_info(self, asset_path: str, asset_info: AssetMetadata) -> None:
        self._asset_map[asset_path] = asset_info

    def _build_asset_map(self) -> AssetMap:
        for pak_metadata in self._metadata.values():
            for asset_metadata in pak_metadata['children']:
                asset_path = asset_metadata['assetPath'].removesuffix('.spawnable').lower()
                self._asset_map[asset_path] = asset_metadata

    def _save_metadata(self) -> None:
        new_metadata = {}
        for pak_id, pak_metadata in self._metadata.items():
            new_metadata[pak_id] = {}
            new_metadata[pak_id] = pak_metadata
            new_metadata[pak_id]['children'] = []

        for asset_path, asset_info in self._asset_map.items():
            pkg_id = asset_info['parentPackageId']
            if pkg_id in new_metadata.keys():
                new_metadata[pkg_id]['children'].append(asset_info)
            else:
                new_metadata[pkg_id] = {}
                new_metadata[pkg_id]['children'] = [asset_info]
        self._metadata = new_metadata
        with open(self._metadata_path, 'w', encoding='utf-8') as f:
            json.dump(self._metadata, f, ensure_ascii=False, indent=2)