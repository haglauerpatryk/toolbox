import functools
from copy import deepcopy
from pathlib import Path

import yaml

from toolbox.context import CallContext, _current
from toolbox.discovery import discover
from toolbox.registries import hook, sink, wrapper
from toolbox.selectors import Selector

_yaml_cache = {}


def load_yaml_config(path):
    if path not in _yaml_cache:
        with open(path, "r") as f:
            _yaml_cache[path] = yaml.safe_load(f) or {}
    return _yaml_cache[path]


def deep_merge_dicts(a, b):
    result = deepcopy(a)
    for k, v in b.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge_dicts(result[k], v)
        elif k in result and isinstance(result[k], list) and isinstance(v, list):
            result[k] = result[k] + deepcopy(v)
        else:
            result[k] = deepcopy(v)
    return result


def resolve_toolbox_config(cls, config_data):
    merged = {}
    for base in reversed(cls.__mro__):
        if not issubclass(base, ToolBox) or base is ToolBox:
            continue
        section_name = getattr(base, "name", None)
        if not section_name:
            continue
        merged = deep_merge_dicts(merged, config_data.get(section_name, {}))
    return merged


class ToolBox:
    name = "toolbox"
    config_path = "config.yaml"
    log_directory = "logs"
    log_filename = "toolbox.log"
    root_dir = Path(__file__).resolve().parent.parent
    variables = {}
    features = []
    auto_discover = True

    def __init__(self):
        discover(self.features, auto=self.auto_discover)

        config_data = load_yaml_config(self.config_path)
        section = resolve_toolbox_config(type(self), config_data)
        selector = Selector(self.variables)

        self.hooks = {"before": [], "after": [], "on_error": []}
        for name in selector.resolve(section.get("hooks", {})):
            entry = hook.get(name)
            for stage in entry.meta.get("stages", ()):
                self.hooks[stage].append(entry.func)

        self.wrappers = [wrapper.get(n).func for n in selector.resolve(section.get("wrappers", {}))]
        self.sinks = [sink.get(n).func for n in selector.resolve(section.get("sinks", {}))]

    @property
    def log_path(self):
        return f"{self.log_directory}/{self.log_filename}"

    @property
    def _active(self):
        return bool(
            self.hooks["before"]
            or self.hooks["after"]
            or self.hooks["on_error"]
            or self.wrappers
            or self.sinks
        )

    def wrap(self, func, on_error=None):
        if not self._active and on_error is None:
            return func

        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            ctx = CallContext(func=func, args=args, kwargs=kwargs, toolbox=self)
            token = _current.set(ctx)
            try:
                ctx.stage = "before"
                for method in self.hooks["before"]:
                    method(ctx)

                inner = func
                for w in reversed(self.wrappers):
                    inner = w(inner)

                try:
                    ctx.result = inner(*args, **kwargs)
                    ctx.stage = "after"
                    for method in self.hooks["after"]:
                        method(ctx)
                    return ctx.result
                except Exception as e:
                    ctx.exception = e
                    ctx.stage = "on_error"
                    for method in self.hooks["on_error"]:
                        method(ctx)
                    if on_error is None:
                        raise
                    outcome = on_error(e)
                    if isinstance(outcome, BaseException):
                        if outcome is e:
                            raise
                        raise outcome from e
                    ctx.result = outcome
                    return ctx.result
            finally:
                for emit in self.sinks:
                    emit(ctx)
                _current.reset(token)

        return wrapped

    def __call__(self, func=None, *, on_error=None):
        if func is not None:
            return self.wrap(func, on_error=on_error)
        return lambda f: self.wrap(f, on_error=on_error)
