from tenacity import (
    RetryCallState,
    retry as _retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_fixed,
)

from toolbox import log, wrapper


@wrapper.register("retry")
def retry(func):
    @_retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        retry=retry_if_exception_type(Exception),
        before_sleep=_log_attempt,
    )
    def wrapped(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapped


def _log_attempt(state: RetryCallState):
    log(f"[RETRY] Attempt {state.attempt_number} failed with: {state.outcome.exception()}")
