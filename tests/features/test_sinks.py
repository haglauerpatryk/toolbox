import functools
import inspect
import os

from toolbox.context import CallContext
from toolbox.registries import sink


def example_func():
    return 1


class FakeToolbox:
    def __init__(self, log_path, root_dir=None):
        self._log_path = log_path
        self.root_dir = root_dir

    @property
    def log_path(self):
        return self._log_path


def make_ctx(buffer=None, toolbox=None):
    ctx = CallContext(func=example_func, toolbox=toolbox)
    if buffer:
        ctx.buffer.extend(buffer)
    return ctx


def test_terminal_prints_when_buffer_present(capsys):
    sink.get("terminal").func(make_ctx(buffer=["line one"]))
    out = capsys.readouterr().out
    assert "line one" in out
    assert "example_func" in out  # header rendered


def test_terminal_silent_when_buffer_empty(capsys):
    sink.get("terminal").func(make_ctx())
    assert capsys.readouterr().out == ""


def test_file_writes_render_and_creates_directory(tmp_path):
    path = tmp_path / "logs" / "out.log"
    ctx = make_ctx(buffer=["hello"], toolbox=FakeToolbox(str(path)))
    sink.get("file").func(ctx)

    content = path.read_text()
    assert "hello" in content
    assert "FUNC:" in content
    assert "example_func" in content
    assert "=" * 80 in content


def test_file_appends_across_calls(tmp_path):
    path = tmp_path / "out.log"
    tb = FakeToolbox(str(path))
    sink.get("file").func(make_ctx(buffer=["first"], toolbox=tb))
    sink.get("file").func(make_ctx(buffer=["second"], toolbox=tb))
    content = path.read_text()
    assert "first" in content
    assert "second" in content


def test_file_silent_when_buffer_empty(tmp_path):
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
    ctx.buffer.append("x")
    sink.get("file").func(ctx)

    content = path.read_text()
    assert "FUNC:    example_func" in content  # unwrapped to the original name


def test_header_renders_path_relative_to_root(tmp_path):
    func_file = inspect.getfile(example_func)
    root = os.path.dirname(func_file)
    path = tmp_path / "out.log"
    ctx = CallContext(func=example_func, toolbox=FakeToolbox(str(path), root_dir=root))
    ctx.buffer.append("x")
    sink.get("file").func(ctx)

    content = path.read_text()
    assert os.path.basename(func_file) in content
    assert f"PATH:    {root}" not in content  # absolute root prefix stripped


def test_header_falls_back_when_func_not_introspectable(capsys):
    # a builtin has no source file -> inspect raises -> "unknown:?"
    ctx = CallContext(func=len, toolbox=None)
    ctx.buffer.append("x")
    sink.get("terminal").func(ctx)
    out = capsys.readouterr().out
    assert "unknown:?" in out
