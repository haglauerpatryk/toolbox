"""Build a real `CallContext` from a stack frame.

This is the one genuine seam between the trace world (frames) and the toolbox
world (`CallContext`). Because `Ping` is a real `ToolBox`, the context carries a
real `toolbox`, so pieces that read `ctx.toolbox.variables` work unchanged.

`func` is a lightweight shim over the frame's code object — enough for pieces
that read `__name__`/`__qualname__` and for `_unwrap` (no `__wrapped__`). Args
are reconstructed from the frame's locals at call time: positional params become
`args`, keyword-only params become `kwargs`. It's a faithful approximation for a
dev dump, not a perfect reproduction of the original call signature.
"""

from toolbox.context import CallContext


class _FrameFunc:
    def __init__(self, code, module):
        self.__name__ = code.co_name
        self.__qualname__ = getattr(code, "co_qualname", code.co_name)
        self.__module__ = module
        self.__code__ = code
        self.__doc__ = None


def build_context(frame, toolbox):
    code = frame.f_code
    func = _FrameFunc(code, frame.f_globals.get("__name__"))
    args, kwargs = _extract_args(frame)
    return CallContext(func=func, args=args, kwargs=kwargs, toolbox=toolbox)


def _extract_args(frame):
    code = frame.f_code
    local = frame.f_locals
    names = code.co_varnames
    npos = code.co_argcount
    nkw = code.co_kwonlyargcount
    args = tuple(local.get(n) for n in names[:npos])
    kwargs = {n: local[n] for n in names[npos:npos + nkw] if n in local}
    return args, kwargs
