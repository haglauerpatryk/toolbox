import os
import yaml
import inspect
import functools
from pathlib import Path
from toolbox.hooks import HookMethods, _feature_hook_registry
from toolbox.logger import init_log_buffer, flush_logs_block
from toolbox.logic import LogicResolver
from toolbox.log_dispatcher import LogDispatcher
from toolbox.decorators import _decorator_registry


from copy import deepcopy

_yaml_cache = None

def load_yaml_config(path="toolbox/config.yaml"):
    global _yaml_cache
    if _yaml_cache is None:
        with open(path, 'r') as f:
            _yaml_cache = yaml.safe_load(f)
    return _yaml_cache or {}

def resolve_toolbox_config(cls, config_data):
    merged = {}

    for base in reversed(cls.__mro__):
        if not issubclass(base, ToolBox) or base is ToolBox:
            continue
        section_name = getattr(base, "name", None)
        if not section_name:
            continue
        section = config_data.get(section_name, {})
        merged = deep_merge_dicts(merged, section)

    return merged

def deep_merge_dicts(a, b):
    result = deepcopy(a)
    for k, v in b.items():
        if k in result:
            if isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = deep_merge_dicts(result[k], v)
            elif isinstance(result[k], list) and isinstance(v, list):
                result[k].extend(v)
            else:
                result[k] = deepcopy(v)
        else:
            result[k] = deepcopy(v)
    return result


class ToolBox(HookMethods):
    name = "toolbox"
    log_directory = "logs"
    log_filename = "toolbox.log"
    root_dir = Path(__file__).resolve().parent.parent

    variables = {
        "DEBUG": 1
    }

    def __init__(self, config_path="toolbox/config.yaml"):
        config_data = load_yaml_config(config_path)
        self.config = resolve_toolbox_config(self.__class__, config_data)

        self.hooks = {
            "before": [],
            "after": [],
            "on_error": []
        }

        resolver = LogicResolver(self.variables)

        # --- Load display, on_error hooks
        for hook_type in ("display", "on_error"):
            logic_block = self.config.get(hook_type, {})
            hook_names = resolver.resolve_logic_block(logic_block)

            for name, entries in _feature_hook_registry.items():
                if name in hook_names:
                    for entry in entries:
                        if entry["stage"] == hook_type or (hook_type == "display" and entry["stage"] in ("before", "after")):
                            func = getattr(self, entry["func"].__name__)
                            self.hooks[entry["stage"]].append(func)

        self.log_dispatcher = None

        logic_block = self.config.get("log_output", {})
        resolver = LogicResolver(self.variables)
        log_outputs = resolver.resolve_logic_block(logic_block)

        self.log_dispatcher = LogDispatcher(
            enabled_outputs=log_outputs,
            file_path=self._get_log_file_path(),
            root_dir=self.root_dir
        )

        self.middle_decorators = []
        decorator_block = self.config.get("decorators", {})
        decorator_names = resolver.resolve_logic_block(decorator_block)

        for name in decorator_names:
            if name in _decorator_registry:
                self.middle_decorators.append(_decorator_registry[name])

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
        def wrapped(*args, **kwargs):
            context = {}
            init_log_buffer()

            for method in self.hooks['before']:
                method(*args, context=context, **kwargs)

            try:
                decorated_func = func
                for decorator in reversed(self.middle_decorators):
                    decorated_func = decorator(decorated_func)

                result = decorated_func(*args, **kwargs)

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

        return wrapped



def load_yaml_config(config_path):
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)
