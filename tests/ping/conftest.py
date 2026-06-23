import sys

import pytest

import ping  # noqa: F401  registers ping's diagnostic pieces before the registry snapshot


@pytest.fixture
def restore_trace():
    """Save/restore the ambient trace function so enabling ping in a test does
    not leave coverage's (or anything else's) tracer disabled afterwards."""
    prev = sys.gettrace()
    try:
        yield
    finally:
        sys.settrace(prev)
