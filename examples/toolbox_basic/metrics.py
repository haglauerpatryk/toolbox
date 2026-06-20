from time import perf_counter

from toolbox import hook

# Aggregate state lives in this module, never in ctx (ctx is per-call scratch).
_call_counts = {}


def reset():
    _call_counts.clear()


def counts():
    return dict(_call_counts)


@hook.register("count_calls", stages=("before",))
def count_calls(ctx):
    name = ctx.func.__name__
    _call_counts[name] = _call_counts.get(name, 0) + 1
    ctx.log(f"[COUNT] {name} call #{_call_counts[name]}")


@hook.register("capture_args", stages=("before",))
def capture_args(ctx):
    ctx.log(f"[ARGS] args={ctx.args!r} kwargs={ctx.kwargs!r}")


@hook.register("slow_warning", stages=("after",))
def slow_warning(ctx):
    # Composes with track_time, which records the start in scratch.
    start = ctx.scratch.get("start")
    if start is None:
        return
    elapsed_ms = (perf_counter() - start) * 1000
    threshold = (getattr(ctx.toolbox, "variables", None) or {}).get("SLOW_MS", 1000)
    if elapsed_ms > threshold:
        ctx.log(f"[SLOW] {ctx.func.__name__} took {elapsed_ms:.1f}ms (> {threshold}ms)")
