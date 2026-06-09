import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from orcalab.actor_property import ActorPropertyKey, ActorProperty, ActorPropertyType, ActorPropertyGroup
from orcalab.path import Path
from orcalab.post_process_dispatcher import PostProcessDispatcher
from orcalab.property_post_process import (
    PostProcessRegistry,
    PostProcessRule,
    ReadPropertiesAction,
)


class TestPostProcessRegistry(unittest.TestCase):
    def setUp(self):
        self._original_instance = PostProcessRegistry._instance
        PostProcessRegistry._instance = None

    def tearDown(self):
        PostProcessRegistry._instance = self._original_instance

    def test_singleton(self):
        a = PostProcessRegistry.instance()
        b = PostProcessRegistry.instance()
        self.assertIs(a, b)

    def test_register_and_find_by_property_name(self):
        registry = PostProcessRegistry.instance()
        rule = PostProcessRule(
            trigger_property="foo",
            component_type="{UUID-1}",
            action=ReadPropertiesAction(["bar", "baz"]),
        )
        registry.register(rule)
        results = registry.find_rules("{UUID-1}", "foo")
        self.assertEqual(len(results), 1)
        self.assertIs(results[0], rule)

    def test_find_no_match(self):
        registry = PostProcessRegistry.instance()
        registry.register(PostProcessRule(
            trigger_property="foo",
            action=ReadPropertiesAction(["bar"]),
        ))
        results = registry.find_rules("", "nonexistent")
        self.assertEqual(len(results), 0)

    def test_find_with_component_type_match(self):
        registry = PostProcessRegistry.instance()
        rule = PostProcessRule(
            trigger_property="foo",
            component_type="{UUID-1}",
            action=ReadPropertiesAction(["bar"]),
        )
        registry.register(rule)
        results = registry.find_rules("{UUID-1}", "foo")
        self.assertEqual(len(results), 1)

    def test_find_with_component_type_mismatch(self):
        registry = PostProcessRegistry.instance()
        rule = PostProcessRule(
            trigger_property="foo",
            component_type="{UUID-1}",
            action=ReadPropertiesAction(["bar"]),
        )
        registry.register(rule)
        results = registry.find_rules("{UUID-2}", "foo")
        self.assertEqual(len(results), 0)

    def test_multiple_rules_same_property(self):
        registry = PostProcessRegistry.instance()
        rule1 = PostProcessRule(
            trigger_property="foo",
            component_type="{UUID-1}",
            action=ReadPropertiesAction(["bar"]),
        )
        rule2 = PostProcessRule(
            trigger_property="foo",
            component_type="{UUID-1}",
            action=ReadPropertiesAction(["baz"]),
        )
        registry.register(rule1)
        registry.register(rule2)
        results = registry.find_rules("{UUID-1}", "foo")
        self.assertEqual(len(results), 2)


class TestPostProcessDispatcherDebounce(unittest.TestCase):
    def test_on_property_set_creates_timer(self):
        local_scene = MagicMock()
        remote_scene = MagicMock()
        dispatcher = PostProcessDispatcher(local_scene, remote_scene)

        PostProcessRegistry._instance = None
        try:
            registry = PostProcessRegistry.instance()
            registry.register(PostProcessRule(
                trigger_property="testProp",
                component_type="{UUID-1}",
                action=ReadPropertiesAction(["derived1"]),
                delay_ms=100,
            ))

            key = ActorPropertyKey(
                actor_path=Path("/actor1"),
                group_prefix="group",
                property_name="testProp",
                property_type=ActorPropertyType.FLOAT,
                entity_id=1,
                component_type="{UUID-1}",
            )

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                dispatcher.on_property_set(key)
                self.assertEqual(len(dispatcher._timers), 1)
            finally:
                dispatcher.cancel_all()
                loop.close()
        finally:
            PostProcessRegistry._instance = None

    def test_cancel_all(self):
        local_scene = MagicMock()
        remote_scene = MagicMock()
        dispatcher = PostProcessDispatcher(local_scene, remote_scene)

        PostProcessRegistry._instance = None
        try:
            registry = PostProcessRegistry.instance()
            registry.register(PostProcessRule(
                trigger_property="testProp",
                component_type="{UUID-1}",
                action=ReadPropertiesAction(["derived1"]),
                delay_ms=500,
            ))

            key = ActorPropertyKey(
                actor_path=Path("/actor1"),
                group_prefix="group",
                property_name="testProp",
                property_type=ActorPropertyType.FLOAT,
                entity_id=1,
                component_type="{UUID-1}",
            )

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                dispatcher.on_property_set(key)
                self.assertEqual(len(dispatcher._timers), 1)
                dispatcher.cancel_all()
                self.assertEqual(len(dispatcher._timers), 0)
            finally:
                loop.close()
        finally:
            PostProcessRegistry._instance = None

    def test_debounce_resets_timer(self):
        local_scene = MagicMock()
        remote_scene = MagicMock()
        dispatcher = PostProcessDispatcher(local_scene, remote_scene)

        PostProcessRegistry._instance = None
        try:
            registry = PostProcessRegistry.instance()
            registry.register(PostProcessRule(
                trigger_property="testProp",
                component_type="{UUID-1}",
                action=ReadPropertiesAction(["derived1"]),
                delay_ms=500,
            ))

            key = ActorPropertyKey(
                actor_path=Path("/actor1"),
                group_prefix="group",
                property_name="testProp",
                property_type=ActorPropertyType.FLOAT,
                entity_id=1,
                component_type="{UUID-1}",
            )

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                dispatcher.on_property_set(key)
                first_handle = list(dispatcher._timers.values())[0]
                dispatcher.on_property_set(key)
                second_handle = list(dispatcher._timers.values())[0]
                self.assertNotEqual(first_handle, second_handle)
                self.assertTrue(first_handle.cancelled())
            finally:
                dispatcher.cancel_all()
                loop.close()
        finally:
            PostProcessRegistry._instance = None

    def test_no_rules_no_timer(self):
        local_scene = MagicMock()
        remote_scene = MagicMock()
        dispatcher = PostProcessDispatcher(local_scene, remote_scene)

        PostProcessRegistry._instance = None
        try:
            key = ActorPropertyKey(
                actor_path=Path("/actor1"),
                group_prefix="group",
                property_name="nonexistent",
                property_type=ActorPropertyType.FLOAT,
                component_type="{UUID-1}",
            )

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                dispatcher.on_property_set(key)
                self.assertEqual(len(dispatcher._timers), 0)
            finally:
                loop.close()
        finally:
            PostProcessRegistry._instance = None


class TestPostProcessDispatcherExecute(unittest.TestCase):
    def test_execute_read_action(self):
        PostProcessRegistry._instance = None
        try:
            local_scene = MagicMock()
            remote_scene = MagicMock()

            prop_density = MagicMock(spec=ActorProperty)
            prop_density.name.return_value = "density"
            prop_density.value_type.return_value = ActorPropertyType.FLOAT

            prop_friction = MagicMock(spec=ActorProperty)
            prop_friction.name.return_value = "friction"
            prop_friction.value_type.return_value = ActorPropertyType.FLOAT

            group = MagicMock(spec=ActorPropertyGroup)
            group.prefix = "group"
            group.properties = [prop_density, prop_friction]

            local_scene.parse_property_key.return_value = (MagicMock(), group, MagicMock())

            remote_scene.get_properties = AsyncMock(return_value=[1000.0, [0.5, 0.1, 0.1]])

            dispatcher = PostProcessDispatcher(local_scene, remote_scene)

            trigger_key = ActorPropertyKey(
                actor_path=Path("/actor1"),
                group_prefix="group",
                property_name="physicalMaterial",
                property_type=ActorPropertyType.INTEGER,
                entity_id=1,
                component_type="{UUID-1}",
            )

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    dispatcher._execute_read_action(trigger_key, ["density", "friction"])
                )

                remote_scene.get_properties.assert_called_once()
                call_args = remote_scene.get_properties.call_args[0][0]
                self.assertEqual(len(call_args), 2)
                self.assertEqual(call_args[0].property_name, "density")
                self.assertEqual(call_args[1].property_name, "friction")

                prop_density.set_value.assert_called_once_with(1000.0)
                prop_friction.set_value.assert_called_once_with([0.5, 0.1, 0.1])
            finally:
                loop.close()
        finally:
            PostProcessRegistry._instance = None

    def test_execute_read_action_skips_missing_props(self):
        PostProcessRegistry._instance = None
        try:
            local_scene = MagicMock()
            remote_scene = MagicMock()

            prop_density = MagicMock(spec=ActorProperty)
            prop_density.name.return_value = "density"
            prop_density.value_type.return_value = ActorPropertyType.FLOAT

            group = MagicMock(spec=ActorPropertyGroup)
            group.prefix = "group"
            group.properties = [prop_density]

            local_scene.parse_property_key.return_value = (MagicMock(), group, MagicMock())

            remote_scene.get_properties = AsyncMock(return_value=[1000.0])

            dispatcher = PostProcessDispatcher(local_scene, remote_scene)

            trigger_key = ActorPropertyKey(
                actor_path=Path("/actor1"),
                group_prefix="group",
                property_name="physicalMaterial",
                property_type=ActorPropertyType.INTEGER,
                entity_id=1,
                component_type="{UUID-1}",
            )

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    dispatcher._execute_read_action(trigger_key, ["density", "nonexistent"])
                )

                call_args = remote_scene.get_properties.call_args[0][0]
                self.assertEqual(len(call_args), 1)
                self.assertEqual(call_args[0].property_name, "density")
            finally:
                loop.close()
        finally:
            PostProcessRegistry._instance = None

    def test_execute_read_action_handles_grpc_error(self):
        PostProcessRegistry._instance = None
        try:
            local_scene = MagicMock()
            remote_scene = MagicMock()

            prop_density = MagicMock(spec=ActorProperty)
            prop_density.name.return_value = "density"
            prop_density.value_type.return_value = ActorPropertyType.FLOAT

            group = MagicMock(spec=ActorPropertyGroup)
            group.prefix = "group"
            group.properties = [prop_density]

            local_scene.parse_property_key.return_value = (MagicMock(), group, MagicMock())

            remote_scene.get_properties = AsyncMock(side_effect=Exception("gRPC error"))

            dispatcher = PostProcessDispatcher(local_scene, remote_scene)

            trigger_key = ActorPropertyKey(
                actor_path=Path("/actor1"),
                group_prefix="group",
                property_name="physicalMaterial",
                property_type=ActorPropertyType.INTEGER,
                entity_id=1,
                component_type="{UUID-1}",
            )

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    dispatcher._execute_read_action(trigger_key, ["density"])
                )
                prop_density.set_value.assert_not_called()
            finally:
                loop.close()
        finally:
            PostProcessRegistry._instance = None

    def test_execute_rules_merges_read_properties(self):
        PostProcessRegistry._instance = None
        try:
            local_scene = MagicMock()
            remote_scene = MagicMock()

            prop_density = MagicMock(spec=ActorProperty)
            prop_density.name.return_value = "density"
            prop_density.value_type.return_value = ActorPropertyType.FLOAT

            prop_friction = MagicMock(spec=ActorProperty)
            prop_friction.name.return_value = "friction"
            prop_friction.value_type.return_value = ActorPropertyType.FLOAT

            group = MagicMock(spec=ActorPropertyGroup)
            group.prefix = "group"
            group.properties = [prop_density, prop_friction]

            local_scene.parse_property_key.return_value = (MagicMock(), group, MagicMock())
            remote_scene.get_properties = AsyncMock(return_value=[1000.0, [0.5, 0.1, 0.1]])

            dispatcher = PostProcessDispatcher(local_scene, remote_scene)

            rules = [
                PostProcessRule(trigger_property="a", action=ReadPropertiesAction(["density"]), delay_ms=50),
                PostProcessRule(trigger_property="a", action=ReadPropertiesAction(["density", "friction"]), delay_ms=100),
            ]

            trigger_key = ActorPropertyKey(
                actor_path=Path("/actor1"),
                group_prefix="group",
                property_name="a",
                property_type=ActorPropertyType.FLOAT,
                entity_id=1,
                component_type="{UUID-1}",
            )

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(dispatcher._execute_rules(rules, trigger_key))

                call_args = remote_scene.get_properties.call_args[0][0]
                prop_names = [k.property_name for k in call_args]
                self.assertEqual(prop_names, ["density", "friction"])
            finally:
                loop.close()
        finally:
            PostProcessRegistry._instance = None


class TestReadPropertiesAction(unittest.TestCase):
    def test_read_properties(self):
        action = ReadPropertiesAction(["density", "friction", "solref"])
        self.assertEqual(action.read_properties, ["density", "friction", "solref"])


class TestPostProcessRule(unittest.TestCase):
    def test_defaults(self):
        rule = PostProcessRule(trigger_property="foo", action=ReadPropertiesAction(["bar"]))
        self.assertEqual(rule.trigger_property, "foo")
        self.assertEqual(rule.component_type, "")
        self.assertEqual(rule.delay_ms, 100)

    def test_custom_values(self):
        rule = PostProcessRule(
            trigger_property="foo",
            component_type="{UUID}",
            action=ReadPropertiesAction(["bar"]),
            delay_ms=200,
        )
        self.assertEqual(rule.component_type, "{UUID}")
        self.assertEqual(rule.delay_ms, 200)


class TestActorPropertyPostReadFields(unittest.TestCase):
    def test_post_read_fields_default(self):
        prop = ActorProperty(name="test", display_name="Test", type=ActorPropertyType.FLOAT, value=0.0)
        self.assertEqual(prop.post_read_fields(), [])
        self.assertEqual(prop.post_read_delay_ms(), 0)

    def test_post_read_fields_setter(self):
        prop = ActorProperty(name="test", display_name="Test", type=ActorPropertyType.FLOAT, value=0.0)
        prop.set_post_read_fields(["density", "friction"])
        prop.set_post_read_delay_ms(150)
        self.assertEqual(prop.post_read_fields(), ["density", "friction"])
        self.assertEqual(prop.post_read_delay_ms(), 150)

class TestAutoRegisterFromPropertyGroup(unittest.TestCase):
    def test_auto_register_from_property_group(self):
        PostProcessRegistry._instance = None
        try:
            from orcalab.protos.edit_service_wrapper import EditServiceWrapper
            from orcalab.protos import edit_service_pb2

            wrapper = EditServiceWrapper.__new__(EditServiceWrapper)

            pg_msg = edit_service_pb2.PropertyGroup(
                prefix="actor",
                name="MjGeomComponent",
                display_name="碰撞体",
                component_type_id="{39E400EC-2015-416D-8483-3C64041787A5}",
            )
            prop_msg = pg_msg.properties.add()
            prop_msg.type = edit_service_pb2.PropertyType.Value("ENUM")
            prop_msg.name = "physicalMaterial"
            prop_msg.display_name = "物理材质"
            prop_msg.post_read_fields.extend(["density", "friction", "solref", "solimp", "condim"])
            prop_msg.post_read_delay_ms = 100

            pg = wrapper._parse_property_group_msg(pg_msg)

            registry = PostProcessRegistry.instance()
            rules = registry.find_rules("{39E400EC-2015-416D-8483-3C64041787A5}", "physicalMaterial")
            self.assertEqual(len(rules), 1)
            self.assertEqual(rules[0].action.read_properties, ["density", "friction", "solref", "solimp", "condim"])
            self.assertEqual(rules[0].delay_ms, 100)
            self.assertEqual(rules[0].component_type, "{39E400EC-2015-416D-8483-3C64041787A5}")

            self.assertEqual(len(pg.properties), 1)
            self.assertEqual(pg.properties[0].post_read_fields(), ["density", "friction", "solref", "solimp", "condim"])
            self.assertEqual(pg.properties[0].post_read_delay_ms(), 100)
        finally:
            PostProcessRegistry._instance = None

    def test_no_register_without_post_read_fields(self):
        PostProcessRegistry._instance = None
        try:
            from orcalab.protos.edit_service_wrapper import EditServiceWrapper
            from orcalab.protos import edit_service_pb2

            wrapper = EditServiceWrapper.__new__(EditServiceWrapper)

            pg_msg = edit_service_pb2.PropertyGroup(
                prefix="actor",
                name="MjGeomComponent",
                display_name="碰撞体",
                component_type_id="{39E400EC-2015-416D-8483-3C64041787A5}",
            )
            prop_msg = pg_msg.properties.add()
            prop_msg.type = edit_service_pb2.PropertyType.Value("Float")
            prop_msg.name = "density"
            prop_msg.display_name = "密度"

            wrapper._parse_property_group_msg(pg_msg)

            registry = PostProcessRegistry.instance()
            rules = registry.find_rules("{39E400EC-2015-416D-8483-3C64041787A5}", "density")
            self.assertEqual(len(rules), 0)
        finally:
            PostProcessRegistry._instance = None


if __name__ == "__main__":
    unittest.main()
