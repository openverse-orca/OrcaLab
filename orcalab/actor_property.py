from enum import Enum
from dataclasses import dataclass, field
from typing import Any, List

from orcalab.entity_path import EntityPath
from orcalab.path import Path


class ActorPropertyType(Enum):
    UNKNOWN = 0
    BOOL = 1
    INTEGER = 2
    FLOAT = 3
    STRING = 4
    ENUM = 5
    ASSET = 6


class ValueWrapper:
    """A simple wrapper to hold a value by reference."""

    def __init__(self, value):
        self.value = value


class ActorProperty:
    def __init__(
        self,
        name: str,
        display_name: str | None,
        type: ActorPropertyType,
        value: Any,
        original_value: Any,
    ):
        self._name = name
        self._display_name: str = display_name if display_name is not None else name
        self._type = type
        self._value = ValueWrapper(value)
        self._base_value = ValueWrapper(value)
        self._read_only = False
        self._editor_hint = ""
        self._enum_values: List[str] = []
        self._post_read_fields: List[str] = []
        self._post_read_delay_ms: int = 0
        self._sub_name: str = ""
        self._parent_struct_name: str = ""
        self._struct_display_name: str = ""
        self._has_range = False
        self._range_min = 0.0
        self._range_max = 1.0
        self._is_slide = False
        self._visible = True

    def name(self) -> str:
        return self._name

    def display_name(self) -> str:
        return self._display_name

    def value_type(self) -> ActorPropertyType:
        return self._type

    def value(self):
        return self._value.value

    def set_value(self, value):
        self._set_value(self._value, value)

    def base_value(self):
        return self._base_value.value

    def set_base_value(self, value):
        self._set_value(self._base_value, value)

    def is_modified(self) -> bool:
        if self._type == ActorPropertyType.FLOAT:
            return abs(self.value() - self.base_value()) > 1e-6

        return self.value() != self.base_value()

    def _set_value(self, target, value):
        match self._type:
            case ActorPropertyType.BOOL:
                if not isinstance(value, bool):
                    raise ValueError("Value must be a boolean")
                target.value = value
            case ActorPropertyType.INTEGER:
                if isinstance(value, int):
                    target.value = value
                elif isinstance(value, float) and value.is_integer():
                    target.value = int(value)
                else:
                    raise ValueError("Value must be an integer")
            case ActorPropertyType.FLOAT:
                if not isinstance(value, float):
                    raise ValueError("Value must be a float")
                target.value = value
            case ActorPropertyType.STRING:
                if not isinstance(value, str):
                    raise ValueError("Value must be a string")
                target.value = value
            case ActorPropertyType.ENUM:
                if not isinstance(value, str):
                    raise ValueError("Value must be a string for enum")
                target.value = value
            case ActorPropertyType.ASSET:
                if not isinstance(value, str):
                    raise ValueError("Value must be a string for asset")
                target.value = value
            case _:
                raise NotImplementedError("Unsupported property type")

    def is_read_only(self) -> bool:
        return self._read_only

    def set_read_only(self, read_only: bool):
        self._read_only = read_only

    def editor_hint(self) -> str:
        return self._editor_hint

    def set_editor_hint(self, hint: str):
        self._editor_hint = hint

    def enum_values(self) -> List[str]:
        return self._enum_values

    def set_enum_values(self, values: List[str]):
        self._enum_values = values

    def post_read_fields(self) -> List[str]:
        return self._post_read_fields

    def set_post_read_fields(self, fields: List[str]):
        self._post_read_fields = fields

    def post_read_delay_ms(self) -> int:
        return self._post_read_delay_ms

    def set_post_read_delay_ms(self, delay_ms: int):
        self._post_read_delay_ms = delay_ms

    def sub_name(self) -> str:
        return self._sub_name

    def set_sub_name(self, sub_name: str):
        self._sub_name = sub_name

    def parent_struct_name(self) -> str:
        return self._parent_struct_name

    def set_parent_struct_name(self, name: str):
        self._parent_struct_name = name

    def struct_display_name(self) -> str:
        return self._struct_display_name

    def set_struct_display_name(self, name: str):
        self._struct_display_name = name

    def has_range(self) -> bool:
        return self._has_range
    
    def range_min(self) -> float:
        return self._range_min
    
    def range_max(self) -> float:
        return self._range_max

    def set_range_min_max(self, range_min: float, range_max: float):
        self._has_range = True
        self._range_min = range_min
        self._range_max = range_max

    def is_slide(self) -> bool:
        return self._is_slide
    
    def set_is_slide(self, is_slide: bool):
        self._is_slide = is_slide

    def is_visible(self) -> bool:
        return self._visible

    def set_visible(self, visible: bool):
        self._visible = visible

@dataclass
class ActorPropertyGroup:
    name: str
    hint: str
    entity_id: int
    entity_path: EntityPath
    component_type_id: str
    component_type_index: int
    properties: List[ActorProperty]

    def set_value(self, name: str, value: Any):
        for prop in self.properties:
            if prop.name() == name:
                prop.set_value(value)
                return


@dataclass
class ActorPropertyKey:
    actor_path: Path
    entity_id: int
    entity_path: EntityPath
    component_type_id: str
    component_type_index: int
    property_name: str
    property_type: ActorPropertyType

    def clone(self) -> "ActorPropertyKey":
        return ActorPropertyKey(
            actor_path=self.actor_path,
            entity_id=self.entity_id,
            entity_path=self.entity_path,
            component_type_id=self.component_type_id,
            component_type_index=self.component_type_index,
            property_name=self.property_name,
            property_type=self.property_type,
        )


@dataclass
class PropertyOverride:
    entity_id: int
    entity_path: EntityPath
    component_type_id: str
    component_type_index: int
    property_name: str
    property_type: ActorPropertyType
    value: Any


@dataclass
class StructPropertyGroup:
    """结构体属性组（树形结构）"""

    name: str
    display_name: str
    properties: List[ActorProperty]
    children: List["StructPropertyGroup"]
    layout: str = "vertical"


@dataclass
class ActorEntities:
    actor_path: Path
    entity_ids: List[int]


@dataclass
class PropertyGetInfo:
    read_only: bool
    value: Any
    base_value: Any


PropertyData = PropertyGetInfo
