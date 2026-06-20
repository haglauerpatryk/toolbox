from toolbox.core import ToolBox
from examples.configs.base import BASE

CONFIGS = "examples/configs"


def make_service(sources):
    cls = type(
        "Service",
        (ToolBox,),
        {
            "name": "service",
            "config_sources": sources,
            "features": ["examples.toolbox_basic"],
            "auto_discover": False,
        },
    )
    return cls()


def before(tb):
    return [f.__name__ for f in tb.hooks["before"]]


def sink_names(tb):
    return [s.__name__ for s in tb.sinks]


def test_python_base_plus_overlay_directory_merges_in_order():
    # BASE: hooks [track_info], sinks [memory]
    # overlays/10-logging.yaml adds sink terminal; 20-metrics.yaml adds hook count_calls
    tb = make_service([BASE, f"{CONFIGS}/overlays/"])
    assert before(tb) == ["track_info", "count_calls"]
    assert sink_names(tb) == ["memory", "terminal"]  # base, then 10- before 20-


def test_production_json_file_is_self_contained():
    tb = make_service([f"{CONFIGS}/prod.json"])
    assert before(tb) == ["track_info"]
    assert sink_names(tb) == ["json_lines"]  # no dev sinks


def test_mixed_dict_yaml_json_sources():
    # dict base + a yaml service file would overlap on memory/track_info -> see dedupe
    tb = make_service([{"service": {"hooks": {"always": ["capture_args"]}}}, f"{CONFIGS}/prod.json"])
    assert before(tb) == ["capture_args", "track_info"]
    assert sink_names(tb) == ["json_lines"]


def test_overlapping_sources_are_deduped_with_warning(capsys):
    # BASE and service.yaml both declare track_info + memory -> duplicates dropped
    tb = make_service([BASE, f"{CONFIGS}/service.yaml"])
    assert before(tb) == ["track_info", "count_calls"]
    assert sink_names(tb) == ["memory"]
    err = capsys.readouterr().err
    assert "removed duplicate hook" in err and "track_info" in err
    assert "removed duplicate sink" in err and "memory" in err


def test_order_decides_precedence_for_scalars():
    # a later source overrides a scalar from an earlier one
    tb = make_service(
        [
            {"service": {"hooks": {"always": ["track_info"]}, "tier": "base"}},
            {"service": {"tier": "override"}},
        ]
    )
    assert before(tb) == ["track_info"]  # list survived the scalar override
