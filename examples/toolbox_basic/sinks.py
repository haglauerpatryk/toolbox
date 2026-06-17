import inspect
import os
from pathlib import Path

from toolbox import sink


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
