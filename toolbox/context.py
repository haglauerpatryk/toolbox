from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

_current = ContextVar("toolbox_call_context", default=None)


@dataclass
class CallContext:
    func: Callable
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    toolbox: Any = None
    stage: Optional[str] = None
    result: Any = None
    exception: Optional[BaseException] = None
    scratch: dict = field(default_factory=dict)
    buffer: list = field(default_factory=list)

    def log(self, msg):
        self.buffer.append(str(msg))


def current_context():
    return _current.get()


def log(msg):
    ctx = _current.get()
    if ctx is not None:
        ctx.log(msg)
