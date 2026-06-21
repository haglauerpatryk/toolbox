import threading

import pytest

from examples.scenarios import dynamic as D
from examples.toolbox_basic import sinks


@pytest.fixture(autouse=True)
def reset_app():
    # isolate the shared live toolbox: reset to the base-logging floor each test
    D.app.reconfigure([D.BASE_LOGGING])
    yield
    D.app.reconfigure([D.BASE_LOGGING])


def before():
    return [f.__name__ for f in D.app.hooks["before"]]


def sink_names():
    return [s.__name__ for s in D.app.sinks]


def test_initial_config_is_just_base_logging():
    assert before() == []
    assert sink_names() == ["memory"]


def test_admin_push_takes_effect_on_next_call():
    D.apply_admin_config({"app": {"hooks": {"always": ["track_info", "count_calls"]}}})
    assert before() == ["track_info", "count_calls"]
    assert D.handle("hi") == "HI"


def test_push_replaces_rather_than_merges():
    D.apply_admin_config({"app": {"hooks": {"always": ["track_info"]}}})
    assert before() == ["track_info"]
    D.apply_admin_config({"app": {"hooks": {"always": ["count_calls"]}}})
    assert before() == ["count_calls"]  # track_info is gone, not merged


def test_base_logging_persists_across_swaps():
    D.apply_admin_config({"app": {"hooks": {"always": ["track_info"]}}})
    assert "memory" in sink_names()
    D.apply_admin_config({"app": {"sinks": {"always": ["terminal"]}}})
    assert sorted(sink_names()) == ["memory", "terminal"]  # base floor still there


def test_unknown_piece_is_rejected_and_old_config_stays_live():
    D.apply_admin_config({"app": {"hooks": {"always": ["track_info"]}}})
    with pytest.raises(KeyError):
        D.apply_admin_config({"app": {"hooks": {"always": ["nonexistent_piece"]}}})
    assert before() == ["track_info"]  # unchanged
    assert D.handle("ok") == "OK"  # still serving


def test_missing_handshake_is_rejected():
    with pytest.raises(ValueError, match="no matching config section"):
        D.app.reconfigure([{"WRONG_SECTION": {}}])
    assert sink_names() == ["memory"]  # old config intact


def test_in_flight_call_keeps_its_captured_config():
    sinks.reset()
    started, release = threading.Event(), threading.Event()
    out = {}

    @D.app
    def slow():
        started.set()
        assert release.wait(timeout=5)
        return "ok"

    worker = threading.Thread(target=lambda: out.__setitem__("r", slow()))
    worker.start()
    assert started.wait(timeout=5)  # call is mid-flight, holding the memory-sink config

    # admin swaps to a counter-only config while the call is in flight
    D.app.reconfigure([{"app": {"sinks": {"always": ["counter"]}}}])
    release.set()
    worker.join(timeout=5)

    assert out["r"] == "ok"
    # the in-flight call emitted to its OLD sink (memory), not the new one (counter)
    assert len(sinks.collected()) == 1
    assert sinks.emit_count() == 0

    # a fresh call now uses the new config (counter)
    @D.app
    def quick():
        return "x"

    quick()
    assert sinks.emit_count() == 1
