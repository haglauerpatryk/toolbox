from toolbox import ToolBox

from config import BASE


class MyToolbox(ToolBox):
    name = "my_toolbox"
    # Order is the only precedence rule: the Python base first, then the local
    # yaml directory layers on top. In production you would instead pass a single
    # config dict (e.g. JSON fetched from an API) and omit the file sources —
    # compose this list however you like, e.g. behind a trivial `if`.
    config_sources = [BASE, "configs/"]
    features = ["examples.toolbox_basic"]
    # A plain user variable; the framework has no built-in notion of DEBUG.
    variables = {"VERBOSE": 1}


class ErrorToolbox(MyToolbox):
    name = "error_toolbox"


error_toolbox = ErrorToolbox()
