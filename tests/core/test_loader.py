from toolbox.config import dedupe, load_config, resolve_sources
from toolbox.config import json as json_format
from toolbox.config import yaml as yaml_format


# --- deserializers (each just turns text into a dict) -----------------------


def test_yaml_deserialize_returns_dict():
    assert yaml_format.deserialize("a: 1\nb: [x, y]") == {"a": 1, "b": ["x", "y"]}


def test_yaml_deserialize_empty_is_empty_dict():
    assert yaml_format.deserialize("") == {}


def test_json_deserialize_returns_dict():
    assert json_format.deserialize('{"a": 1, "b": [1, 2]}') == {"a": 1, "b": [1, 2]}


def test_json_deserialize_blank_is_empty_dict():
    assert json_format.deserialize("") == {}
    assert json_format.deserialize("   \n  ") == {}


# --- load_config dispatch by extension --------------------------------------


def test_load_config_dispatches_yaml(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("a: 1")
    assert load_config(str(p)) == {"a": 1}


def test_load_config_dispatches_yml(tmp_path):
    p = tmp_path / "c.yml"
    p.write_text("a: 1")
    assert load_config(str(p)) == {"a": 1}


def test_load_config_dispatches_json(tmp_path):
    p = tmp_path / "c.json"
    p.write_text('{"a": 1}')
    assert load_config(str(p)) == {"a": 1}


def test_load_config_unknown_extension_falls_back_to_yaml(tmp_path):
    p = tmp_path / "c.conf"
    p.write_text("a: 1")
    assert load_config(str(p)) == {"a": 1}


def test_yaml_and_json_parse_equivalently(tmp_path):
    y = tmp_path / "c.yaml"
    y.write_text("a: 1\nb: [1, 2]")
    j = tmp_path / "c.json"
    j.write_text('{"a": 1, "b": [1, 2]}')
    assert load_config(str(y)) == load_config(str(j))


# --- resolve_sources (ordered merge over dicts / files / dirs) --------------


def test_single_dict_passthrough():
    assert resolve_sources([{"a": 1}]) == {"a": 1}


def test_empty_source_list_is_empty():
    assert resolve_sources([]) == {}


def test_dicts_merge_in_order_later_overrides_scalar_extends_list():
    merged = resolve_sources([{"x": 1, "l": [1]}, {"x": 9, "l": [2]}])
    assert merged == {"x": 9, "l": [1, 2]}


def test_source_dict_is_not_mutated():
    base = {"s": {"l": [1]}}
    resolve_sources([base, {"s": {"l": [2]}}])
    assert base == {"s": {"l": [1]}}


def test_file_source(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("a: 1")
    assert resolve_sources([str(p)]) == {"a": 1}


def test_directory_source_sorted_skips_underscore_and_nonconfig(tmp_path):
    d = tmp_path / "configs"
    d.mkdir()
    (d / "a.yaml").write_text("order: [a]")
    (d / "b.yaml").write_text("order: [b]")
    (d / "_skip.yaml").write_text("order: [skip]")
    (d / "notes.txt").write_text("ignored")
    assert resolve_sources([str(d)]) == {"order": ["a", "b"]}


def test_directory_mixes_yaml_and_json(tmp_path):
    d = tmp_path / "configs"
    d.mkdir()
    (d / "a.yaml").write_text("l: [a]")
    (d / "b.json").write_text('{"l": ["b"]}')
    assert resolve_sources([str(d)]) == {"l": ["a", "b"]}


def test_mixed_dict_file_dir(tmp_path):
    f = tmp_path / "c.yaml"
    f.write_text("from_file: 1")
    d = tmp_path / "configs"
    d.mkdir()
    (d / "x.yaml").write_text("from_dir: 1")
    merged = resolve_sources([{"from_dict": 1}, str(f), str(d)])
    assert merged == {"from_dict": 1, "from_file": 1, "from_dir": 1}


# --- dedupe -----------------------------------------------------------------


def test_dedupe_preserves_first_seen_order():
    assert dedupe(["a", "b", "a", "c", "b"]) == (["a", "b", "c"], ["a", "b"])


def test_dedupe_no_duplicates():
    assert dedupe(["a", "b"]) == (["a", "b"], [])


def test_dedupe_empty():
    assert dedupe([]) == ([], [])
