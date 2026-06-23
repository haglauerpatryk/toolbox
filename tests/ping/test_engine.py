"""End-to-end: enable ping over real functions and assert what it observed —
and, crucially, that it changed nothing about the call."""

import json

import pytest

from toolbox import sink
from ping.core import Ping


def _ping(tmp_path, hooks, sinks, **targets):
    targets.setdefault("enabled", True)
    block = {}
    if hooks:
        block["hooks"] = {"always": hooks}
    if sinks:
        block["sinks"] = {"always": sinks}
    tpath = tmp_path / "targets.json"
    tpath.write_text(json.dumps(targets))
    return Ping(config_sources=[{"ping": block}], targets_path=str(tpath))


def test_success_is_observed_and_result_unchanged(tmp_path, restore_trace):
    seen = []
    sink.register("rec")(lambda ctx: seen.append((ctx.result, ctx.exception, list(ctx.messages))))

    def target_ok(a, b):
        return a + b

    p = _ping(tmp_path, ["ping_time"], ["rec"], functions=["target_ok"])
    p.enable()
    try:
        result = target_ok(2, 3)
    finally:
        p.disable()

    assert result == 5
    assert len(seen) == 1
    res, exc, msgs = seen[0]
    assert res == 5 and exc is None
    assert any("time=" in m for m in msgs)


def test_exception_is_observed_and_propagates_unchanged(tmp_path, restore_trace):
    seen = []
    sink.register("rec2")(lambda ctx: seen.append((ctx.result, ctx.exception)))

    def target_boom():
        raise ValueError("boom")

    p = _ping(tmp_path, ["ping_error"], ["rec2"], functions=["target_boom"])
    p.enable()
    try:
        with pytest.raises(ValueError, match="boom"):
            target_boom()
    finally:
        p.disable()

    assert len(seen) == 1
    res, exc = seen[0]
    assert res is None and isinstance(exc, ValueError)


def test_caught_exception_is_not_a_failure(tmp_path, restore_trace):
    seen = []
    sink.register("rec3")(lambda ctx: seen.append((ctx.result, ctx.exception)))

    def target_caught():
        try:
            raise KeyError("x")
        except KeyError:
            return "recovered"

    p = _ping(tmp_path, [], ["rec3"], functions=["target_caught"])
    p.enable()
    try:
        out = target_caught()
    finally:
        p.disable()

    assert out == "recovered"
    assert seen == [("recovered", None)]


def test_unmatched_function_is_inert(tmp_path, restore_trace):
    seen = []
    sink.register("rec4")(lambda ctx: seen.append(ctx))

    def other():
        return 1

    p = _ping(tmp_path, ["ping_time"], ["rec4"], functions=["something_else"])
    p.enable()
    try:
        other()
    finally:
        p.disable()

    assert seen == []


def test_disabled_targets_are_inert(tmp_path, restore_trace):
    seen = []
    sink.register("rec5")(lambda ctx: seen.append(ctx))

    def target_off():
        return 1

    p = _ping(tmp_path, ["ping_time"], ["rec5"], functions=["target_off"], enabled=False)
    p.enable()
    try:
        target_off()
    finally:
        p.disable()

    assert seen == []
