"""End-to-end tests against the real wiring: config.yaml + the toolbox_basic bundle."""

import pytest

import my_toolbox


def test_error_toolbox_loads_handle_problem_from_real_config():
    et = my_toolbox.error_toolbox
    names = [fn.__name__ for fn in et.hooks["on_error"]]
    assert "handle_problem" in names


def test_error_toolbox_swallows_with_lambda():
    @my_toolbox.error_toolbox(on_error=lambda e: "recovered")
    def f():
        raise ValueError("x")

    assert f() == "recovered"


def test_error_toolbox_routes_by_type_with_catch(capsys):
    from examples.toolbox_basic import catch

    @my_toolbox.error_toolbox(
        on_error=catch(
            {
                ValueError: lambda e: "<bad input>",
                KeyError: lambda e: e,
                Exception: lambda e: RuntimeError(f"unexpected: {e}"),
            }
        )
    )
    def routed(exc):
        raise exc

    assert routed(ValueError("bad")) == "<bad input>"

    with pytest.raises(KeyError):
        routed(KeyError("missing"))

    with pytest.raises(RuntimeError) as info:
        routed(ZeroDivisionError("/0"))
    assert isinstance(info.value.__cause__, ZeroDivisionError)


def test_my_toolbox_debug_pipeline_logs_via_terminal(capsys):
    mt = my_toolbox.MyToolbox()  # DEBUG=1 -> track_info + track_time + terminal sink

    @mt
    def do(name):
        return f"processed {name}"

    assert do("widget") == "processed widget"
    out = capsys.readouterr().out
    assert "processed widget" in out  # [AFTER] summary line surfaced by terminal sink
    assert "RUNTIME:" in out  # track_time fired under DEBUG


def test_my_toolbox_real_pieces_are_wired():
    mt = my_toolbox.MyToolbox()
    before_names = [fn.__name__ for fn in mt.hooks["before"]]
    assert "track_info" in before_names
    assert "track_time" in before_names  # DEBUG=1
    assert [s.__name__ for s in mt.sinks] == ["terminal"]
