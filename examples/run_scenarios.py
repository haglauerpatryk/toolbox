"""Run each production scenario and print what its toolbox observed.

    python -m examples.run_scenarios   # from the repo root
"""

from examples.scenarios import diagnostics, dynamic, llm_api, payments, platform
from examples.toolbox_basic import metrics, sinks


def main():
    print("== diagnostics ==")
    print(diagnostics.transform("hello", upper=True))

    print("\n== payments ==")
    print("ok       ->", payments.charge(1000, "4242424242424242"))
    print("bad input->", payments.charge(-5, "4242424242424242"))
    print("declined ->", payments.charge(1000, "4000000000000002"))

    print("\n== llm (flaky, self-heals via retry+validate) ==")
    print(llm_api.ask("what is the answer?"))

    print("\n== platform (shared diagnostics base, inherited by two services) ==")
    print("payments_svc ->", platform.charge(2500, "4242424242424242"))
    print("llm_svc      ->", platform.ask("inherited diagnostics?"))

    print("\n== dynamic config (admin hot-swap, base logging always kept) ==")
    print("before push:", [f.__name__ for f in dynamic.app.hooks["before"]] or "(base only)")
    dynamic.apply_admin_config({"app": {"hooks": {"always": ["count_calls"]}}})
    print("after push :", [f.__name__ for f in dynamic.app.hooks["before"]])
    dynamic.apply_admin_config({})  # reset to base for a clean demo state

    print("\ncall counts:", metrics.counts())
    print("calls collected by the memory sink:", len(sinks.collected()))


if __name__ == "__main__":
    main()
