import logging
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

_current = ContextVar("toolbox_call_context", default=None)

# Logs emitted outside any wrapped call used to vanish silently. They now fall
# back to this logger so a message is never dropped without a trace.
_fallback_logger = logging.getLogger("toolbox")

DEFAULT_LEVEL = logging.INFO


@dataclass
class LogRecord:
    """One structured, leveled log entry produced during a call.

    `created` is stamped at log time, not at emission time: sinks flush at the
    end of the call, so capturing the timestamp here keeps it accurate when the
    buffered records are later replayed into a backend.
    """

    msg: str
    level: int = DEFAULT_LEVEL
    fields: dict = field(default_factory=dict)
    created: float = field(default_factory=time.time)


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
    records: list = field(default_factory=list)

    def log(self, msg, level=DEFAULT_LEVEL, **fields):
        self.records.append(LogRecord(msg=str(msg), level=level, fields=fields))

    @property
    def messages(self):
        """The rendered message strings, in order — a convenience view over records."""
        return [r.msg for r in self.records]


def current_context():
    return _current.get()


class _Log:
    """The module-level logging front door.

    Inside a wrapped call it appends a structured record to the call's context;
    a sink later decides where those records go. Outside any call it falls back
    to the `toolbox` logger so the message is still emitted rather than dropped.
    The default level is INFO, so existing ``log("...")`` calls keep working.
    """

    def __call__(self, msg, level=DEFAULT_LEVEL, **fields):
        ctx = _current.get()
        if ctx is not None:
            ctx.log(msg, level=level, **fields)
        elif fields:
            _fallback_logger.log(level, "%s | %r", msg, fields)
        else:
            _fallback_logger.log(level, "%s", msg)

    def debug(self, msg, **fields):
        self(msg, level=logging.DEBUG, **fields)

    def info(self, msg, **fields):
        self(msg, level=logging.INFO, **fields)

    def warning(self, msg, **fields):
        self(msg, level=logging.WARNING, **fields)

    def error(self, msg, **fields):
        self(msg, level=logging.ERROR, **fields)

    def critical(self, msg, **fields):
        self(msg, level=logging.CRITICAL, **fields)


log = _Log()
