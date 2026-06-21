import functools
import inspect
import logging
import os

from toolbox.context import CallContext
from toolbox.registries import sink


def example_func():
    return 1


class FakeToolbox:
    def __init__(self, log_path=None, root_dir=None, name="toolbox"):
        self._log_path = log_path
        self.root_dir = root_dir
        self.name = name

    @property
    def log_path(self):
        return self._log_path


def make_ctx(lines=None, toolbox=None, level=logging.INFO):
    ctx = CallContext(func=example_func, toolbox=toolbox)
    for line in lines or []:
        ctx.log(line, level=level)
    return ctx


# --- the logging seam -------------------------------------------------------


def test_logging_sink_emits_records_at_their_level(caplog):
    ctx = make_ctx(toolbox=FakeToolbox(name="svc"))
    ctx.log("info line")
    ctx.log("bad", level=logging.ERROR, code=7)
    with caplog.at_level(logging.DEBUG, logger="toolbox.svc.example_func"):
        sink.get("logging").func(ctx)
    by_level = {r.levelno: r for r in caplog.records}
    assert "info line" in by_level[logging.INFO].getMessage()
    assert "bad" in by_level[logging.ERROR].getMessage()
    # structured fields + call context ride along under a namespaced attribute
    assert by_level[logging.ERROR].toolbox["code"] == 7
    assert by_level[logging.ERROR].toolbox["func"] == "example_func"


def test_logging_sink_silent_without_records(caplog):
    with caplog.at_level(logging.DEBUG):
        sink.get("logging").func(make_ctx(toolbox=FakeToolbox()))
    assert caplog.records == []


def test_logging_sink_preserves_log_time_timestamp(caplog):
    ctx = make_ctx(toolbox=FakeToolbox())
    ctx.log("x")
    stamped = ctx.records[0].created
    with caplog.at_level(logging.INFO, logger="toolbox"):
        sink.get("logging").func(ctx)
    assert caplog.records[0].created == stamped


def test_logging_background_is_registered():
    assert "logging_background" in sink


# --- convenience destinations -----------------------------------------------


def test_terminal_prints_when_records_present(capsys):
    sink.get("terminal").func(make_ctx(lines=["line one"]))
    out = capsys.readouterr().out
    assert "line one" in out
    assert "example_func" in out  # header rendered


def test_terminal_silent_when_no_records(capsys):
    sink.get("terminal").func(make_ctx())
    assert capsys.readouterr().out == ""


def test_terminal_shows_level(capsys):
    sink.get("terminal").func(make_ctx(lines=["uh oh"], level=logging.WARNING))
    assert "[WARNING]" in capsys.readouterr().out


def test_file_writes_render_and_creates_directory(tmp_path):
    path = tmp_path / "logs" / "out.log"
    ctx = make_ctx(lines=["hello"], toolbox=FakeToolbox(str(path)))
    sink.get("file").func(ctx)

    content = path.read_text()
    assert "hello" in content
    assert "FUNC:" in content
    assert "example_func" in content
    assert "=" * 80 in content


def test_file_appends_across_calls(tmp_path):
    path = tmp_path / "out.log"
    tb = FakeToolbox(str(path))
    sink.get("file").func(make_ctx(lines=["first"], toolbox=tb))
    sink.get("file").func(make_ctx(lines=["second"], toolbox=tb))
    content = path.read_text()
    assert "first" in content
    assert "second" in content


def test_file_silent_when_no_records(tmp_path):
    path = tmp_path / "out.log"
    sink.get("file").func(make_ctx(toolbox=FakeToolbox(str(path))))
    assert not path.exists()


def test_file_background_is_registered():
    assert "file_background" in sink


# --- header rendering seams -------------------------------------------------


def test_header_unwraps_wrapped_function(tmp_path):
    # in production the sink sees the functools.wraps wrapper, not the original
    @functools.wraps(example_func)
    def wrapper_fn():
        return example_func()

    path = tmp_path / "out.log"
    ctx = CallContext(func=wrapper_fn, toolbox=FakeToolbox(str(path)))
    ctx.log("x")
    sink.get("file").func(ctx)

    content = path.read_text()
    assert "FUNC:    example_func" in content  # unwrapped to the original name


def test_header_renders_path_relative_to_root(tmp_path):
    func_file = inspect.getfile(example_func)
    root = os.path.dirname(func_file)
    path = tmp_path / "out.log"
    ctx = CallContext(func=example_func, toolbox=FakeToolbox(str(path), root_dir=root))
    ctx.log("x")
    sink.get("file").func(ctx)

    content = path.read_text()
    assert os.path.basename(func_file) in content
    assert f"PATH:    {root}" not in content  # absolute root prefix stripped


def test_header_falls_back_when_func_not_introspectable(capsys):
    # a builtin has no source file -> inspect raises -> "unknown:?"
    ctx = CallContext(func=len, toolbox=None)
    ctx.log("x")
    sink.get("terminal").func(ctx)
    out = capsys.readouterr().out
    assert "unknown:?" in out
