import sys

from ping.adapter import build_context


def test_build_context_extracts_func_and_args():
    def sample(a, b, *, c=0):
        return sys._getframe()

    frame = sample(1, 2, c=9)
    ctx = build_context(frame, toolbox="TB")

    assert ctx.func.__name__ == "sample"
    assert ctx.func.__qualname__.endswith("sample")
    assert ctx.args == (1, 2)
    assert ctx.kwargs == {"c": 9}
    assert ctx.toolbox == "TB"
