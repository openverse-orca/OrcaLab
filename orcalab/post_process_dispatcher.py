from typing import List
from orcalab.actor_property import ActorEntities, ActorPropertyGroup, PropertyData
import asyncio
import logging

from orcalab.actor_property import ActorPropertyKey, ActorProperty
from orcalab.local_scene import LocalScene
from orcalab.property_post_process import (
    PostProcessRegistry,
    PostProcessRule,
    ReadPropertiesAction,
)
from orcalab.remote_scene import RemoteScene
from orcalab.scene_edit_bus import SceneEditNotificationBus

logger = logging.getLogger(__name__)


class PostProcessDispatcher:
    def __init__(self, local_scene: LocalScene, remote_scene: RemoteScene):
        self._local_scene = local_scene
        self._remote_scene = remote_scene
        self._timers: dict[tuple, asyncio.TimerHandle] = {}

    def on_property_set(self, property_key: ActorPropertyKey) -> None:
        rules = PostProcessRegistry.instance().find_rules(
            property_key.component_type_id, property_key.property_name
        )
        if not rules:
            return

        timer_key = (
            property_key.actor_path,
            property_key.entity_id,
            property_key.component_type_id,
            property_key.property_name,
        )

        old_handle = self._timers.pop(timer_key, None)
        if old_handle:
            old_handle.cancel()

        delay = max(rule.delay_ms for rule in rules) / 1000.0

        loop = asyncio.get_event_loop()
        handle = loop.call_later(
            delay, self._on_timer_fire, timer_key, rules, property_key
        )
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

    async def _execute_rules(
        self, rules: list[PostProcessRule], trigger_key: ActorPropertyKey
    ) -> None:
        all_read_props: list[str] = []
        for rule in rules:
            if isinstance(rule.action, ReadPropertiesAction):
                for prop_name in rule.action.read_properties:
                    if prop_name not in all_read_props:
                        all_read_props.append(prop_name)

        if not all_read_props:
            return

        await self._execute_read_action(trigger_key, all_read_props)

    async def _execute_read_action(
        self, trigger_key: ActorPropertyKey, read_properties: list[str]
    ) -> None:
        actor, actor_path = self._local_scene.normalize_actor(trigger_key.actor_path)
        entity_id = actor.entity_root.find_entity_id_by_path(trigger_key.entity_path)

        groups_list = await self._remote_scene.get_entity_property_groups(
            ActorEntities(actor_path, [entity_id])
        )
        if not groups_list:
            return

        groups = groups_list[0]
        if not groups:
            return

        trigger_group: ActorPropertyGroup | None = None
        for group in groups:
            if (
                group.component_type_id == trigger_key.component_type_id
                and group.component_type_index == trigger_key.component_type_index
            ):
                trigger_group = group
                break

        if not trigger_group:
            return

        keys: list[ActorPropertyKey] = []
        datas: list[PropertyData] = []

        for prop in trigger_group.properties:
            matched_read_name = None
            for read_name in read_properties:
                if read_name == "<all>":
                    matched_read_name = read_name
                    break
                if prop.name() == read_name or prop.name().startswith(read_name + "."):
                    matched_read_name = read_name
                    break
            if matched_read_name is None:
                continue
            if prop.name() in [k.property_name for k in keys]:
                continue
            key = ActorPropertyKey(
                actor_path=actor_path,
                entity_id=entity_id,
                entity_path=trigger_key.entity_path,
                component_type_id=trigger_key.component_type_id,
                component_type_index=trigger_key.component_type_index,
                property_name=prop.name(),
                property_type=prop.value_type(),
            )
            keys.append(key)
            datas.append(
                PropertyData(prop.is_read_only(), prop.value(), prop.base_value())
            )

        bus = SceneEditNotificationBus()
        await bus.on_properties_changed(keys, datas, source="post_process")
