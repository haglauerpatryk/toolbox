from toolbox.context import CallContext
from toolbox.registries import hook


def test_handle_problem_registered_for_on_error():
    assert hook.get("handle_problem").meta["stages"] == ("on_error",)


def test_handle_problem_logs_the_exception():
    ctx = CallContext(func=lambda: None, exception=ValueError("boom"))
    hook.get("handle_problem").func(ctx)
    assert ctx.buffer == ["[ERROR] Caught: boom"]
