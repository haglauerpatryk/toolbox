import logging

from toolbox import hook


@hook.register("handle_problem", stages=("on_error",))
def handle_problem(ctx):
    ctx.log(f"[ERROR] Caught: {ctx.exception}", level=logging.ERROR)
