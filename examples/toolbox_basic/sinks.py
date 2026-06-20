import inspect
import json
import os
from pathlib import Path

from toolbox import sink

from .background import background

# Collector/counter state lives here, not in ctx.
_collected = []
_emit_count = {"n": 0}


def reset():
    _collected.clear()
    _emit_count["n"] = 0


def collected():
    return list(_collected)


def emit_count():
    return _emit_count["n"]


@sink.register("terminal")
def terminal(ctx):
    if ctx.buffer:
        print(_render(ctx))


@sink.register("file")
def file(ctx):
    if not ctx.buffer:
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
    _collected.append(
        {
            "func": _unwrap(ctx.func).__name__,
            "lines": list(ctx.buffer),
            "result": ctx.result,
            "exception": ctx.exception,
        }
    )


@sink.register("counter")
def counter(ctx):
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
        "log": list(ctx.buffer),
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
    return "\n".join([_header(ctx), *ctx.buffer, "=" * 80, ""])


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
