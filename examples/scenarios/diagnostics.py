"""Dev diagnostics: a minimal toolbox that makes a function fully observable.

Counts, argument capture, timing, and slow-call warnings, fanned out to an
in-memory collector and the terminal. Verbosity is gated by a plain user
variable — flip VERBOSE off and the timing pieces simply drop out.
"""

from toolbox import ToolBox

DIAGNOSTICS = {
    "diagnostics": {
        "hooks": {
            "always": ["count_calls", "capture_args", "track_info"],
            "if_var": {"VERBOSE": ["track_time", "slow_warning"]},
        },
        "sinks": {"always": ["memory", "terminal"]},
    }
}


class Diagnostics(ToolBox):
    name = "diagnostics"
    config_sources = [DIAGNOSTICS]
    features = ["examples.toolbox_basic"]
    variables = {"VERBOSE": 1, "SLOW_MS": 10}


diagnostics = Diagnostics()


@diagnostics
def transform(value, *, upper=False):
    text = str(value)
    return text.upper() if upper else text
