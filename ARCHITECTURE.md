# Architecture

The direction to hold. Usage details live in the [README](README.md).

## Layers

- **Core (`toolbox/`)** — the engine. Ships *no* behavior; only orchestrates.
- **Pieces (`examples/toolbox_basic/` or your bundle)** — the behavior. Named functions, config picks which run.
- **Use cases (`examples/scenarios/`, `examples/configs/`, demo wiring)** — services composed from the two above. No core changes.

## The four kinds

- **hook** `(ctx)` — observer at `before`/`after`/`on_error`. No control flow.
- **wrapper** `(func)->func` — middleware *inside* the call. **Affects control flow.**
- **sink** `(ctx)` — where a call's records go. Default implementation emits to stdlib `logging`. No control flow.
- **rule** `(variables, payload)->[names]` — a config selector.

## Principles (the invariants)

1. **Tiny core.** Behavior goes in pieces, never in `toolbox/`.
2. **Config selects code, never introduces it.** It can only name registered pieces — so `reconfigure()` can re-wire a live app but can't smuggle in code.
3. **`on_error` lambda is the *sole* function-level escape hatch.** Error policy is userland, passed at decoration — never config.
4. **Never pollute `ctx`.** Per-call scratch only; aggregate state lives in the piece's module.
5. **Instrumentation can't change outcomes.** Hooks/sinks are fail-open (caught, reported, ignored). Only wrappers + `on_error` alter control flow.
6. **Logging is integrated, not reinvented.** Pieces emit leveled/structured records; the `logging` sink hands them to stdlib; the host owns handlers/formats. Backend swappable by writing one sink.
7. **A call reads its config once.** In-flight calls finish on their config; the next sees the swap — lock-free `reconfigure()`.

## Error handling = userland

- Contract: `on_error(e)` returns an **exception → raised**, anything else → **becomes the result**.
- Static type routing → `catch({Type: handler})`. Stateful / predicate / hierarchy → your own factory or class. Both → `catch` inside a class.
- The policy *decides*; configured `on_error` hooks/sinks still *observe* every failure. Examples: `tests/scenarios/test_error_policies.py`.

## Where things go — source

- Engine change → `toolbox/` (orchestration only).
- Reusable piece → `examples/toolbox_basic/` (state in the module, not `ctx`).
- Usage demo → `examples/scenarios/`. Config artifact → `examples/configs/`.
- Error policy → userland. Logging backend → a new sink.

## Where things go — tests

Tests mirror the source layer they protect. Ask: *what source breaks this test?*

- `tests/core/` — the engine. **Synthetic inputs only; never imports `examples/…`.**
- `tests/bundle/` — the reference pieces.
- `tests/scenarios/` — use cases (`examples/scenarios/`, `examples/configs/`, demo wiring).
- conftest: root = path + registry rollback + config-cache + `toolbox_factory`; `bundle`/`scenarios` reset piece state per test.

## Use-case catalog (source ↔ test)

- Observability gated by a variable — `scenarios/diagnostics.py` ↔ `test_diagnostics.py`
- Exceptions → business outcomes via `catch`, JSONL audit — `scenarios/payments.py` ↔ `test_payments.py`
- Flaky API self-heals (`rate_limit,retry,validate` + fallback) — `scenarios/llm_api.py` ↔ `test_llm_api.py`
- Toolbox inheritance + cross-hierarchy dedupe — `scenarios/platform.py` ↔ `test_platform.py`
- Live config hot-swap — `scenarios/dynamic.py` ↔ `test_dynamic.py`
- Nine `on_error` idioms — `scenarios/error_handling.py` ↔ `test_error_handling.py`
- Userland error policies (factory/class/predicate/live-flag) — *(inline)* ↔ `test_error_policies.py`
- Demo wiring end-to-end — `config.py`/`my_toolbox.py`/`configs/` ↔ `test_integration.py`
- YAML ≡ JSON, ordered merge/dedupe — `examples/configs/` ↔ `test_formats.py`, `test_sources_scenarios.py`

Run: `python main.py`, `python -m examples.run_scenarios`.
