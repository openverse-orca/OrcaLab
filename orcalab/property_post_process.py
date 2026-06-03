import asyncio
import logging
from dataclasses import dataclass

from orcalab.actor_property import ActorPropertyKey, ActorProperty
from orcalab.local_scene import LocalScene
from orcalab.remote_scene import RemoteScene
from orcalab.scene_edit_bus import SceneEditNotificationBus

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

    def find_rules(self, component_type: str, property_name: str) -> list[PostProcessRule]:
        results = []
        for rule in self._rules:
            if rule.trigger_property != property_name:
                continue
            if rule.component_type != component_type:
                continue
            results.append(rule)
        return results


class PostProcessDispatcher:
    def __init__(self, local_scene: LocalScene, remote_scene: RemoteScene):
        self._local_scene = local_scene
        self._remote_scene = remote_scene
        self._timers: dict[tuple, asyncio.TimerHandle] = {}

    def on_property_set(self, property_key: ActorPropertyKey) -> None:
        rules = PostProcessRegistry.instance().find_rules(
            property_key.component_type, property_key.property_name
        )
        if not rules:
            return

        timer_key = (
            property_key.actor_path,
            property_key.entity_id,
            property_key.component_type,
            property_key.property_name,
        )

        old_handle = self._timers.pop(timer_key, None)
        if old_handle:
            old_handle.cancel()

        delay = max(rule.delay_ms for rule in rules) / 1000.0

        loop = asyncio.get_event_loop()
        handle = loop.call_later(delay, self._on_timer_fire, timer_key, rules, property_key)
        self._timers[timer_key] = handle

    def cancel_all(self) -> None:
        for handle in self._timers.values():
            handle.cancel()
        self._timers.clear()

    def _on_timer_fire(
        self,
        timer_key: tuple,
        rules: list[PostProcessRule],
        trigger_key: ActorPropertyKey,
    ) -> None:
        self._timers.pop(timer_key, None)
        asyncio.create_task(self._execute_rules(rules, trigger_key))

    async def _execute_rules(self, rules: list[PostProcessRule], trigger_key: ActorPropertyKey) -> None:
        all_read_props: list[str] = []
        for rule in rules:
            if isinstance(rule.action, ReadPropertiesAction):
                for prop_name in rule.action.read_properties:
                    if prop_name not in all_read_props:
                        all_read_props.append(prop_name)

        if not all_read_props:
            return

        await self._execute_read_action(trigger_key, all_read_props)

    async def _execute_read_action(self, trigger_key: ActorPropertyKey, read_properties: list[str]) -> None:
        try:
            actor, group, _ = self._local_scene.parse_property_key(trigger_key)
        except Exception as e:
            logger.warning("PostProcess: failed to parse trigger key: %s", e)
            return

        keys: list[ActorPropertyKey] = []
        props: list[ActorProperty] = []

        def _collect_from_properties(prop_list):
            for prop in prop_list:
                matched_read_name = None
                for read_name in read_properties:
                    if prop.name() == read_name or prop.name().startswith(read_name + "."):
                        matched_read_name = read_name
                        break
                if matched_read_name is None:
                    continue
                if prop.name() in [k.property_name for k in keys]:
                    continue
                key = ActorPropertyKey(
                    trigger_key.actor_path,
                    trigger_key.group_prefix,
                    prop.name(),
                    prop.value_type(),
                    entity_id=trigger_key.entity_id,
                    component_type=trigger_key.component_type,
                )
                keys.append(key)
                props.append(prop)

        def _collect_from_tree(nodes):
            for node in nodes:
                _collect_from_properties(node.properties)
                _collect_from_tree(node.children)

        _collect_from_properties(group.properties)
        _collect_from_tree(group.tree_data)

        if not keys:
            return

        try:
            values = await self._remote_scene.get_properties(keys)
        except Exception as e:
            logger.warning("PostProcess: failed to read properties: %s", e)
            return

        for prop, value in zip(props, values):
            prop.set_value(value)

        bus = SceneEditNotificationBus()
        await bus.on_properties_changed(keys, values, source="post_process")
