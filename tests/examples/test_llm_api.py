import pytest

from toolbox.core import ToolBox
from examples.scenarios import llm_api as L
from examples.toolbox_basic import metrics


@pytest.fixture(autouse=True)
def audit_and_fast(monkeypatch, tmp_path, instant_retry):
    monkeypatch.setattr(L.llm, "log_directory", str(tmp_path))
    return tmp_path


def test_flaky_response_self_heals_via_retry_and_validate():
    out = L.ask("q1")
    assert out == {"answer": "answer to 'q1'", "confidence": 0.92}
    assert L._attempts["q1"] == 2  # malformed once, valid on retry


def test_count_calls_fires_once_per_request_not_per_retry():
    # count_calls is a before-hook (per request); retry re-runs only the wrapped body
    L.ask("q2")
    assert metrics.counts()["ask"] == 1
    assert L._attempts["q2"] == 2


def test_unfixable_response_falls_back_safely():
    out = L.ask_unfixable("q3")
    assert out["answer"] is None
    assert out["confidence"] == 0.0
    assert "Error" in out["error"]  # RetryError wrapping the FormatError


def test_rate_limit_trips_to_fallback(monkeypatch, tmp_path):
    strict = type(
        "StrictLLM",
        (ToolBox,),
        {
            "name": "llm",
            "config_sources": [L.LLM_CONFIG],
            "features": ["examples.toolbox_basic"],
            "auto_discover": False,
            "variables": {"RATE_LIMIT": 1, "REQUIRED_KEYS": L.REQUIRED_KEYS},
        },
    )()
    monkeypatch.setattr(strict, "log_directory", str(tmp_path))

    @strict(on_error=L._FALLBACK)
    def ask_strict(prompt):
        return {"answer": "a", "confidence": 1.0}

    assert ask_strict("x")["answer"] == "a"  # first call within the limit
    out = ask_strict("y")  # second exceeds RATE_LIMIT=1
    assert out["answer"] is None
    assert "ask_strict exceeded" in out["error"]  # name preserved through the chain
