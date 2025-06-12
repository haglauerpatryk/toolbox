from toolbox.core import ToolBox, load_yaml_config

class MyToolbox(ToolBox):
    name = "my_toolbox"
    config_path = "toolbox/config.yaml"

    def __init__(self):
        super().__init__(config_path=self.config_path)


my_toolbox_instance = MyToolbox()

class ErrorToolbox(MyToolbox):
    name = "error_toolbox"

error_toolbox_instance = ErrorToolbox()

def light_toolbox(func):
    return error_toolbox_instance.wrap(func)