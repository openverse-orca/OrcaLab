from orcalab.entity_path import EntityPath, FullEntityPath, NameWithIndex
from orcalab.path import Path


def _make_entity_path(segments: list[tuple[str, int]]) -> EntityPath:
    entity_path = EntityPath([NameWithIndex(name, index) for name, index in segments])
    return entity_path


def test_string_uses_segment_names():
    entity_path = _make_entity_path([("root", 0), ("child", 1), ("leaf", 2)])

    assert entity_path.string() == "root/child/leaf"
    assert repr(entity_path) == "root/child/leaf"


def test_string_cache_does_not_change_result():
    entity_path = _make_entity_path([("root", 0), ("child", 1)])

    first_result = entity_path.string()
    entity_path._segments[0].name = "renamed"

    assert first_result == "root/child"
    assert entity_path.string() == "root/child"


def test_equality_and_hash_use_segment_indices():
    left = _make_entity_path([("root", 0), ("child", 1)])
    same_shape_different_names = _make_entity_path([("parent", 0), ("node", 1)])
    different_shape = _make_entity_path([("root", 0), ("child", 2)])

    assert left == same_shape_different_names
    assert hash(left) == hash(same_shape_different_names)
    assert left != different_shape


def test_entity_path_can_be_used_as_dict_key():
    entity_path = _make_entity_path([("root", 0), ("child", 1)])
    lookup = {entity_path: "value"}

    same_path = _make_entity_path([("other_root", 0), ("other_child", 1)])

    assert lookup[same_path] == "value"


def test_full_entity_path_stores_actor_and_entity_paths():
    actor_path = Path("/actor")
    entity_path = _make_entity_path([("root", 0)])

    full_entity_path = FullEntityPath(actor_path, entity_path)

    assert full_entity_path.actor_path == actor_path
    assert full_entity_path.entity_path == entity_path
