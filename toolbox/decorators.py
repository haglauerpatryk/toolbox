import functools
from toolbox.logger import log
from tenacity import retry, stop_after_attempt, wait_fixed, RetryCallState, retry_if_exception_type

_decorator_registry = {}

def toolbox_decorator(name):
    def wrapper(func):
        _decorator_registry[name] = func
        return func
    return wrapper

@toolbox_decorator("retry")
def universal_api_retry(func):
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        retry=retry_if_exception_type(Exception),
        before_sleep=lambda state: log_retry_attempt(state)
    )
    def wrapped(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapped

def log_retry_attempt(state: RetryCallState):
    exc = state.outcome.exception()
    log(f"[RETRY] Attempt {state.attempt_number} failed with: {exc}")