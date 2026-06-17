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
examples/toolbox_basic/  reference bundle (track_time, track_info, retry, sinks, errors)
config.yaml  my_toolbox.py  main.py   demo wiring
```

## Roadmap

- Split `examples/toolbox_basic/` into its own installable distribution (`toolbox-basic`).
- A wrapper that replaces hand-written `try/except` chains.
- ASGI/WSGI support and async pieces (the `CallContext` is already `contextvars`-based,
  so it carries correctly across `await`).
