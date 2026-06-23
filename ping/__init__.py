"""ping — a trace-driven dev diagnostic sibling of `toolbox`.

`Ping` inherits `toolbox.ToolBox` wholesale (config, selectors, registries,
`CallContext`, fail-open piece execution) and changes only *how* pieces run:
where a toolbox wraps a call, ping observes targeted functions from
`sys.settrace`. It can only observe — it never alters a call's result or
exception — so it can't introduce a bug raw `print`/timing wouldn't.

Importing this package registers ping's diagnostic pieces.
"""

from ping import pieces  # noqa: F401  (registers ping_* hooks + ping_console sink)
from ping.core import Ping

__all__ = ["Ping"]
