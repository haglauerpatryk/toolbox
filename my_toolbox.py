from toolbox.core import ToolBox, load_yaml_config

class MyToolbox(ToolBox):
    name = "my_toolbox"
    config_path = "toolbox/config.yaml"

    def __init__(self):
        global_config = load_yaml_config(self.config_path)
        super().__init__(global_config=global_config)

my_toolbox_instance = MyToolbox()

def light_toolbox(func):
    return my_toolbox_instance.wrap(func)