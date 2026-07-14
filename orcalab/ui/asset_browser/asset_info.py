from orcalab.metadata_service_bus import AssetMetadata
from orcalab.ui.asset_browser.apng_player import ApngPlayer

class AssetInfo:
    def __init__(self):
        self.name: str = ""
        self.path: str = ""
        self.pak_name: str = ""
        self.metadata: AssetMetadata | None = None
        self.apng_player: ApngPlayer | None = None  # ApngPlayer for APNG support