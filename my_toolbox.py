"""
Ponizej widac podstawowy 'setup' dla tego narzedzia w Pythonie. Jak widac, posiada wsparcie dla dziedziczenia
oraz dodawania wlasnych zmiennych konfiguracyjnych.
"""

from toolbox.core import ToolBox

class MyToolbox(ToolBox):
    name = "my_toolbox" # nazwa dla .yaml
    config_path = "config.yaml"

    variables = {
        "DEBUG": 1
    }

    def __init__(self):
        super().__init__(config_path=self.config_path)


my_toolbox_instance = MyToolbox()

class ErrorToolbox(MyToolbox):
    name = "error_toolbox"

error_toolbox_instance = ErrorToolbox()

def light_toolbox(func):
    return error_toolbox_instance.wrap(func)