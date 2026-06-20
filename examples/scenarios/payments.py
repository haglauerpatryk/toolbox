"""Payment processing: an advanced decorator that turns exceptions into business
outcomes and audits every attempt.

Deliberately *no* retry — you do not blindly re-run a charge. Instead, `catch`
routes each failure by type: validation and declines become structured results
the caller can act on, while a network error is re-raised for an idempotent
caller/queue to retry. Every call is written to a JSONL audit stream, and the
on_error hook records the cause even when the error is swallowed into a result.
"""

from toolbox import ToolBox

from examples.toolbox_basic import catch


class PaymentError(Exception):
    pass


class PaymentValidationError(PaymentError):
    pass


class PaymentDeclined(PaymentError):
    pass


class PaymentNetworkError(PaymentError):
    pass


PAYMENTS = {
    "payments": {
        "hooks": {"always": ["track_info", "capture_args", "handle_problem"]},
        "sinks": {"always": ["json_lines", "memory"]},
    }
}


class Payments(ToolBox):
    name = "payments"
    config_sources = [PAYMENTS]
    features = ["examples.toolbox_basic"]


payments = Payments()


def _authorize(amount, card):
    if amount <= 0:
        raise PaymentValidationError("amount must be positive")
    if card == "4000000000000002":
        raise PaymentDeclined("insufficient funds")
    if card == "0000000000000000":
        raise PaymentNetworkError("gateway timeout")
    return {"status": "captured", "amount": amount, "card": card[-4:]}


@payments(
    on_error=catch(
        {
            PaymentValidationError: lambda e: {"status": "rejected", "reason": str(e)},
            PaymentDeclined: lambda e: {"status": "declined", "reason": str(e)},
            PaymentNetworkError: lambda e: e,  # re-raise: an idempotent caller retries
            Exception: lambda e: PaymentError(f"unexpected: {e}"),
        }
    )
)
def charge(amount, card):
    return _authorize(amount, card)
