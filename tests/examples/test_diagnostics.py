from toolbox.core import ToolBox
from examples.scenarios import diagnostics as D
from examples.scenarios.diagnostics import DIAGNOSTICS
from examples.toolbox_basic import metrics, sinks


def test_transform_returns_and_is_fully_observed():
    assert D.transform("hi", upper=True) == "HI"
    records = sinks.collected()
    assert len(records) == 1
    rec = records[0]
    assert rec["func"] == "transform"
    assert rec["result"] == "HI"
    lines = rec["lines"]
    assert any("[COUNT]" in line for line in lines)
    assert any("[ARGS]" in line for line in lines)
    assert any("RUNTIME:" in line for line in lines)  # track_time, gated by VERBOSE


def test_transform_lowercase_branch():
    assert D.transform("HI") == "HI"
    assert D.transform("Hi", upper=False) == "Hi"


def test_count_accumulates_across_calls():
    D.transform("a")
    D.transform("b")
    assert metrics.counts()["transform"] == 2


def test_verbose_off_drops_timing_pieces():
    quiet = type(
        "Quiet",
        (ToolBox,),
        {
            "name": "diagnostics",
            "config_sources": [DIAGNOSTICS],
            "features": ["examples.toolbox_basic"],
            "auto_discover": False,
            "variables": {},  # VERBOSE absent -> if_var pieces drop out
        },
    )()
    before = [f.__name__ for f in quiet.hooks["before"]]
    assert "track_time" not in before
    assert "count_calls" in before  # always-pieces remain
