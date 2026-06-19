import functools

import pytest

from toolbox.context import current_context
from toolbox.registries import hook, sink, wrapper


# --- activation / short-circuit --------------------------------------------


def test_inactive_toolbox_returns_func_unchanged(toolbox_factory):
    tb = toolbox_factory()

    def f():
        return 1

    assert tb.wrap(f) is f  # identity: zero overhead when nothing is wired


def test_inactive_toolbox_with_on_error_still_wraps(toolbox_factory):
    tb = toolbox_factory()

    def f():
        return 7

    wrapped = tb.wrap(f, on_error=lambda e: None)
    assert wrapped is not f
    assert wrapped() == 7


# --- hooks ------------------------------------------------------------------


def test_before_and_after_hooks_run_with_correct_stage(toolbox_factory):
    events = []
    hook.register("h_before", stages=("before",))(
        lambda ctx: events.append(("before", ctx.stage))
    )
    hook.register("h_after", stages=("after",))(
        lambda ctx: events.append(("after", ctx.stage, ctx.result))
    )
    tb = toolbox_factory(hooks=["h_before", "h_after"])

    @tb
    def f():
        return 42

    assert f() == 42
    assert events == [("before", "before"), ("after", "after", 42)]


def test_after_hooks_skipped_on_exception(toolbox_factory):
    events = []
    hook.register("only_after", stages=("after",))(lambda ctx: events.append("after"))
    hook.register("only_error", stages=("on_error",))(lambda ctx: events.append("error"))
    tb = toolbox_factory(hooks=["only_after", "only_error"])

    @tb
    def f():
        raise ValueError("x")

    with pytest.raises(ValueError):
        f()
    assert events == ["error"]


def test_hook_registered_for_multiple_stages_runs_each(toolbox_factory):
    seen = []
    hook.register("both", stages=("before", "after"))(lambda ctx: seen.append(ctx.stage))
    tb = toolbox_factory(hooks=["both"])

    @tb
    def f():
        return 1

    f()
    assert seen == ["before", "after"]


# --- wrappers ---------------------------------------------------------------


def test_wrappers_nest_outermost_first(toolbox_factory):
    order = []

    def make(tag):
        def w(func):
            @functools.wraps(func)
            def inner(*a, **k):
                order.append(("enter", tag))
                result = func(*a, **k)
                order.append(("exit", tag))
                return result

            return inner

        return w

    wrapper.register("w1")(make("w1"))
    wrapper.register("w2")(make("w2"))
    tb = toolbox_factory(wrappers=["w1", "w2"])

    @tb
    def f():
        order.append("body")
        return 1

    f()
    # config order [w1, w2] -> w1 is the outermost wrapper
    assert order == [
        ("enter", "w1"),
        ("enter", "w2"),
        "body",
        ("exit", "w2"),
        ("exit", "w1"),
    ]


def test_wrapper_can_alter_result(toolbox_factory):
    def doubler(func):
        @functools.wraps(func)
        def inner(*a, **k):
            return func(*a, **k) * 2

        return inner

    wrapper.register("double")(doubler)
    tb = toolbox_factory(wrappers=["double"])

    @tb
    def f():
        return 21

    assert f() == 42


# --- sinks ------------------------------------------------------------------


def test_sinks_fire_on_success_and_error(toolbox_factory):
    seen = []
    sink.register("recorder")(lambda ctx: seen.append((ctx.exception, ctx.result)))
    tb = toolbox_factory(sinks=["recorder"])

    @tb
    def ok():
        return "r"

    ok()

    @tb
    def boom():
        raise ValueError("x")

    with pytest.raises(ValueError):
        boom()

    assert seen[0] == (None, "r")
    assert isinstance(seen[1][0], ValueError)
    assert seen[1][1] is None


def test_sink_sees_args_and_kwargs(toolbox_factory):
    captured = {}
    sink.register("argcap")(
        lambda ctx: captured.update(args=ctx.args, kwargs=ctx.kwargs)
    )
    tb = toolbox_factory(sinks=["argcap"])

    @tb
    def f(a, b=2):
        return a + b

    f(1, b=3)
    assert captured == {"args": (1,), "kwargs": {"b": 3}}


def test_all_sinks_run(toolbox_factory):
    hits = []
    sink.register("s_one")(lambda ctx: hits.append("one"))
    sink.register("s_two")(lambda ctx: hits.append("two"))
    tb = toolbox_factory(sinks=["s_one", "s_two"])

    @tb
    def f():
        return 1

    f()
    assert hits == ["one", "two"]


# --- on_error lambda contract ----------------------------------------------


def test_on_error_value_becomes_result(toolbox_factory):
    tb = toolbox_factory()

    @tb(on_error=lambda e: "fallback")
    def f():
        raise ValueError("x")

    assert f() == "fallback"


def test_on_error_none_swallows_to_none(toolbox_factory):
    tb = toolbox_factory()

    @tb(on_error=lambda e: None)
    def f():
        raise ValueError("x")

    assert f() is None


def test_on_error_returning_same_exception_reraises_unchained(toolbox_factory):
    tb = toolbox_factory()

    @tb(on_error=lambda e: e)
    def f():
        raise ValueError("orig")

    with pytest.raises(ValueError, match="orig") as info:
        f()
    assert info.value.__cause__ is None  # bare re-raise preserves traceback, no chain


def test_on_error_returning_new_exception_chains(toolbox_factory):
    tb = toolbox_factory()

    @tb(on_error=lambda e: RuntimeError("translated"))
    def f():
        raise ValueError("orig")

    with pytest.raises(RuntimeError, match="translated") as info:
        f()
    assert isinstance(info.value.__cause__, ValueError)
    assert str(info.value.__cause__) == "orig"


def test_no_on_error_propagates_original(toolbox_factory):
    hook.register("oe_noop", stages=("on_error",))(lambda ctx: None)
    tb = toolbox_factory(hooks=["oe_noop"])

    @tb
    def f():
        raise ValueError("x")

    with pytest.raises(ValueError, match="x"):
        f()


def test_on_error_hooks_fire_even_when_lambda_swallows(toolbox_factory):
    fired = []
    hook.register("oe_capture", stages=("on_error",))(
        lambda ctx: fired.append(ctx.exception)
    )
    tb = toolbox_factory(hooks=["oe_capture"])

    @tb(on_error=lambda e: "ok")
    def f():
        raise ValueError("x")

    assert f() == "ok"
    assert isinstance(fired[0], ValueError)


def test_ctx_exception_is_set_for_sinks_on_error(toolbox_factory):
    seen = []
    sink.register("exc_sink")(lambda ctx: seen.append(ctx.exception))
    tb = toolbox_factory(sinks=["exc_sink"])

    @tb(on_error=lambda e: "swallowed")
    def f():
        raise KeyError("k")

    assert f() == "swallowed"
    assert isinstance(seen[0], KeyError)


# --- contextvar lifecycle ---------------------------------------------------


def test_current_context_set_during_call_and_reset_after(toolbox_factory):
    captured = {}
    hook.register("cap_ctx", stages=("before",))(
        lambda ctx: captured.__setitem__("ctx", current_context())
    )
    tb = toolbox_factory(hooks=["cap_ctx"])

    @tb
    def f():
        return 1

    assert current_context() is None
    f()
    assert captured["ctx"] is not None
    assert current_context() is None


def test_context_reset_even_after_exception(toolbox_factory):
    tb = toolbox_factory()

    @tb(on_error=lambda e: e)
    def f():
        raise ValueError("x")

    with pytest.raises(ValueError):
        f()
    assert current_context() is None


# --- decorator surface ------------------------------------------------------


def test_functools_wraps_preserves_metadata(toolbox_factory):
    hook.register("nop_meta", stages=("before",))(lambda ctx: None)
    tb = toolbox_factory(hooks=["nop_meta"])

    @tb
    def my_func():
        "the docstring"
        return 1

    assert my_func.__name__ == "my_func"
    assert my_func.__doc__ == "the docstring"
    assert my_func.__wrapped__.__name__ == "my_func"


def test_log_path_joins_directory_and_filename(toolbox_factory):
    tb = toolbox_factory()  # defaults: log_directory="logs", log_filename="toolbox.log"
    assert tb.log_path == "logs/toolbox.log"


def test_call_bare_and_parenthesized_forms(toolbox_factory):
    hook.register("nop_call", stages=("before",))(lambda ctx: None)
    tb = toolbox_factory(hooks=["nop_call"])

    @tb
    def a():
        return "a"

    @tb()
    def b():
        return "b"

    assert a() == "a"
    assert b() == "b"
