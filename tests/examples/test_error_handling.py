import pytest

from examples.scenarios import error_handling as EH
from examples.toolbox_basic import sinks


# 1. failover with the same arguments
def test_failover_to_backup_with_same_args():
    assert EH.fetch_region("eu-west") == {"region": "eu-west", "source": "secondary"}


def test_failover_propagates_if_backup_also_fails(monkeypatch):
    def boom(region):
        raise ValueError(f"secondary also down: {region}")

    monkeypatch.setattr(EH, "_secondary_region", boom)
    with pytest.raises(ValueError, match="secondary also down"):
        EH.fetch_region("eu-west")


# 2. degrade to cache
def test_degrade_to_cached_value():
    EH.CACHE["AAPL"] = 199.5
    assert EH.get_price("AAPL") == 199.5


def test_degrade_cache_miss_returns_none():
    assert EH.get_price("UNKNOWN") is None


# 3. best-effort passthrough
def test_best_effort_passthrough():
    assert EH.normalize("  HeLLo ") == "hello"
    assert EH.normalize(123) == 123  # transform fails -> input returned unchanged


# 4. dead-letter handoff
def test_dead_letter_handoff():
    out = EH.process_job("job-7")
    assert out == {"status": "deferred"}
    assert EH.DEAD_LETTER == [{"job": "job-7", "error": "worker crashed on job-7"}]


# 5. observe then propagate
def test_observe_then_propagate():
    with pytest.raises(ValueError, match="invariant violated"):
        EH.critical_op()
    assert EH.ALERTS == ["ValueError: invariant violated"]


# 6. conditional re-raise
def test_conditional_reraise_propagates_retryable():
    with pytest.raises(TimeoutError):
        EH.sync_record("flaky")


def test_conditional_reraise_swallows_terminal():
    assert EH.sync_record("bad") == {"status": "skipped", "reason": "malformed: bad"}


# 7. sanitize before propagating
def test_sanitize_hides_internal_detail_but_keeps_cause():
    with pytest.raises(EH.ServiceError) as info:
        EH.charge_account("acct-1", "s3cr3t")
    assert "s3cr3t" not in str(info.value)  # secret never reaches the caller
    assert isinstance(info.value.__cause__, RuntimeError)
    assert "s3cr3t" in str(info.value.__cause__)  # but preserved for server logs


# 8. result envelope
def test_result_envelope_success():
    assert EH.divide(10, 2) == {"ok": True, "value": 5.0}


def test_result_envelope_failure():
    assert EH.divide(10, 0) == {"ok": False, "error": "division by zero"}


# 9. boundary mapping via catch
@pytest.mark.parametrize(
    "route, status",
    [("ok", 200), ("missing", 404), ("private", 403), ("boom", 500)],
)
def test_boundary_mapping(route, status):
    assert EH.handle_request(route).status == status


# the on_error lambda doesn't disable the configured logging
def test_on_error_hook_still_logs_when_lambda_recovers():
    sinks.reset()
    EH.divide(1, 0)  # recovered by the lambda, but the error is still observed
    logged = sinks.collected()[-1]["lines"]
    assert any("[ERROR] Caught" in line for line in logged)
