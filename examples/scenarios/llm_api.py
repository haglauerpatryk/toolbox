"""Flaky LLM API: retry transient failures, validate the response shape, and fall
back to a safe default when the model keeps misbehaving.

The wrapper stack (config order `[rate_limit, retry, validate]`) nests so that
`retry` re-runs `validate` + the call: a malformed response raises `FormatError`
inside `validate`, `retry` tries again, and `rate_limit` still counts the request
once. If the model never returns a well-formed payload, `retry` exhausts and the
on_error lambda yields a safe fallback instead of crashing the request path.
"""

from toolbox import ToolBox

REQUIRED_KEYS = ["answer", "confidence"]

LLM_CONFIG = {
    "llm": {
        "hooks": {"always": ["track_info", "count_calls"]},
        "wrappers": {"always": ["rate_limit", "retry", "validate"]},
        "sinks": {"always": ["json_lines", "memory"]},
    }
}


class LLM(ToolBox):
    name = "llm"
    config_sources = [LLM_CONFIG]
    features = ["examples.toolbox_basic"]
    variables = {"RATE_LIMIT": 100, "REQUIRED_KEYS": REQUIRED_KEYS}


llm = LLM()

# Deterministic stand-in for a flaky endpoint: the first call for a prompt returns
# a malformed payload (missing 'confidence'); the retry returns valid JSON.
_attempts = {}


def reset():
    _attempts.clear()


def _call_model(prompt):
    n = _attempts.get(prompt, 0) + 1
    _attempts[prompt] = n
    if n < 2:
        return {"answer": "tentative"}  # missing required key -> FormatError
    return {"answer": f"answer to {prompt!r}", "confidence": 0.92}


_FALLBACK = lambda e: {"answer": None, "confidence": 0.0, "error": str(e)}  # noqa: E731


@llm(on_error=_FALLBACK)
def ask(prompt):
    return _call_model(prompt)


@llm(on_error=_FALLBACK)
def ask_unfixable(prompt):
    return {"answer": "no confidence here"}  # never well-formed -> exhausts retry
