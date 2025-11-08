from orcalab.metadata_service_bus import AssetMetadata

class AssetInfo:
    def __init__(self):
        self.name: str = ""
        self.path: str = ""
        self.metadata: AssetMetadata | None = None
        self.apng_player = None  # ApngPlayer for APNG support