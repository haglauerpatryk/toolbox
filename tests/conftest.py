import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
import yaml

# Register the reference bundle's pieces once, before any per-test snapshot is
# taken. Core tests ignore them; feature tests reference them by name.
import examples.toolbox_basic  # noqa: E402,F401

from toolbox.config import clear_cache  # noqa: E402
from toolbox.core import ToolBox  # noqa: E402
from toolbox.registries import hook, rule, sink, wrapper  # noqa: E402

_REGISTRIES = (hook, wrapper, sink, rule)


@pytest.fixture(autouse=True)
def clean_registries():
    """Roll back any pieces a test registers, so global registries stay pristine."""
    snapshots = {reg: dict(reg._entries) for reg in _REGISTRIES}
    try:
        yield
    finally:
        for reg, snap in snapshots.items():
            reg._entries.clear()
            reg._entries.update(snap)


@pytest.fixture(autouse=True)
def clear_config_cache():
    """The config cache is a module global keyed by path; isolate it per test."""
    clear_cache()
    try:
        yield
    finally:
        clear_cache()


@pytest.fixture
def toolbox_factory(tmp_path):
    """Build a real ToolBox from a temp config, wiring named pieces via `always`.

    Exercises the genuine __init__ path (config load -> MRO merge -> selector ->
    wrap pipeline) without touching discovery or the demo's on-disk config.
    """
    counter = {"n": 0}

    def make(*, hooks=None, wrappers=None, sinks=None, variables=None):
        counter["n"] += 1
        section = f"tb_{counter['n']}"
        block = {}
        if hooks:
            block["hooks"] = {"always": list(hooks)}
        if wrappers:
            block["wrappers"] = {"always": list(wrappers)}
        if sinks:
            block["sinks"] = {"always": list(sinks)}
        path = tmp_path / f"{section}.yaml"
        path.write_text(yaml.safe_dump({section: block}))
        cls = type(
            "DynamicToolbox",
            (ToolBox,),
            {
                "name": section,
                "config_path": str(path),
                "features": [],
                "auto_discover": False,
                "variables": dict(variables or {}),
            },
        )
        return cls()

    return make
