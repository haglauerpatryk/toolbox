# toolbox

A small, config-driven **function-wrapping architecture**. The core ships with *no*
behavior of its own — you decorate a function, and a YAML file declaratively decides
what runs around each call (instrumentation, logging, retries, error handling).

The behaviors themselves ("lego pieces") live **outside** the core. You install a
bundle, write your own, or both.

## Concepts

Two layers, kept strictly separate:

- **Core (`toolbox/`)** — the architecture. Installable on its own and does nothing
  until a piece registers. Provides the `ToolBox` engine, the YAML/config machinery,
  the `CallContext`, and the four registries pieces plug into.
- **Pieces (features)** — the lego bricks. Each is a small function registered under a
  name with one of four decorators. They live in feature bundles (e.g.
  `examples/toolbox_basic/`) or in your own project.

### The four kinds

Every extension point uses the **same** convention: `@<kind>.register("<name>")`, where
`<name>` is the exact string you reference in `config.yaml`.

| Kind | Decorator | Signature | What it is |
|------|-----------|-----------|------------|
| hook | `@hook.register("n", stages=("before","after","on_error"))` | `(ctx)` | observer that runs at lifecycle points |
| wrapper | `@wrapper.register("n")` | `(func) -> func` | middleware that wraps the call (can alter control flow) |
| sink | `@sink.register("n")` | `(ctx)` | where buffered output goes |
| rule | `@rule.register("n")` | `(variables, payload) -> [names]` | a config selector (the core ships `always`/`if_var`/`if_not_var`) |

Hooks and sinks receive a single **`CallContext`** carrying everything about the call:
`func`, `args`, `kwargs`, `stage`, `result`, `exception`, a `scratch` dict for passing
state between stages, a per-call `buffer`, and `toolbox` (the owning instance). Wrappers
run *inside* the call and log via the module-level `log()`, which finds the current
context automatically.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .            # installs the core
pip install -r requirements.txt   # demo deps (PyYAML, tenacity)
python3 main.py
```

## The three user-facing files

- **`my_toolbox.py`** — define your toolbox: subclass `ToolBox`, give it a `name`
  (its YAML section), declare `variables` (e.g. `DEBUG`), and list `features`.
- **`config.yaml`** — declare which pieces are active and under what conditions.
- **`main.py`** — your code; decorate functions with the toolbox.

## Writing a piece

```python
from toolbox import hook, CallContext

@hook.register("track_time", stages=("before", "after"))
def track_time(ctx: CallContext):
    if ctx.stage == "before":
        ctx.scratch["start"] = perf_counter()
    else:
        ctx.log(f"RUNTIME: {perf_counter() - ctx.scratch['start']:.3f}s")
```

Importing the module that contains this is all it takes to register it. Names are
unique per kind — a duplicate name raises immediately rather than silently overriding.

## Config grammar

Each section maps 1:1 to a kind (`hooks`, `wrappers`, `sinks`). Inside a section, the
selector rules decide what is active:

```yaml
my_toolbox:
  hooks:
    always:
      - track_info
    if_var:
      DEBUG:
        - track_time
  wrappers:
    always:
      - retry
  sinks:
    if_var:
      DEBUG: [terminal]
    if_not_var:
      DEBUG: [file]
```

Toolboxes inherit config through the class hierarchy: a subclass's YAML section is
deep-merged over its parents' (lists extend, dicts merge).

## Error handling

A toolbox instance is the decorator. Used bare, it applies the configured pieces:

```python
from my_toolbox import error_toolbox

@error_toolbox
def do_work(...):
    ...
```

To replace a `try/except` with a one-liner, hand the decorator an `on_error` lambda.
It is **not** a registered piece and lives nowhere in config — it is freeform code,
bound to that one function, that the framework calls when the function raises. The
contract is a single rule:

> The lambda receives the exception `e`. **Return an exception instance → the framework
> raises it. Return anything else (including `None`) → that value becomes the call's
> result** (the error is swallowed and that's your fallback).

That one rule covers the whole suite:

```python
@error_toolbox(on_error=lambda e: None)                     # swallow → fallback is None
@error_toolbox(on_error=lambda e: {"ok": False})            # swallow with a fallback value
@error_toolbox(on_error=lambda e: e)                        # re-raise the original (traceback kept)
@error_toolbox(on_error=lambda e: ApiError(str(e)))         # translate (chained from the original)
@error_toolbox(on_error=lambda e: None if isinstance(e, TimeoutError) else e)   # branch by type
@error_toolbox(on_error=lambda e: handle(e))                # delegate arbitrary logic to a function
```

A lambda is a single expression, so it cannot contain a `raise` statement — returning
the exception is how you raise from one. For anything beyond a one-liner, point the
lambda at a normal function (`lambda e: handle(e)`); the same return rule applies to
whatever that function hands back.

Logging is unaffected: the configured `on_error` hooks and sinks still fire on every
exception regardless of what the lambda decides. The lambda may read the call's
`CallContext` via `current_context()`, but should never write per-function state into it.

### Routing by exception type

For per-type handling, `catch` (in the reference bundle) compiles a `{type: handler}`
map into a single `on_error` lambda — the core still only ever sees one callable:

```python
from examples.toolbox_basic import catch

@error_toolbox(on_error=catch({
    ValueError: lambda e: "<bad input>",          # swallow with fallback
    KeyError:   lambda e: e,                       # re-raise the original
    Exception:  lambda e: AppError(str(e)),        # translate everything else
}))
def do_work(...):
    ...
```

Matching walks the exception's MRO, so the **most specific type wins regardless of map
order**; `Exception` is the catch-all (the last type every exception's MRO reaches); an
unmatched exception propagates untouched. Tuple keys group types
(`(ValueError, TypeError): handler`). Each
handler obeys the same return rule as a plain `on_error` — `catch` only *selects*, it
doesn't change the contract.

## Off-path sinks

Sinks run inline in the wrap pipeline, so a sink doing slow I/O (a file write, a network
send) adds latency to the call it's attached to. To move that work off the request path,
wrap any sink with `background` — it hands the work to a shared daemon worker and returns
immediately:

```python
from examples.toolbox_basic import background
from examples.toolbox_basic.sinks import file

sink.register("file_background")(background(file))   # the bundle already registers this one
```

Then wire `file_background` instead of `file` in config. The engine is unchanged and stays
synchronous — only the chosen sink runs off-path; the caller pays just the enqueue cost.
The worker uses a **bounded queue** (drops under sustained overload rather than growing
memory or blocking the caller), flushes on interpreter exit, and swallows send failures to
stderr so an off-path failure never surfaces on the request path. The snapshot handed to
the worker is the call's `CallContext`; background sinks must not rely on
`current_context()`, which doesn't cross the thread boundary.

## How pieces are discovered

Three channels, checked at startup:

1. **Auto prefix-scan (zero-config).** Any installed top-level package named
   `toolbox_*` is imported automatically. This is the `pip install` path — install a
   bundle and it self-registers, no configuration:
   ```bash
   pip install toolbox-basic   # provides the `toolbox_basic` package → picked up
   ```
2. **`features` list.** On your toolbox, list module names, a `.py` file, or a
   directory to collect pieces from:
   ```python
   class MyToolbox(ToolBox):
       features = ["examples.toolbox_basic", "myproject/pieces/"]
   ```
3. **Manual import.** Importing any module that registers pieces works on its own.

Set `auto_discover = False` on your toolbox to opt out of the prefix-scan.

## File layout

```
toolbox/                 core — architecture only
  registry.py            the one Registry primitive
  registries.py          the four kind instances (hook/wrapper/sink/rule)
  context.py             CallContext + current-context logging
  selectors.py           always / if_var / if_not_var
  core.py                ToolBox: config load, MRO merge, wrap() pipeline
  discovery.py           prefix-scan + features-list loading
examples/toolbox_basic/  reference bundle (instrument, retry, sinks, errors, catch, background)
config.yaml  my_toolbox.py  main.py   demo wiring
```

## Roadmap

- Split `examples/toolbox_basic/` into its own installable distribution (`toolbox-basic`).
- ASGI/WSGI support and async pieces (the `CallContext` is already `contextvars`-based,
  so it carries correctly across `await`).
