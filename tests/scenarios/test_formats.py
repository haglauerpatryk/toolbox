from toolbox.config import load_config
from toolbox.core import ToolBox
from examples.toolbox_basic import metrics, sinks

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


def test_yaml_and_json_files_deserialize_equal():
    assert load_config(f"{CONFIGS}/service.yaml") == load_config(f"{CONFIGS}/service.json")


def test_service_yaml_wires_expected_pieces():
    tb = make_service([f"{CONFIGS}/service.yaml"])
    assert before(tb) == ["track_info", "count_calls"]
    assert sink_names(tb) == ["memory"]


def test_yaml_and_json_wire_identically():
    y = make_service([f"{CONFIGS}/service.yaml"])
    j = make_service([f"{CONFIGS}/service.json"])
    assert before(y) == before(j)
    assert sink_names(y) == sink_names(j)


def test_yaml_and_json_behave_identically():
    for src in ("service.yaml", "service.json"):
        metrics.reset()
        sinks.reset()
        tb = make_service([f"{CONFIGS}/{src}"])

        @tb
        def op(x):
            return x + 1

        assert op(1) == 2
        assert metrics.counts()["op"] == 1
        assert len(sinks.collected()) == 1
