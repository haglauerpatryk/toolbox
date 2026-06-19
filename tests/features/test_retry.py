import time

import pytest
import tenacity

from toolbox.context import CallContext, _current
from toolbox.registries import wrapper


def build_retry(func):
    """Apply the registered retry piece and neutralize its sleeping."""
    wrapped = wrapper.get("retry").func(func)
    wrapped.retry.sleep = lambda *a, **k: None  # deterministic, no wall-clock waits
    return wrapped


def test_retry_succeeds_on_first_attempt():
    calls = []
    wrapped = build_retry(lambda: calls.append(1) or "ok")
    assert wrapped() == "ok"
    assert len(calls) == 1


def test_retry_recovers_before_exhaustion():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ValueError("transient")
        return "ok"

    wrapped = build_retry(flaky)
    assert wrapped() == "ok"
    assert len(calls) == 3


def test_retry_exhausts_after_three_attempts_and_raises_retryerror():
    calls = []

    def always_fails():
        calls.append(1)
        raise ValueError("permanent")

    wrapped = build_retry(always_fails)
    with pytest.raises(tenacity.RetryError):
        wrapped()
    assert len(calls) == 3


def test_retry_logs_each_failed_attempt_to_context_buffer():
    ctx = CallContext(func=lambda: None)
    token = _current.set(ctx)
    try:
        wrapped = build_retry(lambda: (_ for _ in ()).throw(ValueError("x")))
        with pytest.raises(tenacity.RetryError):
            wrapped()
    finally:
        _current.reset(token)
    retry_lines = [line for line in ctx.buffer if "[RETRY]" in line]
    assert len(retry_lines) == 2  # logged before each of the two re-sleeps


def test_retry_is_configured_for_three_attempts_and_one_second_waits():
    wrapped = wrapper.get("retry").func(lambda: None)
    assert wrapped.retry.stop.max_attempt_number == 3
    assert wrapped.retry.wait.wait_fixed == 1


@pytest.mark.slow
def test_retry_real_timing_sleeps_between_attempts():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 2:
            raise ValueError("transient")
        return "ok"

    wrapped = wrapper.get("retry").func(flaky)  # real tenacity sleep, no patch
    start = time.perf_counter()
    assert wrapped() == "ok"
    elapsed = time.perf_counter() - start
    assert elapsed >= 1.0  # one real wait_fixed(1) between the two attempts
    assert len(calls) == 2
