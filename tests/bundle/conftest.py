import pytest

from examples.toolbox_basic import metrics, sinks, wrappers

# The reference pieces keep aggregate state in their own modules (call counts,
# collectors, memo/rate tables); reset it around every test so cases stay isolated.
_STATEFUL = (metrics, sinks, wrappers)


@pytest.fixture(autouse=True)
def reset_piece_state():
    for mod in _STATEFUL:
        mod.reset()
    try:
        yield
    finally:
        for mod in _STATEFUL:
            mod.reset()
