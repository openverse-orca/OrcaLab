import logging
from typing import Any, List, Tuple, TypeVar

from orcalab.actor import AssetActor, BaseActor, GroupActor
from orcalab.actor_property import (
    ActorProperty,
    ActorPropertyGroup,
    ActorPropertyKey,
    ActorPropertyType,
)
from orcalab.application_util import get_local_scene
from orcalab.local_scene import LocalScene
from orcalab.path import Path
from orcalab.metadata_service_bus import MetadataServiceRequestBus

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


def is_valid_char(c: str) -> bool:
    if c == "_":
        return True
    if c.isalpha():
        return True
    if c.isdigit():
        return True
    return False


def santitize_name(name: str) -> str:
    # 移除非法字符
    characters = []
    for c in name:
        if is_valid_char(c):
            characters.append(c)
        else:
            characters.append("_")

    sanitized = "".join(characters)
    # 如果名字以数字开头，添加前缀 "_"
    if sanitized and sanitized[0].isdigit():
        sanitized = "_" + sanitized
    # 如果名字为空，使用默认名字
    if not sanitized:
        sanitized = "actor"
    return sanitized


def make_unique_name(base_name: str, parent: BaseActor | Path) -> str:
    local_scene = get_local_scene()
    parent_actor, _ = local_scene.get_actor_and_path(parent)
    if not isinstance(parent_actor, GroupActor):
        raise Exception("Parent must be a GroupActor")

    existing_names = {child.name for child in parent_actor.children}

    counter = 1
    # base_name 可能是一个路径，因此以最后一个 / 之后作为名字
    out_put = []
    MetadataServiceRequestBus().get_asset_info(base_name, out_put)
    if len(out_put) > 0 and out_put[0] is not None:
        english_name = out_put[0].get("englishName", None)
        if type(english_name) == str and english_name.strip() != "":
            base_name = english_name
    base_name = base_name.split("/")[-1]
    base_name = santitize_name(base_name)
    new_name = f"{base_name}_{counter}"
    while new_name in existing_names:
        counter += 1
        new_name = f"{base_name}_{counter}"

    return new_name


def parse_count_suffix(name: str) -> Tuple[str, int]:
    under_score = name.rfind("_")
    if under_score == -1:
        return name, 1

    base_name, suffix = name[:under_score], name[under_score + 1 :]
    if suffix.isdigit():
        return base_name, int(suffix)
    else:
        return name, 1


def make_duplicate_names(existing_names: List[str], names: List[str]) -> List[str]:
    unique_names = []
    for name in names:
        base_name, counter = parse_count_suffix(name)
        base_name = santitize_name(base_name)
        new_name = f"{base_name}_{counter}"
        while new_name in existing_names or new_name in unique_names:
            counter += 1
            new_name = f"{base_name}_{counter}"
        unique_names.append(new_name)

    return unique_names


def make_unique_name1(existing_names: List[str], name: str) -> str:
    base_name, counter = parse_count_suffix(name)
    base_name = santitize_name(base_name)
    new_name = f"{base_name}_{counter}"
    while new_name in existing_names:
        counter += 1
        new_name = f"{base_name}_{counter}"
    return new_name


class ActorIterator:
    """深度优先遍历 Actor 树的迭代器"""

    def __init__(self, root: BaseActor, include_root: bool):
        self.stack = []
        if include_root:
            self.stack.append(root)
        else:
            if isinstance(root, GroupActor):
                self.stack.extend(reversed(root.children))

    def __iter__(self):
        return self

    def __next__(self) -> BaseActor:
        if not self.stack:
            raise StopIteration

        current = self.stack.pop()
        if isinstance(current, GroupActor):
            self.stack.extend(reversed(current.children))
        return current




def sort_actors_with_data(
    actor_paths: List[Path], datas: List[_T]
) -> Tuple[List[Path], List[_T]]:
    if len(actor_paths) != len(datas):
        raise Exception("actor_paths and datas must have the same length")

    if len(actor_paths) == 0:
        return [], []

    def _key(pair: Tuple[Path, _T]):
        return pair[0]

    sorted_pairs = sorted(zip(actor_paths, datas), key=_key)
    sorted_actor_paths, sorted_datas = zip(*sorted_pairs)
    return list(sorted_actor_paths), list(sorted_datas)


_T_clone = TypeVar("_T_clone", BaseActor, AssetActor, GroupActor)


def clone_actor_basic(actor: _T_clone) -> _T_clone:
    """Clone actor without parent-child relationships."""
    if isinstance(actor, GroupActor):
        new_actor = GroupActor(actor.name)
    elif isinstance(actor, AssetActor):
        new_actor = AssetActor(actor.name, actor.asset_path)
    else:
        raise Exception("Unsupported actor type")

    new_actor.transform = actor.transform
    new_actor.is_visible = actor.is_visible
    new_actor.is_locked = actor.is_locked
    new_actor.is_parent_visible = actor.is_parent_visible
    new_actor.is_parent_locked = actor.is_parent_locked

    return new_actor  # type: ignore
