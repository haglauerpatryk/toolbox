"""Showcase: user-defined error-handling *policies* on top of the `on_error` contract.

Nothing here touches the core. It demonstrates that because `on_error` accepts any
callable obeying one rule — **return an exception instance -> it is raised; return
anything else -> that becomes the call's result** — a user can express error policy
however they like: a factory function, a stateful class, a class hierarchy, `catch`
wrapped in richer logic, predicates beyond exception type, or a policy that adapts to a
live flag. The framework's responsibility ends at "on_error is a callable".

The recurring theme of the last few: the policy *decides* the outcome, while the
configured `on_error` hooks and sinks *observe* every failure regardless of that
decision (see `test_observation_fires_regardless_of_policy_decision`).
"""

import pytest

from toolbox import current_context
from toolbox.registries import hook, sink
from examples.toolbox_basic import catch


# --- exceptions a "user app" might define -----------------------------------


class DownstreamError(Exception):
    pass


class ValidationError(Exception):
    pass


class TransientError(Exception):
    pass


class HttpError(Exception):
    def __init__(self, status, msg=""):
        super().__init__(msg)
        self.status = status


# --- 1. a factory function that reaches the original call arguments ----------


def failover(backup):
    """Policy factory: on failure, re-run a backup with the *same* arguments.

    The original args/kwargs are read from the call's context, so the policy needs
    no knowledge of the function's signature.
    """

    def policy(e):
        ctx = current_context()
        return backup(*ctx.args, **ctx.kwargs)

    return policy


def test_factory_failover_retries_with_backup(toolbox_factory):
    tb = toolbox_factory()

    def backup(job):
        return f"backup:{job}"

    @tb(on_error=failover(backup))
    def primary(job):
        raise DownstreamError("primary down")

    assert primary("nightly") == "backup:nightly"


# --- 2. a stateful policy: a tiny circuit breaker ---------------------------


class CircuitBreaker:
    """Re-raises while under threshold, then 'opens' and sheds load with a sentinel.

    State (the failure count) lives on the instance — something a static map can't do.
    """

    def __init__(self, threshold):
        self.threshold = threshold
        self.failures = 0

    def __call__(self, e):
        self.failures += 1
        if self.failures >= self.threshold:
            return {"circuit": "open"}
        return e  # re-raise


def test_stateful_circuit_breaker_opens_after_threshold(toolbox_factory):
    tb = toolbox_factory()
    breaker = CircuitBreaker(threshold=3)

    @tb(on_error=breaker)
    def flaky():
        raise TransientError("blip")

    with pytest.raises(TransientError):
        flaky()
    with pytest.raises(TransientError):
        flaky()
    assert flaky() == {"circuit": "open"}  # threshold reached -> circuit opens
    assert breaker.failures == 3


# --- 3. a policy hierarchy via plain Python inheritance ----------------------


class BasePolicy:
    def __call__(self, e):
        return self.handle(e)

    def handle(self, e):
        return e  # default: re-raise


class PaymentsPolicy(BasePolicy):
    def handle(self, e):
        if isinstance(e, ValidationError):
            return {"status": "rejected", "reason": str(e)}
        return super().handle(e)  # everything else falls back to the base


def test_policy_inheritance_overrides_then_falls_back(toolbox_factory):
    tb = toolbox_factory()

    @tb(on_error=PaymentsPolicy())
    def charge(kind):
        raise ValidationError("bad card") if kind == "bad" else DownstreamError("net")

    assert charge("bad") == {"status": "rejected", "reason": "bad card"}
    with pytest.raises(DownstreamError):  # not handled here -> base re-raises
        charge("net")


# --- 4. catch as the dispatch primitive *inside* a richer class --------------


class RoutingWithCount:
    """Lets `catch` own the (subtle) type dispatch; the class only adds state."""

    def __init__(self):
        self.handled = 0
        self._route = catch(
            {
                ValidationError: lambda e: {"status": "rejected"},
                Exception: lambda e: e,
            }
        )

    def __call__(self, e):
        self.handled += 1
        return self._route(e)


def test_catch_inside_class_keeps_dispatch_and_adds_state(toolbox_factory):
    tb = toolbox_factory()
    policy = RoutingWithCount()

    @tb(on_error=policy)
    def f(kind):
        raise ValidationError("v") if kind == "v" else DownstreamError("d")

    assert f("v") == {"status": "rejected"}
    with pytest.raises(DownstreamError):
        f("d")
    assert policy.handled == 2  # both failures routed through the same policy


# --- 5. routing by a predicate beyond exception type ------------------------


def http_policy(e):
    # Route by an attribute, not by type — exactly what `catch` cannot express.
    if isinstance(e, HttpError) and 400 <= e.status < 500:
        return {"error": "client", "status": e.status}  # swallow 4xx
    return e  # re-raise 5xx (and anything else)


def test_predicate_policy_routes_on_attribute(toolbox_factory):
    tb = toolbox_factory()

    @tb(on_error=http_policy)
    def call(status):
        raise HttpError(status, "boom")

    assert call(404) == {"error": "client", "status": 404}
    with pytest.raises(HttpError):
        call(503)


# --- 6. runtime adaptivity via a live flag (no hot-swap needed) --------------


def test_policy_adapts_to_live_flag_without_reconfigure(toolbox_factory):
    tb = toolbox_factory()
    flags = {"maintenance": False}

    def policy(e):
        return {"status": "maintenance"} if flags["maintenance"] else {"status": "error"}

    @tb(on_error=policy)
    def f():
        raise DownstreamError("x")

    assert f() == {"status": "error"}
    flags["maintenance"] = True  # flip live state, not the policy object
    assert f() == {"status": "maintenance"}  # same function, new behavior


# --- 7. the policy decides; configured hooks/sinks still observe -------------


def test_observation_fires_regardless_of_policy_decision(toolbox_factory):
    seen = {}
    hook.register("oe_observer", stages=("on_error",))(
        lambda ctx: seen.__setitem__("hook_exc", ctx.exception)
    )
    sink.register("exc_recorder")(
        lambda ctx: seen.__setitem__("sink_exc", ctx.exception)
    )
    tb = toolbox_factory(hooks=["oe_observer"], sinks=["exc_recorder"])

    @tb(on_error=lambda e: {"ok": False})  # policy swallows to a fallback
    def f():
        raise ValidationError("bad")

    assert f() == {"ok": False}  # policy decided the outcome
    assert isinstance(seen["hook_exc"], ValidationError)  # on_error hook still fired
    assert isinstance(seen["sink_exc"], ValidationError)  # sink still observed it


# --- 8. a class that translates obeys the raise-vs-return contract -----------


class Translator:
    def __call__(self, e):
        return DownstreamError(f"wrapped: {e}")  # return an exception -> it is raised


def test_policy_class_translating_chains_the_original(toolbox_factory):
    tb = toolbox_factory()

    @tb(on_error=Translator())
    def f():
        raise ValueError("orig")

    with pytest.raises(DownstreamError, match="wrapped: orig") as info:
        f()
    assert isinstance(info.value.__cause__, ValueError)  # chained from the original
