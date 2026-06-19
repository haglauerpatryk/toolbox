from toolbox.context import CallContext, _current, current_context, log


def make_ctx():
    return CallContext(func=lambda: None)


def test_defaults():
    ctx = make_ctx()
    assert ctx.args == ()
    assert ctx.kwargs == {}
    assert ctx.toolbox is None
    assert ctx.stage is None
    assert ctx.result is None
    assert ctx.exception is None
    assert ctx.scratch == {}
    assert ctx.buffer == []


def test_log_appends_stringified():
    ctx = make_ctx()
    ctx.log("hello")
    ctx.log(123)
    assert ctx.buffer == ["hello", "123"]


def test_mutable_defaults_not_shared_between_instances():
    a = make_ctx()
    b = make_ctx()
    a.buffer.append("x")
    a.scratch["k"] = 1
    a.kwargs["q"] = 2
    assert b.buffer == []
    assert b.scratch == {}
    assert b.kwargs == {}


def test_module_log_is_noop_without_active_context():
    assert current_context() is None
    log("dropped")  # must not raise


def test_module_log_targets_current_context():
    ctx = make_ctx()
    token = _current.set(ctx)
    try:
        assert current_context() is ctx
        log("hi")
        assert ctx.buffer == ["hi"]
    finally:
        _current.reset(token)
    assert current_context() is None


def test_contexts_isolated_by_token_reset():
    first = make_ctx()
    token1 = _current.set(first)
    try:
        second = make_ctx()
        token2 = _current.set(second)
        try:
            assert current_context() is second
        finally:
            _current.reset(token2)
        assert current_context() is first
    finally:
        _current.reset(token1)
