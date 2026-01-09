import pytest

from orcalab.actor import BaseActor, GroupActor


def test_add_child():
    group = GroupActor("Group1")
    actor = BaseActor("Actor1", None)
    group.add_child(actor)
    assert actor in group.children
    assert actor.parent is group


def test_set_parent_when_construct():
    group = GroupActor("Group1")
    actor = BaseActor("Actor1", group)
    assert actor in group.children
    assert actor.parent is group


def test_set_parent_none():
    group = GroupActor("Group1")
    actor = BaseActor("Actor1", group)
    actor.parent = None
    assert len(group.children) == 0
    assert actor.parent is None


def test_add_child_wrong_type():
    group = GroupActor("Group1")
    with pytest.raises(TypeError):
        group.add_child("not_an_actor")


def test_remove_child():
    group = GroupActor("Group1")
    actor = BaseActor("Actor1", None)
    group.add_child(actor)
    group.remove_child(actor)
    assert actor not in group.children
    assert actor.parent is None

# TODO: Test the behavior when removing a child that is not present
# def test_remove_child_not_present():
#     group = GroupActor("Group1")
#     actor = BaseActor("Actor1", None)
#     with pytest.raises(ValueError):
#         group.remove_child(actor)


def test_children_property():
    group = GroupActor("Group1")
    actor1 = BaseActor("Actor1", None)
    actor2 = BaseActor("Actor2", None)
    group.add_child(actor1)
    group.add_child(actor2)
    children = group.children
    assert len(children) == 2
    assert children == [actor1, actor2]
    # Ensure it's a copy
    children.append(GroupActor("dummy"))
    assert len(group.children) == 2


def test_repr():
    group = GroupActor("Group1")
    assert "GroupActor(name=Group1" in repr(group)
