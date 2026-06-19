import pytest

from toolbox.registries import rule
from toolbox.selectors import Selector


def test_always_returns_payload():
    assert Selector({}).resolve({"always": ["a", "b"]}) == ["a", "b"]


def test_if_var_includes_on_truthy():
    assert Selector({"DEBUG": 1}).resolve({"if_var": {"DEBUG": ["x"]}}) == ["x"]


def test_if_var_excludes_on_falsy():
    assert Selector({"DEBUG": 0}).resolve({"if_var": {"DEBUG": ["x"]}}) == []


def test_if_var_excludes_when_var_absent():
    assert Selector({}).resolve({"if_var": {"DEBUG": ["x"]}}) == []


def test_if_not_var_includes_on_falsy():
    assert Selector({"DEBUG": 0}).resolve({"if_not_var": {"DEBUG": ["x"]}}) == ["x"]
    assert Selector({}).resolve({"if_not_var": {"DEBUG": ["x"]}}) == ["x"]


def test_if_not_var_excludes_on_truthy():
    assert Selector({"DEBUG": 1}).resolve({"if_not_var": {"DEBUG": ["x"]}}) == []


def test_empty_block_and_none():
    assert Selector({}).resolve({}) == []
    assert Selector({}).resolve(None) == []


def test_empty_payloads_tolerated():
    assert Selector({}).resolve({"always": None}) == []
    assert Selector({"D": 1}).resolve({"if_var": None}) == []
    assert Selector({"D": 0}).resolve({"if_not_var": None}) == []


def test_multiple_rules_combine_in_block_order():
    block = {
        "always": ["a"],
        "if_var": {"D": ["b"]},
        "if_not_var": {"E": ["c"]},
    }
    assert Selector({"D": 1}).resolve(block) == ["a", "b", "c"]


def test_unknown_rule_raises_keyerror():
    with pytest.raises(KeyError, match="unknown rule 'nope'"):
        Selector({}).resolve({"nope": ["x"]})


def test_baseline_rules_are_registered():
    assert {"always", "if_var", "if_not_var"} <= set(rule.names())
