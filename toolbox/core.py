import os
import yaml
import inspect
import functools
from pathlib import Path
from toolbox.hooks import HookMethods, _hook_registry
from toolbox.logger import init_log_buffer, flush_logs_block

class ToolBox(HookMethods):
    log_directory = "logs"
    log_filename = "toolbox.log"
    root_dir = Path(__file__).resolve().parent.parent

    def __init__(self, config):
        self.config = config
        self.hooks = {
            "before": [],
            "after": [],
            "on_error": []
        }

        log_cfg = config.get("log_output", {})
        self.log_to_terminal = log_cfg.get("terminal", False)
        self.log_to_file = log_cfg.get("file", False)

        self._load_hooks()

    def _get_log_file_path(self):
        return f"{self.log_directory}/{self.log_filename}"

    def _load_hooks(self):
        selected_hooks = set()
        for label, features in self.config.items():
            if label == "log_output":
                continue
            selected_hooks.update(features)

        for name, entries in _hook_registry.items():
            if name in selected_hooks:
                for entry in entries:
                    stage = entry["stage"]
                    func = getattr(self, entry["func"].__name__)
                    self.hooks[stage].append(func)

    def wrap(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            context = {}
            init_log_buffer()

            for method in self.hooks['before']:
                method(*args, context=context, **kwargs)

            try:
                result = func(*args, **kwargs)
                for method in self.hooks['after']:
                    method(result, context=context)
                return result
            except Exception as e:
                for method in self.hooks['on_error']:
                    method(e, context=context)
                raise
            finally:
                flush_logs_block(
                    func,
                    to_terminal=self.log_to_terminal,
                    to_file=self.log_to_file,
                    file_path=self._get_log_file_path(),
                    root_dir=self.root_dir
                )

        return wrapper



# Load config once
def _load_config(config_path="toolbox/config.yaml"):
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

_TOOLBOX_INSTANCE = ToolBox(config=_load_config())

def light_toolbox(func):
    return _TOOLBOX_INSTANCE.wrap(func)
