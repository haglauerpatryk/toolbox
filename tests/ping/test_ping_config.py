import pytest

from toolbox import wrapper
from ping.core import Ping


def test_default_ping_builds_from_its_own_config():
    p = Ping()
    before = [getattr(f, "__name__", "") for f in p.hooks["before"]]
    assert p.name == "ping"
    assert "ping_time" in before
    assert "ping_args" in before


def test_wrappers_are_rejected(tmp_path):
    wrapper.register("noop_w")(lambda f: f)
    cfg = {"ping": {"wrappers": {"always": ["noop_w"]}}}
    with pytest.raises(ValueError, match="does not support wrappers"):
        Ping(config_sources=[cfg], targets_path=str(tmp_path / "t.json"))
