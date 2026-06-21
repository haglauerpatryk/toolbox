# TODO — Closing the gap to "the logging & error-handling layer"

This file tracks the concerns raised in evaluating `toolbox` **against its intended
role**: a tool that absorbs the *entire overhead of logging and error handling* for an
application (concretely, a centralised layer for a Django startup).

The framework is a clean engine for attaching config-driven cross-cutting behaviour to
functions. The items below are where it currently falls short of *being the logging and
error layer itself*, rather than just a generic wrapping mechanism. Each item states the
concern, the evidence in code, why it matters for the goal, and the implication so a
future change can be designed without re-deriving the reasoning.

Severity legend: **P0** blocks the stated goal · **P1** materially undercuts it · **P2**
quality / robustness.

---

## 1. Logging is reinvented, not integrated  — **P0** ✅ DONE

**Resolved.** Records are now leveled + structured (`LogRecord`: level/msg/fields/created
in `toolbox/context.py`); the front door `log()` / `ctx.log()` takes a level + `**fields`
with `log.debug/info/warning/error/critical` helpers, and falls back to the `toolbox`
logger when called outside a call (1e). A new **`logging` sink** (`examples/toolbox_basic/
sinks.py`) is the swappable seam: it replays each record into a named `logging.Logger`,
passing fields + call context via `extra=` and preserving the log-time timestamp — so
levels (1b), destinations/formats (handlers/formatters, host-owned), and structured fields
(1d) are all the library's job. Buffered emit kept (the `finally`/sink position = "always
emit"); immediate emit (1c) deliberately deferred.

Also folded in **item 3 (piece-failure isolation)** since it's a prerequisite for real I/O
in sinks: `_run_piece` in `toolbox/core.py` now runs every hook/sink fail-open, reporting
to the `toolbox` logger, so a broken piece can't skip a call, mis-route to on_error, or
mask a result/exception. Covered by new tests in `tests/core/test_wrap.py`.

**Deviation from plan:** kept `terminal`/`file`/`json_lines` (reimplemented over records)
instead of retiring them — lower blast radius. The `logging` sink is the new default
(`config.py`). **Follow-up:** README still documents the old buffer/sink model and needs
updating; item 3 below is now effectively done.

---

### Original analysis (kept for reference)

This was the load-bearing gap. The whole pitch is "manage the overhead of logging," but
the tool builds a *second, parallel* logging channel that ignores the logging stack it is
supposed to manage. A Django app already has `LOGGING`: handlers, levels, formatters, and
aggregation (JSON-to-stdout, Sentry, etc.). Today this framework neither reads nor feeds
that stack.

The logging model is a per-call buffer of strings (`CallContext.buffer: list`,
`toolbox/context.py:18`), appended via `log()` / `ctx.log()` (`toolbox/context.py:20`,
`:28`), then flushed by sinks at the end of the call. That single design choice produces
five distinct sub-problems:

### 1a. No integration with the standard library `logging`
- **Evidence:** nothing in `toolbox/` imports `logging`. Sinks write to `print`/files
  directly (`examples/toolbox_basic/sinks.py`).
- **Why it matters:** instead of *absorbing* existing logging overhead, the tool *adds*
  to it — operators now have two places to configure, two formats, two destinations.
- **Implication / direction:** there should be a first-class path that emits through a
  `logging.Logger` (so existing handlers, formatters, and aggregation just work), with
  the buffer/sink model becoming one *optional* sink rather than the only channel.

### 1b. No log levels
- **Evidence:** `buffer` is an undifferentiated `list[str]`; there is no severity
  anywhere. `VERBOSE` is a *build-time selector* (which pieces attach,
  `toolbox/selectors.py` + `config.py`), not a runtime level.
- **Why it matters:** you cannot filter, threshold, or route by DEBUG/INFO/WARNING/ERROR
  — table stakes for a logging layer.
- **Implication:** introduce a real level on each log record; let level (not just
  piece-selection) drive what is emitted and where.

### 1c. Buffered emit loses the logs you most want
- **Evidence:** sinks fire only in the `finally` at the end of `wrap()`
  (`toolbox/core.py:179-181`); nothing is emitted mid-call.
- **Why it matters:** if a call hangs or the process is killed mid-execution, the
  buffered lines for every in-flight call are never flushed — exactly the crash/hang you
  are trying to debug.
- **Implication:** support immediate emit (stream as logged), with buffering as an opt-in
  for the cases where a single consolidated record per call is genuinely wanted.

### 1d. String-only payload caps structured logging
- **Evidence:** the contract is "append a string." The `json_lines` sink can therefore
  only dump pre-rendered text as `"log": [...]` (`examples/toolbox_basic/sinks.py`).
- **Why it matters:** you cannot emit real key/value fields, so structured/observability
  backends get opaque strings instead of queryable data.
- **Implication:** the log primitive should accept structured fields (message + kwargs /
  a record object), with text rendering as a downstream concern of the sink.

### 1e. `log()` silently no-ops outside a context
- **Evidence:** `toolbox/context.py:28-31` — `log()` returns silently when there is no
  current context.
- **Why it matters:** a piece (or user code) that logs off the call path drops the
  message with no signal — quiet data loss in a tool whose job is not to lose telemetry.
- **Implication:** decide deliberately — fall back to a module logger, or warn — rather
  than silently discard.

---

## 2. Error *policy* is not actually centralised  — **P1**

The goal includes managing error-handling overhead centrally, but the decision of *what
to do on failure* lives at each decoration site, not in config.

- **Evidence:** the `on_error` lambda is passed per-decoration (`toolbox/core.py:187-190`,
  used throughout `main.py`) and, by deliberate design, lives nowhere in config. Config
  centralises only the *observation* of errors — the `on_error` hooks and sinks
  (`toolbox/core.py:166-169`). `catch()` (`examples/toolbox_basic/catch.py`) makes each
  site compact but is still authored site-by-site.
- **Why it matters:** "manage the entire overhead of error handling" implies a central
  place to express recovery/translation policy; right now that policy is sprinkled across
  call sites as lambdas.
- **Context / tension:** keeping `on_error` out of config is an intentional design
  principle (it is the sole function-level escape hatch, and config must never be able to
  introduce code). So this is **not** simply "move it into config" — any solution must
  preserve that invariant. The open question is whether *reusable, named* error policies
  (a registered kind, referenced from config, that still resolve to one callable) can give
  central management without letting config smuggle in arbitrary code.
- **Implication:** explore a registered "policy" piece that config can *select* (like
  hooks/wrappers/sinks) which compiles to an `on_error` callable, so common recovery
  shapes are defined once and reused, while bespoke one-offs stay as inline lambdas.

### 2a. `on_error` contract conflates control and data (sub-note)
- The rule "return an exception → raise it; return anything else → that is the result"
  (`toolbox/core.py:172-178`) is elegant but cannot express "the successful fallback value
  *is itself* an exception object," and `None` ("I didn't really handle it") is
  indistinguishable from "swallow with `None`." Low priority, but document the edge so any
  redesign of the contract is intentional.

---

## 3. The framework is not hardened against its own pieces failing  — **P1**

For a tool whose job is reliability, it can itself become the source of an unhandled error
or can mask the real one.

- **Before-hook failure escapes the call.** `before` hooks run *outside* the inner
  try/except: the loop at `toolbox/core.py:152-154` precedes the guarded block at
  `:159-178`. A raising observability hook therefore crashes the user's function and never
  reaches the `on_error` path.
- **A raising sink masks the result/exception.** Sinks run in the `finally`
  (`toolbox/core.py:179-181`); an exception from a sink propagates out of `finally` and
  replaces whatever the call was about to return or raise. `background`
  (`examples/toolbox_basic/background.py`) mitigates this for the off-path file case, but
  every inline sink is exposed.
- **Why it matters:** instrumentation should never be able to change program outcome. A
  logging/error layer that can turn a healthy call into a crash — or swallow the genuine
  exception behind a sink bug — undermines the very guarantee it exists to provide.
- **Implication:** isolate piece execution (hooks and sinks) so a misbehaving piece is
  caught, reported through a defined channel, and cannot alter the wrapped call's result
  or mask its exception. Decide the policy explicitly (fail-open vs. fail-loud) rather
  than inheriting it from control-flow accident.

### 3a. Catches `Exception`, not `BaseException` (sub-note)
- `toolbox/core.py:165` catches `Exception`, so `KeyboardInterrupt`/`SystemExit` bypass
  `on_error` and the on_error hooks. Usually correct, but make it a deliberate, documented
  choice.

---

## 4. Per-function granularity + sync-only is a poor fit for "entire overhead" in Django — **P1**

There is a structural mismatch between the goal's scope (app-wide) and the mechanism's
scope (one function at a time).

- **Granularity.** The unit of application is a single decorated function
  (`toolbox/core.py:wrap`). To cover "the entire app" you decorate many functions by hand;
  there is no hook into Django's request lifecycle, middleware, or its `LOGGING` config.
  "Entire overhead" (app-wide) vs. opt-in per-function decoration is a real gap to close
  or to scope down explicitly.
- **Sync-only.** `wrap()` defines a synchronous `wrapped` (`toolbox/core.py:146`). Wrapping
  a coroutine returns the coroutine object with hooks/sinks firing *before* it is awaited —
  so async request paths cannot be wrapped correctly today. The README lists async as
  roadmap; `CallContext` is already `contextvars`-based (`toolbox/context.py:5`), which is
  the right foundation, but the engine itself is not async-aware.
- **Why it matters:** modern Django is increasingly async, and the request paths that
  carry the most logging/error value are exactly the ones a sync wrapper cannot handle.
- **Implication:** decide the intended integration surface (middleware-level adapter?
  per-view decorator? both) and add an async-capable `wrap` path. Either is a substantial
  design item; flagging so scope is chosen deliberately.

---

## 5. Wrapper chain is recomposed on every call  — **P2**

- **Evidence:** the middleware chain is rebuilt inside `wrapped` on each invocation —
  `for w in reversed(cfg.wrappers): inner = w(inner)` (`toolbox/core.py:155-157`).
- **Why it matters:** it is avoidable per-call work on a hot path, in a tool that markets
  itself as managing overhead.
- **Context / tradeoff:** rebuilding per call is what keeps `reconfigure` swaps trivial —
  the chain always reflects the latest `cfg` captured once at the top of the call
  (`toolbox/core.py:147`). Any optimisation (e.g. compose-once and invalidate on
  reconfigure) must preserve the "a call reads one consistent config" guarantee.
- **Implication:** low priority; revisit only if profiling shows it matters, and keep the
  config-swap semantics intact.

---

## Notes on what NOT to break

These existing properties are correct and should survive any change above:
- The fast path that returns the function untouched when nothing is configured and there
  is no `on_error` (`toolbox/core.py:142`).
- The config machinery: ordered sources, deep-merge, MRO inheritance, dedupe-with-warning,
  build-then-swap `reconfigure`, the name-handshake, and `validate`
  (`toolbox/core.py`, `toolbox/config/loader.py`, `toolbox/inspect.py`).
- The invariant that **config can rewire registered pieces but can never introduce code**
  (relevant to item 2).
- Aggregate state living in module scope, never in `ctx` (the per-call context stays
  per-call).
