import pytest

from toolbox import inspect as ti
from toolbox.core import ToolBox
from toolbox.registries import hook, sink


def register_hook(name, stages=("before",)):
    if name not in hook:
        def fn(ctx, _n=name):
            ctx.log(_n)

        fn.__name__ = name
        hook.register(name, stages=stages)(fn)


def register_sink(name):
    if name not in sink:
        def fn(ctx, _n=name):
            pass

        fn.__name__ = name
        sink.register(name)(fn)


def make_tb(name, hooks=None, sinks=None):
    block = {}
    if hooks:
        block["hooks"] = {"always": list(hooks)}
    if sinks:
        block["sinks"] = {"always": list(sinks)}
    cls = type(
        "TB_" + name,
        (ToolBox,),
        {
            "name": name,
            "config_sources": [{name: block}],
            "features": [],
            "auto_discover": False,
        },
    )
    return cls()


# --- the core tag -----------------------------------------------------------


def test_tag_is_set_on_a_wrapped_function():
    register_hook("h1")
    tb = make_tb("t1", hooks=["h1"])

    @tb
    def f():
        return 1

    assert f.__toolbox__ is tb


def test_inactive_toolbox_leaves_function_untagged():
    tb = make_tb("t_empty")  # section present but no pieces -> inactive

    def f():
        return 1

    assert tb.wrap(f) is f
    assert not hasattr(f, "__toolbox__")


# --- stack walking ----------------------------------------------------------


def test_stack_single_layer():
    register_hook("h1")
    tb = make_tb("t1", hooks=["h1"])

    @tb
    def f():
        return 1

    assert ti.toolbox_stack(f) == [tb]


def test_stack_two_layers_outermost_first():
    register_hook("h1")
    register_hook("h2")
    tb1 = make_tb("t1", hooks=["h1"])
    tb2 = make_tb("t2", hooks=["h2"])

    @tb1
    @tb2
    def f():
        return 1

    assert ti.toolbox_stack(f) == [tb1, tb2]


def test_stack_of_plain_function_is_empty():
    assert ti.toolbox_stack(lambda: 1) == []


# --- active pieces ----------------------------------------------------------


def test_active_pieces_reports_names_by_kind():
    register_hook("h1", stages=("before", "after"))
    register_sink("s1")
    tb = make_tb("t1", hooks=["h1"], sinks=["s1"])
    p = ti.active_pieces(tb)
    assert p["hooks"]["before"] == ["h1"]
    assert p["hooks"]["after"] == ["h1"]
    assert p["sinks"] == ["s1"]
    assert p["wrappers"] == []


# --- inspect_function -------------------------------------------------------


def test_inspect_reports_layers_and_no_duplicates():
    register_hook("h1")
    register_hook("h2")
    tb1 = make_tb("t1", hooks=["h1"])
    tb2 = make_tb("t2", hooks=["h2"])

    @tb1
    @tb2
    def my_func():
        return 1

    report = ti.inspect_function(my_func)
    assert report["function"] == "my_func"
    assert [layer["name"] for layer in report["layers"]] == ["t1", "t2"]
    assert report["duplicate_pieces"] == {}
    assert report["repeated_toolboxes"] == []


def test_inspect_flags_cross_stack_duplicate():
    register_hook("shared")
    register_hook("h2")
    tb1 = make_tb("t1", hooks=["shared"])
    tb2 = make_tb("t2", hooks=["shared", "h2"])
    f = tb1.wrap(tb2.wrap(lambda: 1))
    report = ti.inspect_function(f)
    assert ("hook", "shared") in report["duplicate_pieces"]
    assert sorted(report["duplicate_pieces"][("hook", "shared")]) == ["t1", "t2"]


def test_inspect_flags_repeated_toolbox():
    register_hook("h1")
    tb = make_tb("t1", hooks=["h1"])
    f = tb.wrap(tb.wrap(lambda: 1))
    assert ti.inspect_function(f)["repeated_toolboxes"] == ["t1"]


# --- validate ---------------------------------------------------------------


def test_validate_instance_returns_pieces():
    register_hook("h1")
    tb = make_tb("t1", hooks=["h1"])
    assert ti.validate(tb)["hooks"]["before"] == ["h1"]


def test_validate_class_builds_and_returns_pieces():
    register_hook("h1")
    cls = type(
        "TBV",
        (ToolBox,),
        {
            "name": "tbv",
            "config_sources": [{"tbv": {"hooks": {"always": ["h1"]}}}],
            "features": [],
            "auto_discover": False,
        },
    )
    assert ti.validate(cls)["hooks"]["before"] == ["h1"]


def test_validate_rejects_non_toolbox():
    with pytest.raises(TypeError):
        ti.validate(42)


def test_validate_surfaces_unknown_piece():
    cls = type(
        "TBbad",
        (ToolBox,),
        {
            "name": "tbbad",
            "config_sources": [{"tbbad": {"hooks": {"always": ["nope"]}}}],
            "features": [],
            "auto_discover": False,
        },
    )
    with pytest.raises(KeyError):
        ti.validate(cls)


# --- helpers ----------------------------------------------------------------


def test_names_falls_back_to_dunder_name_for_unregistered_func():
    def stray():
        pass

    assert ti._names([stray], hook) == ["stray"]


def test_unwrap_returns_original():
    register_hook("h1")
    tb = make_tb("t1", hooks=["h1"])

    @tb
    def f():
        return 1

    assert ti._unwrap(f).__name__ == "f"


def test_render_pieces_empty():
    empty = {"hooks": {s: [] for s in ti._HOOK_STAGES}, "wrappers": [], "sinks": []}
    assert ti._render_pieces(empty) == "(no pieces)"


def test_render_pieces_includes_wrappers():
    pieces = {"hooks": {s: [] for s in ti._HOOK_STAGES}, "wrappers": ["retry"], "sinks": []}
    assert "wrappers: retry" in ti._render_pieces(pieces)


# --- rendering --------------------------------------------------------------


def test_render_shows_cross_stack_duplicate():
    register_hook("shared")
    tb1 = make_tb("t1", hooks=["shared"])
    tb2 = make_tb("t2", hooks=["shared"])
    f = tb1.wrap(tb2.wrap(lambda: 1))
    text = ti.render_inspect(ti.inspect_function(f))
    assert "duplicate pieces" in text
    assert "shared" in text


def test_render_shows_repeated_toolbox():
    register_hook("h1")
    tb = make_tb("t1", hooks=["h1"])
    f = tb.wrap(tb.wrap(lambda: 1))
    assert "applied more than once" in ti.render_inspect(ti.inspect_function(f))


def test_render_no_toolboxes():
    assert "no toolboxes attached" in ti.render_inspect(ti.inspect_function(lambda: 1))


# --- CLI --------------------------------------------------------------------


def test_cli_inspect(capsys):
    rc = ti.main(["inspect", "examples.scenarios.payments.charge"])
    assert rc == 0
    assert "payments" in capsys.readouterr().out


def test_cli_inspect_plain_function(capsys):
    rc = ti.main(["inspect", "os.getcwd"])
    assert rc == 0
    assert "no toolboxes" in capsys.readouterr().out


def test_cli_validate_ok(capsys):
    rc = ti.main(["validate", "examples.scenarios.payments.Payments"])
    assert rc == 0
    assert "OK" in capsys.readouterr().out


def test_cli_validate_non_toolbox(capsys):
    rc = ti.main(["validate", "os.getcwd"])
    assert rc == 1
    assert "INVALID" in capsys.readouterr().err


def test_cli_bad_usage():
    assert ti.main([]) == 2
    assert ti.main(["bogus", "x"]) == 2


def test_cli_resolution_errors(capsys):
    assert ti.main(["inspect", "does.not.exist"]) == 2  # ImportError
    assert ti.main(["inspect", "nodot"]) == 2  # ValueError
    assert ti.main(["inspect", "os.nope"]) == 2  # AttributeError