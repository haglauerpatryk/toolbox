"""Hands-on ping demo:  python -m examples.ping_scenarios.demo

Targets are set programmatically here to keep the demo self-contained (normally
the `ping` CLI writes them). It shows ping observing only the targeted functions
and leaving results and exceptions untouched — timing on a slow call, a surfaced
error that still propagates, and a normal return.
"""

import json
import logging
import os
import tempfile
import time

from ping.core import Ping

logging.basicConfig(level=logging.INFO)


def slow_add(a, b):
    time.sleep(0.05)
    return a + b


def flaky(x):
    if x < 0:
        raise ValueError(f"negative: {x}")
    return x * 2


def main():
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as fh:
        json.dump({"functions": ["slow_add", "flaky"], "enabled": True}, fh)

    with Ping(targets_path=path):  # tracing on for this block only
        print("slow_add(2, 3) ->", slow_add(2, 3))
        try:
            flaky(-1)
        except ValueError as exc:
            print("flaky(-1) propagated ->", exc)
        print("flaky(4) ->", flaky(4))

    os.unlink(path)


if __name__ == "__main__":
    main()
