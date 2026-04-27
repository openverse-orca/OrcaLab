from orcalab.path import Path


def test_default_construct_path_is_root_path():
    p = Path()
    assert p == Path.root_path()


def test_equal():
    assert Path("/a") == Path("/a")
    assert Path("/box1") == Path("/box1")
    assert Path() == Path()


def test_as_key():
    d = {Path("/a"): 1, Path("/b"): 2}
    assert Path("/a") in d
    assert d[Path("/a")] == 1
    assert d[Path("/b")] == 2


def test_is_descendant_of():
    assert Path("/a").is_descendant_of(Path("/")) is True
    assert Path("/a/b").is_descendant_of(Path("/a")) is True
    assert Path("/a/b/c").is_descendant_of(Path("/a")) is True

    assert Path("/a").is_descendant_of(Path("/a")) is False
    assert Path("/a/b").is_descendant_of(Path("/b")) is False
    assert Path("/a/b").is_descendant_of(Path("/c")) is False
    assert Path("/a/b").is_descendant_of(Path("/a/b/c")) is False
    assert Path("/aaa").is_descendant_of(Path("/a")) is False


def test_parent():
    assert Path("/a").parent() == Path("/")
    assert Path("/a/b").parent() == Path("/a")
    assert Path("/a/b/c").parent() == Path("/a/b")
    assert Path("/").parent() is None


def test_is_root():
    assert Path("/").is_root() is True
    assert Path().is_root() is True
    assert Path("/a").is_root() is False
    assert Path("/a/b").is_root() is False


def test_sort():
    """
    Path按照字符串排序，因此/a/b在/a/c之前，/a在/a/b之前。同时也能确保父节点在子节点之前。
    """

    paths = [Path("/a/b"), Path("/a/c"), Path("/a"), Path("/b"), Path("/")]
    sorted_paths = sorted(paths)
    assert sorted_paths == [Path("/"), Path("/a"), Path("/a/b"), Path("/a/c"), Path("/b")]