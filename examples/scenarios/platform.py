"""Toolbox inheritance: one shared diagnostics base, two services derived from it.

`PlatformBase` carries the diagnostics every service wants (call counts, info, an
in-memory collector). `PaymentsService` and `LLMService` inherit it and add their
own pieces; each service's config section deep-merges over the base's through the
class hierarchy (exactly like the wrap pipeline's MRO resolution).

`PaymentsService` deliberately re-declares a base hook (`count_calls`) so its
section overlaps the base — at construction the duplicate is dropped and a yellow
warning is emitted. `LLMService` adds only fresh pieces, so it stays quiet.

The payment and LLM *processing* is reused from the standalone scenarios; only the
toolbox wiring changes, to show orchestration via inheritance.
"""

from toolbox import ToolBox

from examples.scenarios import llm_api, payments
from examples.toolbox_basic import catch

# Every service can see every section; MRO resolution picks the relevant ones.
BASE_DIAGNOSTICS = {
    "platform_base": {
        "hooks": {"always": ["track_info", "count_calls"]},
        "sinks": {"always": ["memory"]},
    }
}

PAYMENTS_SECTION = {
    "payments_svc": {
        # 'count_calls' overlaps the base -> deduped with a yellow warning
        "hooks": {"always": ["count_calls", "handle_problem"]},
        "sinks": {"always": ["json_lines"]},
    }
}

LLM_SECTION = {
    "llm_svc": {
        "hooks": {"always": ["capture_args"]},
        "wrappers": {"always": ["rate_limit", "retry", "validate"]},
        "sinks": {"always": ["json_lines"]},
    }
}


class PlatformBase(ToolBox):
    name = "platform_base"
    config_sources = [BASE_DIAGNOSTICS, PAYMENTS_SECTION, LLM_SECTION]
    features = ["examples.toolbox_basic"]


class PaymentsService(PlatformBase):
    name = "payments_svc"


class LLMService(PlatformBase):
    name = "llm_svc"
    variables = {"RATE_LIMIT": 100, "REQUIRED_KEYS": llm_api.REQUIRED_KEYS}


payments_svc = PaymentsService()
llm_svc = LLMService()


@payments_svc(
    on_error=catch(
        {
            payments.PaymentValidationError: lambda e: {"status": "rejected", "reason": str(e)},
            payments.PaymentDeclined: lambda e: {"status": "declined", "reason": str(e)},
            payments.PaymentNetworkError: lambda e: e,
            Exception: lambda e: payments.PaymentError(f"unexpected: {e}"),
        }
    )
)
def charge(amount, card):
    return payments._authorize(amount, card)


@llm_svc(on_error=lambda e: {"answer": None, "confidence": 0.0, "error": str(e)})
def ask(prompt):
    return llm_api._call_model(prompt)
