from toolbox.context import CallContext
from toolbox.registries import hook


def make_ctx():
    return CallContext(func=lambda: None)


def test_track_info_registered_for_both_stages():
    assert hook.get("track_info").meta["stages"] == ("before", "after")


def test_track_info_before_sets_path_and_logs():
    ctx = make_ctx()
    ctx.stage = "before"
    hook.get("track_info").func(ctx)
    assert ctx.scratch["path"] == "/fake/path/example.txt"
    assert any("[BEFORE]" in line for line in ctx.buffer)


def test_track_info_after_summarizes_result():
    ctx = make_ctx()
    ctx.stage = "before"
    hook.get("track_info").func(ctx)
    ctx.result = "RESULT"
    ctx.stage = "after"
    hook.get("track_info").func(ctx)
    assert any("[AFTER]" in line and "RESULT" in line for line in ctx.buffer)


def test_track_time_registered_for_both_stages():
    assert hook.get("track_time").meta["stages"] == ("before", "after")


def test_track_time_records_start_then_logs_runtime():
    ctx = make_ctx()
    ctx.stage = "before"
    hook.get("track_time").func(ctx)
    assert "start" in ctx.scratch

    ctx.stage = "after"
    hook.get("track_time").func(ctx)
    assert any("RUNTIME:" in line for line in ctx.buffer)


def test_track_time_after_without_start_does_not_crash():
    ctx = make_ctx()
    ctx.stage = "after"  # no preceding "before"
    hook.get("track_time").func(ctx)
    assert any("RUNTIME:" in line for line in ctx.buffer)
