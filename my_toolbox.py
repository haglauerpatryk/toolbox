from toolbox import ToolBox


class MyToolbox(ToolBox):
    name = "my_toolbox"
    config_path = "config.yaml"
    features = ["examples.toolbox_basic"]
    variables = {
        "DEBUG": 1,
    }


class ErrorToolbox(MyToolbox):
    name = "error_toolbox"


error_toolbox = ErrorToolbox()
