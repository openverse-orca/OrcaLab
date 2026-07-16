from attr import dataclass, field

from orcalab.transform import Transform


@dataclass
class CameraDataPNGResult:
    transform: Transform = Transform()
    has_color: bool = False
    has_depth: bool = False
    has_normal: bool = False
    has_object_color: bool = False
