from time import perf_counter

from toolbox import hook


@hook.register("track_time", stages=("before", "after"))
def track_time(ctx):
    if ctx.stage == "before":
        ctx.scratch["start"] = perf_counter()
    else:
        elapsed = perf_counter() - ctx.scratch.get("start", perf_counter())
        ctx.log(f"RUNTIME: {elapsed:.3f}s")


@hook.register("track_info", stages=("before", "after"))
def track_info(ctx):
    if ctx.stage == "before":
        ctx.scratch["path"] = "/fake/path/example.txt"
        ctx.log(f"[BEFORE] Path set to: {ctx.scratch['path']}")
    else:
        ctx.log(f"[AFTER] Result summary: {ctx.result}, path was: {ctx.scratch.get('path')}")
