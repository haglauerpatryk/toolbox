import pytest

from toolbox.registry import Entry, Registry

# NOTE (untested by design): Registry.register/get take no lock. The framework
# assumes all pieces register at import time, i.e. single-threaded. Registering
# concurrently from multiple threads at runtime is an unguarded race and is
# intentionally out of scope here — revisit if runtime registration is ever added.


def test_register_returns_original_func():
    reg = Registry("thing")

    def f():
        return 1

    assert reg.register("a")(f) is f


def test_register_stores_entry_with_meta():
    reg = Registry("thing")

    def f():
        return 1

    reg.register("a", stages=("before",), priority=5)(f)
    entry = reg.get("a")
    assert isinstance(entry, Entry)
    assert entry.name == "a"
    assert entry.func is f
    assert entry.meta == {"stages": ("before",), "priority": 5}


def test_default_meta_is_empty():
    reg = Registry("thing")
    reg.register("a")(lambda: None)
    assert reg.get("a").meta == {}


def test_duplicate_name_raises_valueerror():
    reg = Registry("thing")
    reg.register("a")(lambda: None)
    with pytest.raises(ValueError, match="duplicate thing 'a' already registered"):
        reg.register("a")(lambda: None)


def test_get_unknown_raises_keyerror():
    reg = Registry("thing")
    with pytest.raises(KeyError, match="unknown thing 'missing'"):
        reg.get("missing")


def test_contains():
    reg = Registry("thing")
    reg.register("a")(lambda: None)
    assert "a" in reg
    assert "b" not in reg


def test_names_preserves_insertion_order():
    reg = Registry("thing")
    reg.register("z")(lambda: None)
    reg.register("a")(lambda: None)
    reg.register("m")(lambda: None)
    assert reg.names() == ["z", "a", "m"]


def test_kind_is_stored():
    assert Registry("hook").kind == "hook"


def test_registries_are_independent():
    a = Registry("one")
    b = Registry("two")
    a.register("x")(lambda: None)
    assert "x" in a
    assert "x" not in b
