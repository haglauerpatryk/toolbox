"""End-to-end tests against the real wiring: config.py base + configs/ overlay + bundle."""

import logging

import pytest

import my_toolbox


def test_error_toolbox_loads_handle_problem_from_base():
    et = my_toolbox.error_toolbox
    assert "handle_problem" in [fn.__name__ for fn in et.hooks["on_error"]]


def test_error_toolbox_swallows_with_lambda():
    @my_toolbox.error_toolbox(on_error=lambda e: "recovered")
    def f():
        raise ValueError("x")

    assert f() == "recovered"


def test_error_toolbox_routes_by_type_with_catch():
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


def test_base_plus_overlay_wires_pieces():
    mt = my_toolbox.MyToolbox()
    before = [fn.__name__ for fn in mt.hooks["before"]]
    assert before == ["track_info", "track_time"]  # base + VERBOSE overlay
    assert [s.__name__ for s in mt.sinks] == ["logging_sink"]


def test_overlay_piece_surfaces_in_output(caplog):
    mt = my_toolbox.MyToolbox()

    @mt
    def do(name):
        return f"processed {name}"

    with caplog.at_level(logging.INFO, logger="toolbox"):
        assert do("widget") == "processed widget"
    messages = [r.getMessage() for r in caplog.records]
    assert any("processed widget" in m for m in messages)  # track_info AFTER summary
    assert any("RUNTIME:" in m for m in messages)  # track_time, from the configs/ overlay


def test_production_style_dict_only_omits_overlay():
    # production: hand in the base dict alone (stand-in for API JSON), no files
    from config import BASE

    prod = my_toolbox.MyToolbox(config_sources=[BASE])
    before = [fn.__name__ for fn in prod.hooks["before"]]
    assert before == ["track_info"]  # no track_time: the overlay is never read
