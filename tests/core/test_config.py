from toolbox.config import deep_merge_dicts, load_config
from toolbox.core import ToolBox, resolve_toolbox_config


# --- deep_merge_dicts -------------------------------------------------------


def test_scalar_override():
    assert deep_merge_dicts({"a": 1}, {"a": 2}) == {"a": 2}


def test_new_keys_added():
    assert deep_merge_dicts({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}


def test_lists_extend():
    assert deep_merge_dicts({"a": [1]}, {"a": [2, 3]}) == {"a": [1, 2, 3]}


def test_dicts_merge_recursively():
    merged = deep_merge_dicts({"a": {"x": 1}}, {"a": {"y": 2}})
    assert merged == {"a": {"x": 1, "y": 2}}


def test_type_mismatch_overrides():
    assert deep_merge_dicts({"a": {"x": 1}}, {"a": [1]}) == {"a": [1]}
    assert deep_merge_dicts({"a": [1]}, {"a": {"x": 1}}) == {"a": {"x": 1}}


def test_inputs_are_not_mutated():
    a = {"a": [1], "d": {"x": 1}}
    b = {"a": [2], "d": {"y": 2}}
    deep_merge_dicts(a, b)
    assert a == {"a": [1], "d": {"x": 1}}
    assert b == {"a": [2], "d": {"y": 2}}


def test_nested_result_is_a_deep_copy():
    a = {"d": {"x": [1]}}
    merged = deep_merge_dicts(a, {})
    merged["d"]["x"].append(2)
    assert a == {"d": {"x": [1]}}


# --- load_config ------------------------------------------------------------


def test_load_config_parses_yaml(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("a: 1\nb: [x, y]\n")
    assert load_config(str(p)) == {"a": 1, "b": ["x", "y"]}


def test_load_config_is_cached(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("a: 1")
    first = load_config(str(p))
    p.write_text("a: 2")  # disk changes...
    second = load_config(str(p))
    assert second is first  # ...but the cached object is returned
    assert second == {"a": 1}


def test_empty_file_yields_empty_dict(tmp_path):
    p = tmp_path / "empty.yaml"
    p.write_text("")
    assert load_config(str(p)) == {}


# --- resolve_toolbox_config (MRO merge) -------------------------------------


def test_resolve_merges_parent_then_child():
    class Parent(ToolBox):
        name = "parent"

    class Child(Parent):
        name = "child"

    data = {
        "parent": {"hooks": {"always": ["a"]}, "sinks": {"always": ["file"]}},
        "child": {"hooks": {"always": ["b"]}},
    }
    merged = resolve_toolbox_config(Child, data)
    # parent's section applies first, child's deep-merges over it
    assert merged == {
        "hooks": {"always": ["a", "b"]},
        "sinks": {"always": ["file"]},
    }


def test_resolve_skips_base_toolbox_and_nameless_classes():
    class Named(ToolBox):
        name = "named"

    class Nameless(Named):
        name = None

    data = {"named": {"x": 1}, "toolbox": {"x": 99}}
    # ToolBox itself (name="toolbox") is skipped; Nameless contributes nothing
    assert resolve_toolbox_config(Nameless, data) == {"x": 1}


def test_resolve_missing_section_is_empty():
    class Solo(ToolBox):
        name = "solo"

    assert resolve_toolbox_config(Solo, {}) == {}
