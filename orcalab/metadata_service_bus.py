from typing import Any, Mapping, List

from orcalab.event_bus import create_event_bus


AssetMetadata = Mapping[str, Any]
AssetMap = Mapping[str, AssetMetadata]


class MetadataServiceRequest:

    def reload_metadata(self) -> None:
        pass

    def get_asset_info(self, asset_path: str, output: list[AssetMetadata] = None) -> AssetMetadata:
        pass

    def get_asset_map(self, output: List[AssetMap] = None) -> AssetMap:
        pass
    
    def update_asset_info(self, asset_path: str, asset_info: AssetMetadata) -> None:
        pass

MetadataServiceRequestBus = create_event_bus(MetadataServiceRequest)



