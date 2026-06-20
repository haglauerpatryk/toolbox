import pytest

from toolbox.core import ToolBox
from toolbox.registries import hook


def register_hook(name):
    if name not in hook:
        def fn(ctx, _n=name):
            ctx.scratch.setdefault("ran", []).append(_n)

        fn.__name__ = name
        hook.register(name, stages=("before",))(fn)


def section(name, always):
    return {name: {"hooks": {"always": list(always)}}}


def make_toolbox_class(
    sources=None, *, name="s_tb", variables=None, dedupe=True, warn=True, config_path=None
):
    attrs = {
        "name": name,
        "features": [],
        "auto_discover": False,
        "variables": variables or {},
        "dedupe": dedupe,
        "warn_on_dedupe": warn,
    }
    if sources is not None:
        attrs["config_sources"] = sources
    if config_path is not None:
        attrs["config_path"] = config_path
    return type("DynamicToolbox", (ToolBox,), attrs)


def before_names(tb):
    return [f.__name__ for f in tb.hooks["before"]]


# --- ordered source composition ---------------------------------------------


def test_config_sources_merges_two_dict_sources():
    register_hook("h1")
    register_hook("h2")
    cls = make_toolbox_class([section("s_tb", ["h1"]), section("s_tb", ["h2"])])
    assert before_names(cls()) == ["h1", "h2"]


def test_later_source_overrides_via_order():
    # order is the only precedence rule: a later source's scalar wins
    register_hook("h1")
    cls = make_toolbox_class(
        [
            {"s_tb": {"hooks": {"always": ["h1"]}, "variables_note": "early"}},
            {"s_tb": {"variables_note": "late"}},
        ]
    )
    # (no assertion on the note itself — just that merge order didn't drop h1)
    assert before_names(cls()) == ["h1"]


def test_dict_source_is_the_json_slot():
    # a plain dict, e.g. parsed from an API JSON response, is a valid source
    register_hook("h1")
    cls = make_toolbox_class([{"s_tb": {"hooks": {"always": ["h1"]}}}])
    assert before_names(cls()) == ["h1"]


def test_constructor_config_sources_overrides_class_attribute():
    register_hook("h1")
    register_hook("h2")
    cls = make_toolbox_class([section("s_tb", ["h1"])])
    tb = cls(config_sources=[section("s_tb", ["h2"])])
    assert before_names(tb) == ["h2"]


def test_missing_section_raises_handshake_error():
    # the config never names the toolbox -> hard fail, not a silent empty config
    cls = make_toolbox_class([{"some_other_toolbox": {"hooks": {"always": ["x"]}}}])
    with pytest.raises(ValueError, match="no matching config section"):
        cls()


def test_empty_section_satisfies_the_handshake():
    # naming the toolbox, even with an empty section, is the acknowledgement
    cls = make_toolbox_class([{"s_tb": {}}])
    tb = cls()
    assert before_names(tb) == []


def test_config_path_fallback_when_no_sources(tmp_path):
    register_hook("h1")
    p = tmp_path / "c.yaml"
    p.write_text("s_tb:\n  hooks:\n    always: [h1]\n")
    cls = make_toolbox_class(sources=None, config_path=str(p))
    assert before_names(cls()) == ["h1"]


# --- dedupe + flags ---------------------------------------------------------


def test_duplicates_removed_and_warned_in_yellow(capsys):
    register_hook("h1")
    cls = make_toolbox_class([section("s_tb", ["h1"]), section("s_tb", ["h1"])])
    tb = cls()
    assert before_names(tb) == ["h1"]
    err = capsys.readouterr().err
    assert "removed duplicate hook" in err
    assert "h1" in err
    assert "\033[33m" in err  # yellow ANSI
    assert "s_tb" in err


def test_dedupe_disabled_keeps_duplicates(capsys):
    register_hook("h1")
    cls = make_toolbox_class(
        [section("s_tb", ["h1"]), section("s_tb", ["h1"])], dedupe=False
    )
    tb = cls()
    assert before_names(tb) == ["h1", "h1"]  # runs twice
    assert capsys.readouterr().err == ""


def test_dedupe_silent_when_warning_disabled(capsys):
    register_hook("h1")
    cls = make_toolbox_class(
        [section("s_tb", ["h1"]), section("s_tb", ["h1"])], warn=False
    )
    tb = cls()
    assert before_names(tb) == ["h1"]
    assert capsys.readouterr().err == ""


def test_dedupe_catches_cross_selector_duplicate(capsys):
    # same name reached via `always` and `if_var` resolves to one entry
    register_hook("h1")
    cls = make_toolbox_class(
        [
            {
                "s_tb": {
                    "hooks": {
                        "always": ["h1"],
                        "if_var": {"ON": ["h1"]},
                    }
                }
            }
        ],
        variables={"ON": 1},
    )
    tb = cls()
    assert before_names(tb) == ["h1"]
    assert "removed duplicate hook" in capsys.readouterr().err
