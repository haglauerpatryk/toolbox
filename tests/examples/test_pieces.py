import json
from contextlib import contextmanager
from time import perf_counter

import pytest

from toolbox.context import CallContext, _current
from examples.toolbox_basic import metrics, rules, sinks, wrappers


class FakeToolbox:
    def __init__(self, log_directory=None, **variables):
        self.log_directory = log_directory
        self.variables = variables


@contextmanager
def active_context(func, **variables):
    ctx = CallContext(func=func, toolbox=FakeToolbox(**variables))
    token = _current.set(ctx)
    try:
        yield ctx
    finally:
        _current.reset(token)


def ctx_for(func=None, **kw):
    return CallContext(func=func or (lambda: None), **kw)


# --- metrics hooks ----------------------------------------------------------


def test_count_calls_increments_per_func():
    def a():
        pass

    metrics.count_calls(ctx_for(a))
    c = ctx_for(a)
    metrics.count_calls(c)
    assert metrics.counts()["a"] == 2
    assert any("call #2" in line for line in c.buffer)


def test_capture_args_logs_args_and_kwargs():
    c = ctx_for(args=(1, 2), kwargs={"k": 3})
    metrics.capture_args(c)
    assert any("[ARGS]" in line and "k" in line for line in c.buffer)


def test_slow_warning_fires_over_threshold():
    c = ctx_for(toolbox=FakeToolbox(SLOW_MS=10))
    c.scratch["start"] = perf_counter() - 1.0  # ~1000ms ago
    metrics.slow_warning(c)
    assert any("[SLOW]" in line for line in c.buffer)


def test_slow_warning_silent_under_threshold():
    c = ctx_for(toolbox=FakeToolbox(SLOW_MS=100000))
    c.scratch["start"] = perf_counter()
    metrics.slow_warning(c)
    assert c.buffer == []


def test_slow_warning_noop_without_start():
    c = ctx_for(toolbox=FakeToolbox(SLOW_MS=1))
    metrics.slow_warning(c)
    assert c.buffer == []


def test_slow_warning_default_threshold_without_variables():
    c = ctx_for(toolbox=None)  # no variables -> default 1000ms, fast -> silent
    c.scratch["start"] = perf_counter()
    metrics.slow_warning(c)
    assert c.buffer == []


# --- sinks ------------------------------------------------------------------


def test_memory_records_structured_entry():
    c = ctx_for()
    c.result = "r"
    c.buffer.append("x")
    sinks.memory(c)
    rec = sinks.collected()[0]
    assert rec == {"func": "<lambda>", "lines": ["x"], "result": "r", "exception": None}


def test_counter_counts_emissions():
    sinks.counter(ctx_for())
    sinks.counter(ctx_for())
    assert sinks.emit_count() == 2


def test_json_lines_writes_success_record(tmp_path):
    c = ctx_for(toolbox=FakeToolbox(log_directory=str(tmp_path)))
    c.result = {"a": 1}
    c.buffer.append("log1")
    sinks.json_lines(c)
    rec = json.loads((tmp_path / "events.jsonl").read_text().strip())
    assert rec["ok"] is True
    assert rec["result"] == {"a": 1}
    assert rec["log"] == ["log1"]
    assert rec["error"] is None


def test_json_lines_writes_error_record(tmp_path):
    c = ctx_for(toolbox=FakeToolbox(log_directory=str(tmp_path)), exception=ValueError("boom"))
    sinks.json_lines(c)
    rec = json.loads((tmp_path / "events.jsonl").read_text().strip())
    assert rec["ok"] is False
    assert rec["error"] == "boom"


def test_json_lines_non_serializable_result_falls_back(tmp_path):
    sentinel = object()
    c = ctx_for(toolbox=FakeToolbox(log_directory=str(tmp_path)))
    c.result = sentinel
    sinks.json_lines(c)
    rec = json.loads((tmp_path / "events.jsonl").read_text().strip())
    assert isinstance(rec["result"], str)  # repr fallback


# --- wrappers ---------------------------------------------------------------


def test_memoize_caches_by_args():
    calls = []

    def f(x):
        calls.append(x)
        return x * 2

    wrapped = wrappers.memoize(f)
    assert wrapped(3) == 6
    assert wrapped(3) == 6  # cached
    assert wrapped(4) == 8
    assert calls == [3, 4]


def test_rate_limit_allows_within_limit():
    def f():
        return "ok"

    wrapped = wrappers.rate_limit(f)
    with active_context(f, RATE_LIMIT=2):
        assert wrapped() == "ok"
        assert wrapped() == "ok"


def test_rate_limit_raises_when_exceeded():
    def f():
        return "ok"

    wrapped = wrappers.rate_limit(f)
    with active_context(f, RATE_LIMIT=1):
        wrapped()
        with pytest.raises(wrappers.RateLimitExceeded):
            wrapped()


def test_validate_passes_with_required_keys():
    def f():
        return {"answer": 1, "confidence": 2}

    with active_context(f, REQUIRED_KEYS=["answer", "confidence"]):
        assert wrappers.validate(f)() == {"answer": 1, "confidence": 2}


def test_validate_raises_on_missing_key():
    def f():
        return {"answer": 1}

    with active_context(f, REQUIRED_KEYS=["answer", "confidence"]):
        with pytest.raises(wrappers.FormatError, match="missing keys"):
            wrappers.validate(f)()


def test_validate_raises_on_non_dict():
    def f():
        return "not a dict"

    with active_context(f, REQUIRED_KEYS=["answer"]):
        with pytest.raises(wrappers.FormatError, match="expected dict"):
            wrappers.validate(f)()


def test_validate_passes_when_no_required_keys_configured():
    # no active context -> _variables() returns {} -> nothing to validate
    def f():
        return "anything"

    assert wrappers.validate(f)() == "anything"


# --- custom rules -----------------------------------------------------------


def test_if_env_included_when_set(monkeypatch):
    monkeypatch.setenv("TOOLBOX_FLAG", "1")
    assert rules.if_env({}, {"TOOLBOX_FLAG": ["x"]}) == ["x"]


def test_if_env_excluded_when_unset(monkeypatch):
    monkeypatch.delenv("TOOLBOX_FLAG", raising=False)
    assert rules.if_env({}, {"TOOLBOX_FLAG": ["x"]}) == []


def test_if_equals_matches_value():
    payload = {"ENV": {"prod": ["p"], "dev": ["d"]}}
    assert rules.if_equals({"ENV": "prod"}, payload) == ["p"]


def test_if_equals_no_match():
    assert rules.if_equals({"ENV": "staging"}, {"ENV": {"prod": ["p"]}}) == []
