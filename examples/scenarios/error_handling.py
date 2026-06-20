"""The on_error lambda as a full replacement for try/except.

Each function pairs a real failure with a one-line `on_error` lambda; the comment
shows the try/except it stands in for. The lambda is a single expression, but it
can call any function, reach the original call's arguments via `current_context()`,
run side effects with `or`, and decide per-exception whether to recover or re-raise.
"""

from toolbox import ToolBox, current_context

from examples.toolbox_basic import catch

# Side stores for the patterns below; reset between tests.
CACHE = {}
DEAD_LETTER = []
ALERTS = []


def reset():
    CACHE.clear()
    DEAD_LETTER.clear()
    ALERTS.clear()


ERROR_DEMO = {
    "error_demo": {
        "hooks": {"always": ["handle_problem"]},  # logging still fires on every error
        "sinks": {"always": ["memory"]},
    }
}


class ErrorDemo(ToolBox):
    name = "error_demo"
    config_sources = [ERROR_DEMO]
    features = ["examples.toolbox_basic"]


errors = ErrorDemo()


class ServiceError(Exception):
    """A safe, client-facing error that never carries internal detail."""


class Response:
    def __init__(self, status, body):
        self.status = status
        self.body = body


# 1. Failover to a backup with the SAME arguments.
#    try: _primary(region)  except: _secondary(region)
def _primary_region(region):
    raise ConnectionError(f"primary down for {region}")


def _secondary_region(region):
    return {"region": region, "source": "secondary"}


@errors(on_error=lambda e: _secondary_region(*current_context().args, **current_context().kwargs))
def fetch_region(region):
    return _primary_region(region)


# 2. Graceful degradation: serve the last-known-good value from cache.
#    try: live(symbol)  except: cache.get(symbol)
def _live_price(symbol):
    raise TimeoutError("market feed timeout")


@errors(on_error=lambda e: CACHE.get(current_context().args[0]))
def get_price(symbol):
    return _live_price(symbol)


# 3. Best-effort transform: on failure, return the input unchanged.
#    try: value.strip().lower()  except: value
@errors(on_error=lambda e: current_context().args[0])
def normalize(value):
    return value.strip().lower()


# 4. Dead-letter handoff: enqueue the failed work elsewhere, return a deferred ack.
#    try: process(job)  except: dead_letter.put(job); return {"status": "deferred"}
@errors(
    on_error=lambda e: DEAD_LETTER.append({"job": current_context().args[0], "error": str(e)})
    or {"status": "deferred"}
)
def process_job(job_id):
    raise RuntimeError(f"worker crashed on {job_id}")


# 5. Observe then propagate: alert on failure but re-raise the original.
#    try: op()  except: alert(); raise
@errors(on_error=lambda e: ALERTS.append(f"{type(e).__name__}: {e}") or e)
def critical_op():
    raise ValueError("invariant violated")


# 6. Conditional re-raise: propagate retryable errors, swallow terminal ones.
#    try: sync(r)  except Retryable: raise  except: return {"status": "skipped"}
def _is_retryable(e):
    return isinstance(e, (TimeoutError, ConnectionError))


@errors(on_error=lambda e: e if _is_retryable(e) else {"status": "skipped", "reason": str(e)})
def sync_record(record):
    if record == "flaky":
        raise TimeoutError("downstream slow")
    raise ValueError(f"malformed: {record}")


# 7. Sanitize before propagating: never leak internal detail to the caller.
#    try: internal()  except Exception as e: raise ServiceError("...") from e
@errors(on_error=lambda e: ServiceError("service temporarily unavailable"))
def charge_account(account, secret_token):
    raise RuntimeError(f"db auth failed with token={secret_token}")


# 8. Result envelope: never raise; both paths return a uniform object.
#    try: {"ok": True, ...}  except: {"ok": False, ...}
@errors(on_error=lambda e: {"ok": False, "error": str(e)})
def divide(a, b):
    return {"ok": True, "value": a / b}


# 9. Boundary mapping: turn exception types into HTTP-style responses (via catch).
@errors(
    on_error=catch(
        {
            KeyError: lambda e: Response(404, "not found"),
            PermissionError: lambda e: Response(403, "forbidden"),
            Exception: lambda e: Response(500, "internal error"),
        }
    )
)
def handle_request(route):
    if route == "missing":
        raise KeyError(route)
    if route == "private":
        raise PermissionError(route)
    if route == "boom":
        raise RuntimeError("unexpected")
    return Response(200, "ok")
