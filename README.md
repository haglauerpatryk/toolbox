# toolbox

A small, config-driven **function-wrapping architecture**. The core ships with *no*
behavior of its own — you decorate a function, and config (YAML, JSON, or a plain dict)
declaratively decides what runs around each call (instrumentation, logging, retries,
error handling).

The behaviors themselves ("lego pieces") live **outside** the core. You install a
bundle, write your own, or both.

> For the mental model — the layers, the design principles, and a cheat sheet for **what
> belongs where** (source and tests) — see [ARCHITECTURE.md](ARCHITECTURE.md).

## Concepts

Two layers, kept strictly separate:

- **Core (`toolbox/`)** — the architecture. Installable on its own and does nothing
  until a piece registers. Provides the `ToolBox` engine, the config machinery,
  the `CallContext`, and the four registries pieces plug into.
- **Pieces (features)** — the lego bricks. Each is a small function registered under a
  name with one of four decorators. They live in feature bundles (e.g.
  `examples/toolbox_basic/`) or in your own project.

### The four kinds

Every extension point uses the **same** convention: `@<kind>.register("<name>")`, where
`<name>` is the exact string you reference in your config.

| Kind | Decorator | Signature | What it is |
|------|-----------|-----------|------------|
| hook | `@hook.register("n", stages=("before","after","on_error"))` | `(ctx)` | observer that runs at lifecycle points |
| wrapper | `@wrapper.register("n")` | `(func) -> func` | middleware that wraps the call (can alter control flow) |
| sink | `@sink.register("n")` | `(ctx)` | where each call's log records go (the default emits to stdlib `logging`) |
| rule | `@rule.register("n")` | `(variables, payload) -> [names]` | a config selector (the core ships `always`/`if_var`/`if_not_var`) |

Hooks and sinks receive a single **`CallContext`** carrying everything about the call:
`func`, `args`, `kwargs`, `stage`, `result`, `exception`, a `scratch` dict for passing
state between stages, a per-call list of structured log `records`, and `toolbox` (the
owning instance). Wrappers run *inside* the call and log via the module-level `log()`,
which finds the current context automatically. See [Logging](#logging) for the record
model and the standard-library backend.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .            # installs the core
pip install -r requirements.txt   # demo deps (PyYAML, tenacity)
python3 main.py
```

Run the tests:

```bash
pip install -e ".[test]"    # pytest + tenacity
pytest
```

## The user-facing files

- **`config.py`** — a base config authored as a Python dict (`BASE`); treat it as
  the production source of truth.
- **`configs/`** — a directory of YAML files merged on top of the base in dev.
- **`my_toolbox.py`** — define your toolbox: subclass `ToolBox`, give it a `name`
  (its config section), set `config_sources`, declare `variables`, list `features`.
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

## Logging

Logging is **integrated, not reinvented.** A piece emits with `log()` (module-level, finds
the current call) or `ctx.log()` — both take a level and arbitrary structured fields:

```python
from toolbox import log

log("started")                                  # INFO by default
log.warning("slow upstream", latency_ms=812)    # level + structured fields
log.error("charge failed", order_id=order.id)
```

Each call accumulates these as structured `LogRecord`s (level, message, fields, and a
log-time timestamp) on its `CallContext.records`. They are **not** emitted as they happen —
they're buffered and flushed once, at the end of the call, by a **sink**. That is the
"always emit" point: sinks run in a `finally`, so every record produced on any path (success,
error, or recovery) is flushed. A log emitted *outside* any wrapped call doesn't vanish — it
falls back to the `toolbox` logger.

### The logging sink — the backend seam

The default sink, `logging`, hands each record to a named `logging.Logger`
(`toolbox.<toolbox>.<function>`), passing the structured fields and call context through
`extra=` and preserving the log-time timestamp. That is the whole integration: **levels,
destinations, formatting, and routing are the standard library's job** — you configure them
with ordinary handlers/formatters (or Django's `LOGGING`). Dev-console vs. JSONL production
output is a *formatter* choice on a handler, not framework code:

```python
import logging
logging.basicConfig(level=logging.INFO)   # the host owns logging configuration
```

Because the backend lives behind a sink, it is swappable: to move to structlog (or anything
else) you write one sink and name it in config — the core never changes. The bundle also
ships `terminal`/`file`/`json_lines` as convenience sinks that render records directly, and
`logging_background` to run emission off the request path (see [Off-path sinks](#off-path-sinks)).

### Instrumentation can't break your call

Every hook and sink runs **fail-open**: if a piece raises, the failure is caught, reported
to the `toolbox` logger, and the call's result or exception is left untouched. A broken
`before` hook won't skip the call, a broken `after` hook won't be mis-routed into the error
path, and a sink whose I/O fails won't mask your result. Observability can never change what
your function does — only wrappers (deliberately *inside* the call) and your `on_error`
lambda affect control flow.

## Config grammar

Each section maps 1:1 to a kind (`hooks`, `wrappers`, `sinks`). Inside a section, the
selector rules decide what is active. `VERBOSE` below is just a name *you* chose — the
framework has no built-in variables (no special `DEBUG`); a selector reads whatever you
put in the toolbox's `variables`:

```yaml
my_toolbox:
  hooks:
    always:
      - track_info
    if_var:
      VERBOSE:
        - track_time
  wrappers:
    always:
      - retry
  sinks:
    always:
      - logging                # emit through stdlib logging on every call
    if_var:
      VERBOSE: [terminal]      # also echo a rendered block to the console in dev
```

Toolboxes inherit config through the class hierarchy: a subclass's section is
deep-merged over its parents' (lists extend, dicts merge). A toolbox **must** name
its own section in the resolved config — even an empty `my_toolbox:` — or construction
fails. This handshake confirms a toolbox is pointed at config meant for it, rather than
silently coming up empty when a section name is wrong or missing.

## Config sources

A toolbox builds its config from `config_sources`, an **ordered list**. Each entry is a
**dict**, a **file path**, or a **directory**; they are deep-merged left-to-right. Order
is the *only* precedence rule — arrange the list to decide what overrides what:

```python
from config import BASE   # a Python dict

class MyToolbox(ToolBox):
    config_sources = [BASE, "configs/"]   # base, then the yaml dir on top
    variables = {"VERBOSE": 1}
```

- **dict** — used as-is. This is the slot for **JSON**: hand in a dict you parsed
  yourself (e.g. fetched from an API). The framework never reaches for a JSON file —
  *you* own how it arrives. File paths are still read by extension (`.yaml`/`.yml`/`.json`),
  so a JSON file works too if that's your case.
- **file** — deserialized by extension; YAML and JSON resolve to the same shape.
- **directory** — every `*.yaml`/`*.yml`/`*.json` inside, sorted, merged (files
  beginning with `_` are skipped).

Dev vs. prod is *your* composition, not a framework mode: list `[BASE, "configs/"]`
locally; pass `[BASE]` (or your API dict alone) in production. A constructor override —
`MyToolbox(config_sources=[...])` — is the natural slot for a config assembled at runtime.

On overlap, scalars and dict-keys take the later source; **lists are appended and then
de-duplicated**. Dedup runs after resolution (so it catches repeats from any origin —
multiple files, a directory, or class inheritance), keeping the first occurrence and
printing a yellow warning naming what was dropped. Two toolbox flags control it:

```python
dedupe = True          # set False to keep duplicates (a piece can then run twice)
warn_on_dedupe = True  # set False to dedupe silently
```

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

The return rule is about exceptions you *choose*. A policy can also raise simply because
something it **calls** raised — and that exception propagates, chained to the original as
its context (`backup failure … during handling of primary failure`). This is deliberate:
it is how a failover handler surfaces a backup's failure (`lambda e: call_backup(...)` —
if the backup also fails, the caller sees *that* error). So: to translate to a *chosen*
exception, **return** it (cleanly chained via `from e`); to let a downstream failure
propagate, just let it raise. The framework can't tell a deliberate downstream raise from
a bug in your policy, so keep policies total and side-effect-light.

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

### Patterns

The lambda is one expression, but it can call any function, reach the original call's
arguments via `current_context()`, run a side effect with `or`, and branch — so it covers
nearly every `try/except` you'd write. `examples/scenarios/error_handling.py` works through
nine real ones: failover to a backup with the same arguments, degrade to a cached value,
best-effort passthrough, dead-letter handoff, observe-then-re-raise (`alert(e) or e`),
conditional re-raise of retryable errors, sanitize-before-propagating (don't leak internals),
a uniform result envelope, and HTTP-style boundary mapping. The configured `on_error` hooks
and sinks still fire regardless of what the lambda decides.

## Dynamic config

A toolbox builds its config once, but `reconfigure(config_sources)` rebuilds it and swaps
it onto the **live** instance — for config pushed at runtime (e.g. from an admin panel)
while the app keeps serving:

```python
app.reconfigure([BASE_LOGGING, admin_payload])   # full replace, not a merge
```

It is a full replace: you compose the source list yourself (always include your base
logging floor). The swap is safe by construction:

- **Build-then-swap** — the new config is fully built and validated first; a bad payload
  (unknown piece, or missing the name handshake) raises *before* anything changes, so the
  running config stays live.
- **A call reads its config once**, so a request in flight finishes on the config it
  started with; the next request sees the new one. The reference swap is atomic (no lock).
- Config can only re-wire **already-registered** pieces — it can never introduce code.
- **File sources are read once.** A file or directory path is deserialized from disk the
  first time it's loaded and then cached for the life of the process; a live `reconfigure`
  therefore picks up new content only from **dict** payloads (e.g. JSON from your admin
  API), not from edits to a file already read at startup. Pass runtime config as a dict.

## Off-path sinks

Sinks run inline in the wrap pipeline, so a sink doing slow I/O (a file write, a network
send) adds latency to the call it's attached to. To move that work off the request path,
wrap any sink with `background` — it hands the work to a shared daemon worker and returns
immediately:

```python
from examples.toolbox_basic import background
from examples.toolbox_basic.sinks import logging_sink

sink.register("logging_background")(background(logging_sink))   # the bundle already registers this one
```

Then wire `logging_background` instead of `logging` in config (the bundle also ships
`file_background` for the file sink). The engine is unchanged and stays
synchronous — only the chosen sink runs off-path; the caller pays just the enqueue cost.
The worker uses a **bounded queue** (drops under sustained overload rather than growing
memory or blocking the caller), flushes on interpreter exit, and swallows send failures to
stderr so an off-path failure never surfaces on the request path. The snapshot handed to
the worker is the call's `CallContext`; background sinks must not rely on
`current_context()`, which doesn't cross the thread boundary.

## Introspection

`toolbox/inspect.py` is a read-only CLI for checking complex setups **without running
anything** — it loads only when invoked, so it adds nothing to a running app (the one
enabling change is a single `__toolbox__` tag set on each wrapper at decoration, never on
the call path):

```bash
python -m toolbox.inspect inspect  examples.scenarios.payments.charge   # the wrap stack
python -m toolbox.inspect validate examples.scenarios.payments.Payments # build-check a config
```

`inspect` walks a function's wrap stack (which toolboxes are attached, outermost first,
with each one's active pieces) and flags any piece active in **more than one layer** — a
duplicate the per-toolbox dedup can't catch, because stacked toolboxes are independent.
`validate` builds a toolbox's config (handshake + every referenced piece exists) and exits
non-zero on a problem — handy in CI or as a pre-flight before an admin `reconfigure`.

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
  context.py             CallContext + structured LogRecord + current-context logging
  selectors.py           always / if_var / if_not_var
  core.py                ToolBox: source resolution, MRO merge, dedupe, wrap(), reconfigure
  discovery.py           prefix-scan + features-list loading
  inspect.py             read-only introspection CLI (python -m toolbox.inspect)
  config/                config loading, separated by concern
    yaml.py  json.py     per-format deserializers (text -> dict)
    loader.py            extension dispatch, source merge, dedupe
examples/
  toolbox_basic/         reference bundle: instrument, metrics,
                         sinks (logging backend seam + terminal/file/json_lines),
                         wrappers (retry/memoize/rate_limit/validate),
                         rules (if_env/if_equals), errors, catch, background
  configs/               example configs — service.yaml + service.json (equivalent),
                         base.py, prod.json, logging.yaml, overlays/ (ordered merge)
  scenarios/             production usage: diagnostics, payments, llm_api,
                         platform (inheritance), dynamic (live reconfigure),
                         error_handling (on_error patterns)
  run_scenarios.py       `python -m examples.run_scenarios`
config.py  configs/  my_toolbox.py  main.py   demo wiring
```

## Production examples

`examples/scenarios/` shows the architecture composed for real use cases — each is a
toolbox plus config, no core changes:

- **`diagnostics`** — make any function observable for local dev (counts, args, timing,
  slow-call warnings), gated by a plain `VERBOSE` variable.
- **`payments`** — an advanced decorator that turns exceptions into business outcomes via
  `catch` (validation/decline → structured results, network error → re-raised for an
  idempotent caller), auditing every attempt to a JSONL stream. Deliberately no retry.
- **`llm_api`** — a flaky API: `[rate_limit, retry, validate]` so a malformed response
  raises `FormatError`, `retry` re-runs the call, and on persistent breakage the
  `on_error` lambda yields a safe fallback instead of crashing the request path.
- **`platform`** — toolbox inheritance: a shared `PlatformBase` (diagnostics) that both a
  payments and an LLM service derive from, reusing the same processing under inherited
  wiring. The payments service re-declares a base hook, so its section overlaps the base
  and you see the dedup warning fire across the class hierarchy.
- **`dynamic`** — hot-swap a live toolbox's config from an admin API. Base logging is the
  always-on floor; each push *replaces* the dynamic config wholesale, a bad payload is
  rejected before anything changes, and an in-flight request finishes on the config it
  started with.
- **`error_handling`** — nine real `try/except` idioms written as one-line `on_error`
  lambdas: failover, cache fallback, dead-letter, observe-then-re-raise, conditional
  re-raise, sanitize-and-propagate, result envelopes, and type-based boundary mapping.

`examples/configs/` carries the same service config in YAML *and* JSON (they resolve
identically), a Python base dict, a production JSON payload, a base logging config for the
`dynamic` example, and an `overlays/` directory demonstrating ordered, de-duplicated
source merging.

## Roadmap

- Split `examples/toolbox_basic/` into its own installable distribution (`toolbox-basic`).
- ASGI/WSGI support and async pieces (the `CallContext` is already `contextvars`-based,
  so it carries correctly across `await`).
