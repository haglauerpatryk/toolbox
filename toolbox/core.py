import functools
import sys
from pathlib import Path

from toolbox.config import (
    deep_merge_dicts,
    dedupe as _dedupe,
    load_config,
    resolve_sources,
)
from toolbox.context import CallContext, _current
from toolbox.discovery import discover
from toolbox.registries import hook, sink, wrapper
from toolbox.selectors import Selector

_YELLOW = "\033[33m"
_RESET = "\033[0m"


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
    config_sources = None
    log_directory = "logs"
    log_filename = "toolbox.log"
    root_dir = Path(__file__).resolve().parent.parent
    variables = {}
    features = []
    auto_discover = True
    dedupe = True
    warn_on_dedupe = True

    def __init__(self, *, config_sources=None):
        discover(self.features, auto=self.auto_discover)

        sources = config_sources or self.config_sources or [self.config_path]
        config_data = resolve_sources(sources)
        if self.name not in config_data:
            raise ValueError(
                f"toolbox '{self.name}' has no matching config section "
                f"(sources declared: {sorted(config_data)}). Name the toolbox "
                f"explicitly in its config as a handshake, even if the section is empty."
            )
        section = resolve_toolbox_config(type(self), config_data)
        selector = Selector(self.variables)

        self.hooks = {"before": [], "after": [], "on_error": []}
        for name in self._resolve_names(selector, section.get("hooks", {}), "hook"):
            entry = hook.get(name)
            for stage in entry.meta.get("stages", ()):
                self.hooks[stage].append(entry.func)

        self.wrappers = [
            wrapper.get(n).func
            for n in self._resolve_names(selector, section.get("wrappers", {}), "wrapper")
        ]
        self.sinks = [
            sink.get(n).func
            for n in self._resolve_names(selector, section.get("sinks", {}), "sink")
        ]

    def _resolve_names(self, selector, block, kind):
        names = selector.resolve(block)
        if not self.dedupe:
            return names
        kept, removed = _dedupe(names)
        if removed and self.warn_on_dedupe:
            self._warn_duplicates(kind, removed)
        return kept

    def _warn_duplicates(self, kind, removed):
        names = ", ".join(sorted(set(removed)))
        msg = f"[toolbox] {self.name}: removed duplicate {kind}(s): {names}"
        print(f"{_YELLOW}{msg}{_RESET}", file=sys.stderr)

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
