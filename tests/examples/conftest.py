import time

import pytest

from examples.scenarios import llm_api
from examples.toolbox_basic import metrics, sinks, wrappers

# Pieces keep aggregate state in their own modules; reset it around every test.
_STATEFUL = (metrics, sinks, wrappers, llm_api)


@pytest.fixture(autouse=True)
def reset_piece_state():
    for mod in _STATEFUL:
        mod.reset()
    try:
        yield
    finally:
        for mod in _STATEFUL:
            mod.reset()


@pytest.fixture
def instant_retry(monkeypatch):
    """Make tenacity's wait instant (it calls time.sleep at runtime)."""
    monkeypatch.setattr(time, "sleep", lambda *a, **k: None)
