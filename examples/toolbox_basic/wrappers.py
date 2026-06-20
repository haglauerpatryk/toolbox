import functools

from tenacity import (
    RetryCallState,
    retry as _retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_fixed,
)

from toolbox import current_context, log, wrapper


class FormatError(Exception):
    """Raised by `validate` when a result fails its expected shape."""


class RateLimitExceeded(Exception):
    """Raised by `rate_limit` when a function exceeds its allowance."""


# memoize cache and rate-limit counters live here, not in ctx.
_memo = {}
_rate = {}


def reset():
    _memo.clear()
    _rate.clear()


@wrapper.register("retry")
def retry(func):
    @_retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        retry=retry_if_exception_type(Exception),
        before_sleep=_log_attempt,
    )
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapped


@wrapper.register("memoize")
def memoize(func):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        key = (func.__name__, args, tuple(sorted(kwargs.items())))
        if key in _memo:
            log("[MEMO] hit")
            return _memo[key]
        result = func(*args, **kwargs)
        _memo[key] = result
        log("[MEMO] store")
        return result

    return wrapped


@wrapper.register("rate_limit")
def rate_limit(func):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        limit = _variables().get("RATE_LIMIT", 60)
        name = func.__name__
        _rate[name] = _rate.get(name, 0) + 1
        if _rate[name] > limit:
            raise RateLimitExceeded(f"{name} exceeded {limit} calls")
        return func(*args, **kwargs)

    return wrapped


@wrapper.register("validate")
def validate(func):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        result = func(*args, **kwargs)
        required = _variables().get("REQUIRED_KEYS", [])
        if required:
            if not isinstance(result, dict):
                raise FormatError(f"expected dict, got {type(result).__name__}")
            missing = [k for k in required if k not in result]
            if missing:
                raise FormatError(f"missing keys: {missing}")
        log("[VALID] format ok")
        return result

    return wrapped


def _variables():
    ctx = current_context()
    return (getattr(ctx, "toolbox", None) and getattr(ctx.toolbox, "variables", None)) or {}


def _log_attempt(state: RetryCallState):
    log(f"[RETRY] Attempt {state.attempt_number} failed with: {state.outcome.exception()}")
