"""ping's own trivial diagnostics.

They are ordinary `toolbox` hooks/sinks — registered into the same registries,
selected by ping's config the same way — so ping reuses the architecture rather
than reinventing it. They emit onto `ctx.records` (never anywhere your real
logging would pick them up) and a console sink renders them to stderr. Self
contained: ping does not depend on the example bundle.
"""

import logging
import sys
from time import perf_counter

from toolbox import hook, sink


@hook.register("ping_time", stages=("before", "after"))
def ping_time(ctx):
    if ctx.stage == "before":
        ctx.scratch["__ping_start__"] = perf_counter()
    else:
        start = ctx.scratch.get("__ping_start__")
        if start is not None:
            ctx.log(f"time={(perf_counter() - start) * 1000:.2f}ms")


@hook.register("ping_args", stages=("before",))
def ping_args(ctx):
    ctx.log(f"args={ctx.args!r} kwargs={ctx.kwargs!r}")


@hook.register("ping_types", stages=("after",))
def ping_types(ctx):
    ctx.log(f"-> {type(ctx.result).__name__} {ctx.result!r}")


@hook.register("ping_error", stages=("on_error",))
def ping_error(ctx):
    ctx.log(
        f"raised {type(ctx.exception).__name__}: {ctx.exception}",
        level=logging.ERROR,
    )


@sink.register("ping_console")
def ping_console(ctx):
    if not ctx.records:
        return
    name = getattr(ctx.func, "__name__", "?")
    body = "\n".join(f"  {logging.getLevelName(r.level)} {r.msg}" for r in ctx.records)
    sys.stderr.write(f"[ping] {name}\n{body}\n")
