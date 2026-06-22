import inspect
import json
import logging
import os
import threading
from pathlib import Path

from toolbox import sink

from .background import background

# Collector/counter state lives here, not in ctx. Pieces run on whatever threads
# the host uses, so this shared state is guarded by a lock.
_collected = []
_emit_count = {"n": 0}
_lock = threading.Lock()


def reset():
    with _lock:
        _collected.clear()
        _emit_count["n"] = 0


def collected():
    with _lock:
        return list(_collected)


def emit_count():
    with _lock:
        return _emit_count["n"]


# --- the logging seam: the default, stdlib-backed emitter --------------------
#
# This is where logging is *integrated* rather than reinvented. The sink hands
# each structured record to a named `logging.Logger`; destinations, formatting,
# and level thresholds are owned by the host's logging configuration
# (handlers/formatters — e.g. Django's LOGGING). Swap this one sink for another
# backend (structlog, etc.) without touching the core.


def _logger_for(ctx):
    tb_name = getattr(ctx.toolbox, "name", None) or "toolbox"
    return logging.getLogger(f"toolbox.{tb_name}.{_unwrap(ctx.func).__name__}")


@sink.register("logging")
def logging_sink(ctx):
    if not ctx.records:
        return
    logger = _logger_for(ctx)
    func_name = _unwrap(ctx.func).__name__
    tb_name = getattr(ctx.toolbox, "name", None) or "toolbox"
    for rec in ctx.records:
        if not logger.isEnabledFor(rec.level):
            continue
        std = logger.makeRecord(
            logger.name, rec.level, "(toolbox)", 0, rec.msg, (), None,
            func=func_name,
            extra={"toolbox": {
                "toolbox": tb_name,
                "func": func_name,
                "call_id": id(ctx),
                "stage": ctx.stage,
                **rec.fields,
            }},
        )
        # Preserve the log-time timestamp captured when the record was created,
        # rather than this end-of-call emission time.
        std.created = rec.created
        std.msecs = (rec.created % 1) * 1000
        logger.handle(std)


# same emitter, run off the request path by the background worker
sink.register("logging_background")(background(logging_sink))


# --- convenience destinations (render the records directly) -------------------
# Handy for demos/tests; the logging sink above is the recommended path.


@sink.register("terminal")
def terminal(ctx):
    if ctx.records:
        print(_render(ctx))


@sink.register("file")
def file(ctx):
    if not ctx.records:
        return
    path = ctx.toolbox.log_path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as fh:
        fh.write(_render(ctx) + "\n")


# same file sink, run off the request path by a background worker
sink.register("file_background")(background(file))


@sink.register("memory")
def memory(ctx):
    # An in-memory collector: a real aggregation sink and a clean test affordance.
    entry = {
        "func": _unwrap(ctx.func).__name__,
        "lines": list(ctx.messages),
        "records": list(ctx.records),
        "result": ctx.result,
        "exception": ctx.exception,
    }
    with _lock:
        _collected.append(entry)


@sink.register("counter")
def counter(ctx):
    with _lock:
        _emit_count["n"] += 1


@sink.register("json_lines")
def json_lines(ctx):
    # Structured, one JSON object per call — an audit/event stream.
    path = os.path.join(getattr(ctx.toolbox, "log_directory", "logs"), "events.jsonl")
    record = {
        "func": _unwrap(ctx.func).__name__,
        "ok": ctx.exception is None,
        "result": _jsonable(ctx.result),
        "error": None if ctx.exception is None else str(ctx.exception),
        "log": [
            {"level": logging.getLevelName(r.level), "msg": r.msg, "fields": r.fields}
            for r in ctx.records
        ],
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as fh:
        fh.write(json.dumps(record) + "\n")


def _jsonable(value):
    try:
        json.dumps(value)
        return value
    except TypeError:
        return repr(value)


def _render(ctx):
    body = [f"[{logging.getLevelName(r.level)}] {r.msg}" for r in ctx.records]
    return "\n".join([_header(ctx), *body, "=" * 80, ""])


def _header(ctx):
    func = _unwrap(ctx.func)
    try:
        path = inspect.getfile(func)
        line = inspect.getsourcelines(func)[1]
        root = getattr(ctx.toolbox, "root_dir", None)
        if root and str(path).startswith(str(root)):
            path = Path(path).relative_to(root)
    except Exception:
        path, line = "unknown", "?"
    return "\n".join(["=" * 80, f"FUNC:    {func.__name__}", f"PATH:    {path}:{line}"])


def _unwrap(func):
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__
    return func
