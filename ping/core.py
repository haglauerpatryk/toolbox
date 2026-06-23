"""`Ping` — a `ToolBox` whose engine is `sys.settrace` instead of `wrap`.

Everything about config (sources, MRO merge, selectors, dedupe, reconfigure) and
piece execution (`CallContext`, fail-open `_run_piece`) is inherited unchanged.
The only differences:

  * activation is `enable()`/`disable()` (install/remove the trace hook), not a
    decorator;
  * pieces run from trace events — `call` -> before, `return` -> after,
    `exception`/unwind -> on_error — against a `CallContext` built from the frame;
  * wrappers are rejected: a tracer observes, it cannot alter control flow.

The trace callbacks never raise into traced code and never touch the call's
result or exception, so ping cannot introduce a bug raw tooling wouldn't.
"""

import logging
import sys
import threading
from pathlib import Path

from toolbox.context import _current
from toolbox.core import ToolBox, _run_piece

from ping.adapter import build_context
from ping.matcher import TargetMatcher

_log = logging.getLogger("ping")

_PING_DIR = Path(__file__).resolve().parent
_DEFAULT_CONFIG = str(_PING_DIR / "config" / "ping.yaml")
_DEFAULT_TARGETS = str(_PING_DIR / "config" / "targets.json")


class Ping(ToolBox):
    name = "ping"
    config_sources = [_DEFAULT_CONFIG]
    targets_path = _DEFAULT_TARGETS
    features = []
    auto_discover = False

    def __init__(self, *, config_sources=None, targets_path=None):
        super().__init__(config_sources=config_sources)
        self._matcher = TargetMatcher(targets_path or self.targets_path)
        self._frames = {}
        self._installed = False

    def _build(self, sources):
        cfg = super()._build(sources)
        if cfg.wrappers:
            raise ValueError(
                "ping does not support wrappers — a tracer observes, it cannot "
                "alter control flow. Remove the 'wrappers' section from ping config."
            )
        return cfg

    # --- activation ---------------------------------------------------------

    def enable(self):
        if self._installed:
            return
        self._installed = True
        self._frames = {}
        threading.settrace(self._global_trace)
        sys.settrace(self._global_trace)

    def disable(self):
        if not self._installed:
            return
        self._installed = False
        sys.settrace(None)
        threading.settrace(None)
        self._frames.clear()

    def __enter__(self):
        self.enable()
        return self

    def __exit__(self, *exc):
        self.disable()
        return False

    # --- trace driver -------------------------------------------------------

    def _global_trace(self, frame, event, arg):
        # Fires on entering every frame in the process; act only on matched
        # targets. Guarded so a failure here can never break traced code.
        if event != "call":
            return None
        try:
            if not self._matcher.matches(frame):
                return None
            ctx = build_context(frame, toolbox=self)
            self._frames[id(frame)] = {"ctx": ctx, "exc": None}
            self._run_stage("before", ctx)
        except Exception:
            _log.exception("ping: error entering traced frame")
            return None
        return self._local_trace

    def _local_trace(self, frame, event, arg):
        try:
            state = self._frames.get(id(frame))
            if state is None:
                return self._local_trace
            if event == "line":
                # An exception that reaches 'return' un-cleared was unwinding; a
                # caught one runs further lines (the except body), which clears
                # it — so a caught-then-return isn't misreported as a failure.
                state["exc"] = None
            elif event == "exception":
                state["exc"] = arg[1]
            elif event == "return":
                self._finalize(frame, state, arg)
        except Exception:
            _log.exception("ping: error in trace callback")
        return self._local_trace

    def _finalize(self, frame, state, arg):
        self._frames.pop(id(frame), None)
        ctx = state["ctx"]
        if state["exc"] is not None:
            ctx.exception = state["exc"]
            self._run_stage("on_error", ctx)
        else:
            ctx.result = arg
            self._run_stage("after", ctx)
        self._flush(ctx)

    def _run_stage(self, stage, ctx):
        ctx.stage = stage
        token = _current.set(ctx)
        try:
            for method in self._config.hooks[stage]:
                _run_piece(method, ctx, "hook")
        finally:
            _current.reset(token)

    def _flush(self, ctx):
        token = _current.set(ctx)
        try:
            for emit in self._config.sinks:
                _run_piece(emit, ctx, "sink")
        finally:
            _current.reset(token)
