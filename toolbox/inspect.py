"""Read-only introspection for toolboxes and wrapped functions.

    python -m toolbox.inspect inspect  <module.path.to.function>
    python -m toolbox.inspect validate <module.path.to.toolbox>

`inspect` walks a function's wrap stack (which toolboxes are attached, outermost
first) and flags any piece active in more than one layer — a duplicate the
per-toolbox dedup can't see, because stacked toolboxes are independent. `validate`
builds a toolbox's config (handshake + every piece exists) without running it.

Nothing here is imported by the core at runtime; it loads only when invoked.
"""

import importlib
import sys

from toolbox.core import ToolBox
from toolbox.registries import hook, sink, wrapper

_YELLOW = "\033[33m"
_RESET = "\033[0m"
_HOOK_STAGES = ("before", "after", "on_error")


def toolbox_stack(func):
    """The toolboxes wrapping `func`, outermost first."""
    stack = []
    current = func
    seen = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        tb = getattr(current, "__toolbox__", None)
        if tb is not None:
            stack.append(tb)
        current = getattr(current, "__wrapped__", None)
    return stack


def active_pieces(tb):
    """A toolbox's resolved piece names, by kind."""
    cfg = tb._config
    return {
        "hooks": {stage: _names(cfg.hooks[stage], hook) for stage in _HOOK_STAGES},
        "wrappers": _names(cfg.wrappers, wrapper),
        "sinks": _names(cfg.sinks, sink),
    }


def inspect_function(func):
    layers = [{"name": tb.name, "pieces": active_pieces(tb)} for tb in toolbox_stack(func)]
    return {
        "function": getattr(_unwrap(func), "__name__", repr(func)),
        "layers": layers,
        "duplicate_pieces": _cross_stack_duplicates(layers),
        "repeated_toolboxes": _repeated(layer["name"] for layer in layers),
    }


def validate(target):
    """Build a toolbox's config without running it; raises on a bad config."""
    if isinstance(target, ToolBox):
        target._build(target._sources)
        return active_pieces(target)
    if isinstance(target, type) and issubclass(target, ToolBox):
        return active_pieces(target())
    raise TypeError(f"{target!r} is not a ToolBox class or instance")


# --- helpers ----------------------------------------------------------------


def _names(funcs, registry):
    lookup = {id(registry.get(n).func): n for n in registry.names()}
    return [lookup.get(id(f), getattr(f, "__name__", repr(f))) for f in funcs]


def _unwrap(func):
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__
    return func


def _cross_stack_duplicates(layers):
    where = {}
    for layer in layers:
        pieces = layer["pieces"]
        by_kind = {
            "hook": {n for stage in _HOOK_STAGES for n in pieces["hooks"][stage]},
            "wrapper": set(pieces["wrappers"]),
            "sink": set(pieces["sinks"]),
        }
        for kind, names in by_kind.items():
            for name in names:
                where.setdefault((kind, name), []).append(layer["name"])
    return {key: tbs for key, tbs in where.items() if len(tbs) > 1}


def _repeated(names):
    seen, repeated = set(), set()
    for n in names:
        (repeated if n in seen else seen).add(n)
    return sorted(repeated)


# --- rendering / CLI --------------------------------------------------------


def _render_pieces(pieces, indent=""):
    lines = []
    for stage in _HOOK_STAGES:
        if pieces["hooks"][stage]:
            lines.append(f"{indent}hooks.{stage}: {', '.join(pieces['hooks'][stage])}")
    if pieces["wrappers"]:
        lines.append(f"{indent}wrappers: {', '.join(pieces['wrappers'])}")
    if pieces["sinks"]:
        lines.append(f"{indent}sinks: {', '.join(pieces['sinks'])}")
    return "\n".join(lines) if lines else f"{indent}(no pieces)"


def render_inspect(report):
    lines = [f"function: {report['function']}"]
    if not report["layers"]:
        lines.append("  (no toolboxes attached — not a wrapped function)")
        return "\n".join(lines)
    lines.append("toolboxes (outermost first):")
    for i, layer in enumerate(report["layers"], 1):
        lines.append(f"  {i}. {layer['name']}")
        lines.append(_render_pieces(layer["pieces"], indent="       "))
    dups = report["duplicate_pieces"]
    if dups:
        lines.append(f"{_YELLOW}duplicate pieces across the stack:{_RESET}")
        for (kind, name), tbs in sorted(dups.items()):
            lines.append(f"{_YELLOW}  {kind} '{name}' in: {', '.join(sorted(tbs))}{_RESET}")
    if report["repeated_toolboxes"]:
        names = ", ".join(report["repeated_toolboxes"])
        lines.append(f"{_YELLOW}  toolbox applied more than once: {names}{_RESET}")
    if not dups and not report["repeated_toolboxes"]:
        lines.append("no duplicate pieces across the stack.")
    return "\n".join(lines)


def _resolve(path):
    module_path, _, attr = path.rpartition(".")
    if not module_path:
        raise ValueError(f"'{path}' is not a dotted module path (expected module.attr)")
    return getattr(importlib.import_module(module_path), attr)


def cmd_inspect(path):
    print(render_inspect(inspect_function(_resolve(path))))
    return 0


def cmd_validate(path):
    target = _resolve(path)
    try:
        pieces = validate(target)
    except Exception as e:
        print(f"{_YELLOW}INVALID{_RESET} {path}: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(f"OK {path}")
    print(_render_pieces(pieces, indent="  "))
    return 0


_COMMANDS = {"inspect": cmd_inspect, "validate": cmd_validate}


def main(argv):
    if len(argv) != 2 or argv[0] not in _COMMANDS:
        print(
            "usage: python -m toolbox.inspect {inspect|validate} <module.path.to.target>",
            file=sys.stderr,
        )
        return 2
    try:
        return _COMMANDS[argv[0]](argv[1])
    except (ImportError, AttributeError, ValueError) as e:
        print(f"{_YELLOW}error{_RESET}: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
