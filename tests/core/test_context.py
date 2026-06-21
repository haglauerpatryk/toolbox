import logging

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
    assert ctx.records == []
    assert ctx.messages == []


def test_log_appends_stringified():
    ctx = make_ctx()
    ctx.log("hello")
    ctx.log(123)
    assert ctx.messages == ["hello", "123"]


def test_log_records_level_and_fields():
    ctx = make_ctx()
    ctx.log("default")
    ctx.log("warn", level=logging.WARNING, user="bob")
    assert ctx.records[0].level == logging.INFO
    assert ctx.records[0].fields == {}
    assert ctx.records[1].level == logging.WARNING
    assert ctx.records[1].fields == {"user": "bob"}


def test_mutable_defaults_not_shared_between_instances():
    a = make_ctx()
    b = make_ctx()
    a.log("x")
    a.scratch["k"] = 1
    a.kwargs["q"] = 2
    assert b.records == []
    assert b.scratch == {}
    assert b.kwargs == {}


def test_module_log_falls_back_to_toolbox_logger_without_context(caplog):
    assert current_context() is None
    with caplog.at_level(logging.INFO, logger="toolbox"):
        log("orphan")  # no active call -> must not be dropped silently
    assert any("orphan" in r.getMessage() for r in caplog.records)


def test_module_log_targets_current_context():
    ctx = make_ctx()
    token = _current.set(ctx)
    try:
        assert current_context() is ctx
        log("hi")
        assert ctx.messages == ["hi"]
    finally:
        _current.reset(token)
    assert current_context() is None


def test_module_log_level_helpers_target_context():
    ctx = make_ctx()
    token = _current.set(ctx)
    try:
        log.warning("w")
        log.error("e", code=5)
    finally:
        _current.reset(token)
    assert [(r.msg, r.level) for r in ctx.records] == [
        ("w", logging.WARNING),
        ("e", logging.ERROR),
    ]
    assert ctx.records[1].fields == {"code": 5}


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
