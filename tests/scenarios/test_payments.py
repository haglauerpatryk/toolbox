import json

import pytest

from examples.scenarios import payments as P
from examples.toolbox_basic import sinks

GOOD_CARD = "4242424242424242"
DECLINE_CARD = "4000000000000002"
NETWORK_CARD = "0000000000000000"


@pytest.fixture(autouse=True)
def redirect_audit(monkeypatch, tmp_path):
    monkeypatch.setattr(P.payments, "log_directory", str(tmp_path))
    return tmp_path


def audit_records(tmp_path):
    return [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]


def test_successful_charge_is_captured_and_audited(redirect_audit):
    out = P.charge(1000, GOOD_CARD)
    assert out == {"status": "captured", "amount": 1000, "card": "4242"}
    rec = audit_records(redirect_audit)[0]
    assert rec["ok"] is True and rec["func"] == "charge"


def test_validation_error_becomes_business_result():
    out = P.charge(-5, GOOD_CARD)
    assert out == {"status": "rejected", "reason": "amount must be positive"}
    # the swallowed cause is still recorded for audit
    rec = sinks.collected()[0]
    assert isinstance(rec["exception"], P.PaymentValidationError)


def test_decline_becomes_business_result():
    out = P.charge(1000, DECLINE_CARD)
    assert out == {"status": "declined", "reason": "insufficient funds"}


def test_network_error_is_reraised_for_caller_to_retry():
    with pytest.raises(P.PaymentNetworkError):
        P.charge(1000, NETWORK_CARD)


def test_unexpected_error_is_translated_and_chained(monkeypatch):
    def boom(amount, card):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(P, "_authorize", boom)
    with pytest.raises(P.PaymentError) as info:
        P.charge(1000, GOOD_CARD)
    assert isinstance(info.value.__cause__, RuntimeError)
    assert not isinstance(info.value, (P.PaymentDeclined, P.PaymentNetworkError))
