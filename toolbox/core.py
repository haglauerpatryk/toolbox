import os
import yaml
import inspect
import functools
from pathlib import Path
from toolbox.hooks import HookMethods, _feature_hook_registry
from toolbox.logger import init_log_buffer, flush_logs_block
from toolbox.logic import LogicResolver
from toolbox.log_dispatcher import LogDispatcher

class ToolBox(HookMethods):
    name = "toolbox"
    log_directory = "logs"
    log_filename = "toolbox.log"
    root_dir = Path(__file__).resolve().parent.parent

    variables = {
        "DEBUG": 1
    }

    def __init__(self, global_config):
        section = global_config.get(self.name, {})
        self.config = section

        self.hooks = {
            "before": [],
            "after": [],
            "on_error": []
        }

        resolver = LogicResolver(self.variables)

        # --- Load display, on_error hooks
        for hook_type in ("display", "on_error"):
            logic_block = section.get(hook_type, {})
            hook_names = resolver.resolve_logic_block(logic_block)

            for name, entries in _feature_hook_registry.items():
                if name in hook_names:
                    for entry in entries:
                        if entry["stage"] == hook_type or (hook_type == "display" and entry["stage"] in ("before", "after")):
                            func = getattr(self, entry["func"].__name__)
                            self.hooks[entry["stage"]].append(func)

        self.log_dispatcher = None

        logic_block = section.get("log_output", {})
        resolver = LogicResolver(self.variables)
        log_outputs = resolver.resolve_logic_block(logic_block)

        self.log_dispatcher = LogDispatcher(
            enabled_outputs=log_outputs,
            file_path=self._get_log_file_path(),
            root_dir=self.root_dir
        )

    def _get_log_file_path(self):
        return f"{self.log_directory}/{self.log_filename}"

    def _load_hooks(self):
        selected_hooks = set()
        for label, features in self.config.items():
            if label == "log_output":
                continue
            selected_hooks.update(features)

        for name, entries in _feature_hook_registry.items():
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
                if self.log_dispatcher:
                    self.log_dispatcher.dispatch(func)

        return wrapper



def load_yaml_config(config_path):
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)
