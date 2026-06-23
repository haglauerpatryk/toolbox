# ping

Dev-only diagnostics for specific functions. Point it at a function or file; while
enabled it prints args, timing, result, and errors for *just those* — observing from
`sys.settrace`, never altering the call. It's a `ToolBox` subclass whose engine is a
trace hook instead of a decorator.

## Use

Pick targets (the CLI writes `ping/config/targets.json`):

```bash
python -m ping add app.services.charge     # a function (full or bare name)
python -m ping add app/services.py         # a whole file
python -m ping list
python -m ping off                          # pause without losing targets
```

Turn it on in your app — dev only, so gate it:

```python
import os
from ping import Ping

p = Ping()
if os.environ.get("PING"):
    p.enable()            # or scope it:  with Ping(): ...
```

Targets reload live (no restart). Output goes to stderr:

```
[ping] charge
  INFO  args=(42,) kwargs={'card': '...'}
  INFO  time=12.3ms
  INFO  -> dict {'ok': True}
```

## What it shows

Set in `ping/config/ping.yaml` — the toolbox selector grammar, choosing which
diagnostics run on a match:

| piece | shows |
|---|---|
| `ping_args` | call args / kwargs |
| `ping_time` | wall-clock per call |
| `ping_types` | result type + value |
| `ping_error` | the exception (which still propagates) |

These are ordinary toolbox hooks/sinks; name any registered piece here.

## Targets

- **function** — `module.qualname`, or a bare name.
- **file** — a `.py` path (or any path with a separator) → every function in it.

## Rules & limits

- **Observe-only.** Can't change a result or swallow an error — no bug a raw `print`
  wouldn't have. Wrappers (control-flow pieces) are rejected.
- **Dev-only.** In production just never `enable()` — zero footprint.
- **Sync functions** only; generators/`async def` aren't handled yet.
- **Per-thread** (`threading.settrace` covers new threads) and adds tracing overhead
  while on — enable it while diagnosing, not always-on.

## CLI

`init · add <target> · rm <target> · list · clear · on · off · status`
