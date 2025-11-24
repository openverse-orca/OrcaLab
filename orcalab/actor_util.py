from orcalab.actor import BaseActor, GroupActor
from orcalab.application_util import get_local_scene
from orcalab.path import Path


def make_unique_name(base_name: str, parent: BaseActor | Path) -> str:
    local_scene = get_local_scene()
    parent_actor, _ = local_scene.get_actor_and_path(parent)
    if not isinstance(parent_actor, GroupActor):
        raise Exception("Parent must be a GroupActor")

    existing_names = {child.name for child in parent_actor.children}

    counter = 1
    # base_name 可能是一个路径，因此以最后一个 / 之后作为名字
    base_name = base_name.split("/")[-1]
    new_name = f"{base_name}_{counter}"
    while new_name in existing_names:
        counter += 1
        new_name = f"{base_name}_{counter}"

    return new_name
