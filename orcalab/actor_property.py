from enum import Enum
from typing import List

from orcalab.path import Path


class ActorPropertyType(Enum):
    UNKNOWN = 0
    BOOL = 1
    INTEGER = 2
    FLOAT = 3
    STRING = 4


class ValueWrapper:
    """A simple wrapper to hold a value by reference."""

    def __init__(self, value):
        self.value = value


class ActorProperty:
    def __init__(
        self, name: str, display_name: str | None, type: ActorPropertyType, value
    ):
        self._name = name
        self._display_name: str = display_name if display_name is not None else name
        self._type = type
        self._value = ValueWrapper(value)
        self._original_value = ValueWrapper(value)

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

    def original_value(self):
        return self._original_value.value

    def set_original_value(self, value):
        self._set_value(self._original_value, value)

    def is_modified(self) -> bool:
        if self._type == ActorPropertyType.FLOAT:
            return abs(self.value() - self.original_value()) > 1e-6

        return self.value() != self.original_value()

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
            case _:
                raise NotImplementedError("Unsupported property type")


class ActorPropertyGroup:
    def __init__(self, prefix: str, name: str, hint: str):
        self.prefix = prefix
        self.name = name
        self.hint = hint
        self.properties: List[ActorProperty] = []


class ActorPropertyKey:
    def __init__(
        self,
        actor_path: Path,
        group_prefix: str,
        property_name: str,
        property_type: ActorPropertyType,
    ):
        self.actor_path = actor_path
        self.group_prefix = group_prefix
        self.property_name = property_name
        self.property_type = property_type

    def __eq__(self, other):
        if not isinstance(other, ActorPropertyKey):
            return NotImplemented

        return (
            self.actor_path == other.actor_path
            and self.group_prefix == other.group_prefix
            and self.property_name == other.property_name
            and self.property_type == other.property_type
        )

    def __hash__(self):
        return hash(
            (self.actor_path, self.group_prefix, self.property_name, self.property_type)
        )
