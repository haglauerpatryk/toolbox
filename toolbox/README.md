# toolbox

Config-driven function wrapping. The core ships **no behavior** — you decorate a
function and config decides what runs around each call. Behaviors ("pieces") live
outside the core.

## The four kinds

| kind | decorator | signature | role |
|---|---|---|---|
| hook | `@hook.register("n", stages=(...))` | `(ctx)` | observe at before / after / on_error |
| wrapper | `@wrapper.register("n")` | `(func)->func` | middleware inside the call (alters flow) |
| sink | `@sink.register("n")` | `(ctx)` | where a call's log records go |
| rule | `@rule.register("n")` | `(vars, payload)->[names]` | config selector |

## Define a toolbox

```python
from toolbox import ToolBox
from config import BASE

class MyBox(ToolBox):
    name = "my_box"                       # must match a config section (handshake)
    config_sources = [BASE, "configs/"]   # ordered; later overrides earlier
    variables = {"VERBOSE": 1}            # your flags — no built-ins
    features = ["myproject.pieces"]       # modules to import pieces from

box = MyBox()
```

## Decorate

```python
@box
def work(...): ...

@box(on_error=lambda e: None)             # swallow → result is None
def risky(...): ...
```

**`on_error` contract:** return an exception → it's raised; return anything else →
that becomes the result. `catch({Type: handler})` routes by exception type. A policy
that itself raises propagates that exception (this is how failover surfaces a backup's
failure).

## Config

```yaml
my_box:
  hooks:    { always: [track], if_var: { VERBOSE: [timing] } }
  wrappers: { always: [retry] }
  sinks:    { always: [logging] }
```

Sections map to kinds; rules (`always` / `if_var` / `if_not_var`) pick pieces by name.
Subclasses deep-merge their parents' sections.

**Sources** — an ordered list of dicts / files / directories, merged left-to-right:
dict = pass-through (e.g. JSON from an API), files by extension (`.yaml`/`.json`),
directories merge the config files inside. Lists append, then de-duplicate.

## Write a piece

```python
from toolbox import hook

@hook.register("timing", stages=("before", "after"))
def timing(ctx):
    ...   # cross-call state lives in the module, never on ctx (and guard it for threads)
```

Importing the module registers it. Names are unique per kind.

## Logging

```python
from toolbox import log
log("started"); log.warning("slow upstream", ms=812)
```

Records buffer on the call and flush **once**, via a sink, at the end of every path
(success, error, recovery). The default `logging` sink hands them to stdlib `logging` —
the host owns handlers and formatters.

## Invariants

- Config **selects** code, never introduces it — `reconfigure(sources)` can re-wire a
  live app but can't smuggle in code. It rebuilds and atomically swaps; in-flight calls
  finish on the old config.
- Hooks and sinks are **fail-open** (a raising piece is caught and reported); only
  wrappers and `on_error` change a call's outcome.

> Full reference: [../README.md](../README.md) · design rationale: [../ARCHITECTURE.md](../ARCHITECTURE.md)
