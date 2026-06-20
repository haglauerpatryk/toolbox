"""Dynamic config: hot-swap a live toolbox's config from an admin API, safely.

Production ships a base logging config (always on). When the admin panel pushes a
new config, `reconfigure` *replaces* the live config wholesale — base logging is
re-included as the floor, the dynamic section is swapped in, and a bad payload is
rejected before anything changes, so the running app never breaks.

`apply_admin_config` stands in for the admin-panel endpoint. Composing the source
list (always putting base logging first) is the app's job, not the framework's.
"""

from toolbox import ToolBox

BASE_LOGGING = "examples/configs/logging.yaml"  # the always-on floor, in YAML


class App(ToolBox):
    name = "app"
    config_sources = [BASE_LOGGING]
    features = ["examples.toolbox_basic"]


app = App()


@app
def handle(request):
    return request.upper()


def apply_admin_config(dynamic):
    """Stand-in for the admin-panel API call: replace the live config wholesale.

    Base logging is always re-included as the floor; the dynamic section is a dict
    (e.g. parsed from the request body). A bad payload raises and the live config
    is left untouched.
    """
    app.reconfigure([BASE_LOGGING, dynamic])
