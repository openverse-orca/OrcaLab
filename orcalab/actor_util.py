from copy import deepcopy
import logging
from typing import Any, List, Tuple

from orcalab.actor import AssetActor, BaseActor, GroupActor
from orcalab.actor_property import (
    ActorProperty,
    ActorPropertyGroup,
    ActorPropertyKey,
    ActorPropertyType,
    TreePropertyNode,
)
from orcalab.application_util import get_local_scene
from orcalab.local_scene import LocalScene
from orcalab.path import Path
from orcalab.metadata_service_bus import MetadataServiceRequestBus

logger = logging.getLogger(__name__)


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


def collect_tree_propertys(
    keys: List[ActorPropertyKey],
    props: List[ActorProperty],
    actor_path: Path,
    group_prefix: str,
    node: TreePropertyNode,
):
    """递归收集树形属性的子属性"""
    for prop in node.properties:
        full_name = f"{node.name}.{prop.name()}"
        key = ActorPropertyKey(
            actor_path,
            group_prefix,
            full_name,
            prop.value_type(),
        )
        keys.append(key)
        props.append(prop)

    for child in node.children:
        collect_tree_propertys(keys, props, actor_path, group_prefix, child)


def collect_properties(
    keys: List[ActorPropertyKey],
    props: List[ActorProperty],
    properties: List[ActorPropertyGroup],
    actor_path: Path,
):
    for group in properties:
        for prop in group.properties:
            # TREE 类型的属性没有直接值，跳过获取
            if prop.value_type() == ActorPropertyType.TREE:
                continue
            key = ActorPropertyKey(
                actor_path, group.prefix, prop.name(), prop.value_type()
            )
            props.append(prop)
            keys.append(key)

        # 收集树形属性的子属性
        for tree_node in group.tree_data:
            collect_tree_propertys(keys, props, actor_path, group.prefix, tree_node)


class TreePropertyNode_PairIterator:
    """同时遍历两个 ActorPropertyGroup 的树形属性节点，返回节点对 (node1, node2)，如果两个树并不匹配，抛出异常"""

    def __init__(
        self, tree_data1: List[TreePropertyNode], tree_data2: List[TreePropertyNode]
    ):
        self.stack1: List[TreePropertyNode] = []
        self.stack2: List[TreePropertyNode] = []
        self.stack1.extend(reversed(tree_data1))
        self.stack2.extend(reversed(tree_data2))

    def __iter__(self):
        return self

    def __next__(self) -> Tuple[TreePropertyNode, TreePropertyNode]:
        if len(self.stack1) != len(self.stack2):
            raise Exception(f"Tree mismatch")

        if not self.stack1 and not self.stack2:
            raise StopIteration

        node1 = self.stack1.pop()
        node2 = self.stack2.pop()

        if len(node1.children) != len(node2.children):
            raise Exception(f"Tree mismatch")

        for child in reversed(node1.children):
            self.stack1.append(child)
        for child in reversed(node2.children):
            self.stack2.append(child)

        return node1, node2


def collect_properties_duplicate_data(
    keys: List[ActorPropertyKey],
    props: List[ActorProperty],
    values: List[Any],
    src_properties: List[ActorPropertyGroup],
    dst_properties: List[ActorPropertyGroup],
    dst_actor_path: Path,
):
    for src_group, dst_group in zip(src_properties, dst_properties):
        for prop in src_group.properties:
            # TREE 类型的属性没有直接值，跳过获取
            if prop.value_type() == ActorPropertyType.TREE:
                continue
            key = ActorPropertyKey(
                dst_actor_path, src_group.prefix, prop.name(), prop.value_type()
            )
            keys.append(key)
            props.append(prop)
            values.append(prop.value())

        # 收集树形属性的子属性
        for src_node, dst_node in TreePropertyNode_PairIterator(
            src_group.tree_data, dst_group.tree_data
        ):
            for src_prop, dst_prop in zip(src_node.properties, dst_node.properties):
                full_name = f"{dst_node.name}.{dst_prop.name()}"
                key = ActorPropertyKey(
                    dst_actor_path,
                    dst_group.prefix,
                    full_name,
                    dst_prop.value_type(),
                )
                keys.append(key)
                props.append(dst_prop)
                values.append(src_prop.value())


def sort_actors_with_data[T](
    actor_paths: List[Path], datas: List[T]
) -> Tuple[List[Path], List[T]]:
    if len(actor_paths) != len(datas):
        raise Exception("actor_paths and datas must have the same length")

    if len(actor_paths) == 0:
        return [], []

    def _key(pair: Tuple[Path, T]):
        return pair[0]

    sorted_pairs = sorted(zip(actor_paths, datas), key=_key)
    sorted_actor_paths, sorted_datas = zip(*sorted_pairs)
    return list(sorted_actor_paths), list(sorted_datas)


def clone_actor_basic[T](actor: T) -> T:
    """Clone actor without parent-child relationships."""
    if isinstance(actor, GroupActor):
        new_actor = GroupActor(actor.name)
    elif isinstance(actor, AssetActor):
        new_actor = AssetActor(actor.name, actor.asset_path)
        new_actor.property_groups = deepcopy(actor.property_groups)
    else:
        raise Exception("Unsupported actor type")

    new_actor.transform = actor.transform

    return new_actor  # type: ignore
