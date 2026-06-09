import asyncio
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ReadPropertiesAction:
    read_properties: list[str]


@dataclass
class PostProcessRule:
    trigger_property: str
    component_type: str = ""
    action: ReadPropertiesAction = None
    delay_ms: int = 100


class PostProcessRegistry:
    _instance: "PostProcessRegistry | None" = None

    @classmethod
    def instance(cls) -> "PostProcessRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._rules: list[PostProcessRule] = []

    def register(self, rule: PostProcessRule) -> None:
        self._rules.append(rule)

    def find_rules(
        self, component_type: str, property_name: str
    ) -> list[PostProcessRule]:
        results = []
        for rule in self._rules:
            if rule.trigger_property != property_name:
                continue
            if rule.component_type != component_type:
                continue
            results.append(rule)
        return results
