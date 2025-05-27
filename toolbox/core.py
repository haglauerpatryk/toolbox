import yaml
import functools
from toolbox.hooks import HookMethods, _hook_registry


class ToolBox(HookMethods):
    def __init__(self, config):
        self.config = config

        self.hooks = {
            "before": [],
            "after": [],
            "on_error": []
        }

        self._load_hooks()

    def _load_hooks(self):
        # Flatten all selected method names from config (excluding on_error for now)
        selected_methods = set()
        for label, methods in self.config.items():
            if label == "on_error":
                continue
            selected_methods.update(methods)

        # Load from registry only those that match YAML
        for name, meta in _hook_registry.items():
            if name in selected_methods or (self.config.get("on_error") and name in self.config["on_error"]):
                self.hooks[meta["stage"]].append(getattr(self, name))

    def wrap(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for method in self.hooks['before']:
                method(*args, **kwargs)

            try:
                result = func(*args, **kwargs)
                for method in self.hooks['after']:
                    method(result)
                return result
            except Exception as e:
                for method in self.hooks['on_error']:
                    method(e)
                raise

        return wrapper


# Singleton logic
def _load_config(config_path="toolbox/config.yaml"):
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

_TOOLBOX_INSTANCE = ToolBox(config=_load_config())

def light_toolbox(func):
    return _TOOLBOX_INSTANCE.wrap(func)
