"""Concurrency safety of the stateful reference pieces.

These pieces keep aggregate state in their own modules; under a threaded host
(e.g. a WSGI worker pool) the read-modify-write on that state races without a
lock. With the locks in place the tallies are *exact*, so equality assertions
are deterministic — the test confirms correctness, it doesn't rely on tripping a
race. A barrier releases all threads together to maximise contention.
"""

import threading

from examples.toolbox_basic import metrics, sinks, wrappers

_THREADS = 8
_PER_THREAD = 500
_TOTAL = _THREADS * _PER_THREAD


def _hammer(call):
    barrier = threading.Barrier(_THREADS)

    def worker():
        barrier.wait()
        for _ in range(_PER_THREAD):
            call()

    threads = [threading.Thread(target=worker) for _ in range(_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def test_count_calls_and_counter_are_exact_under_threads(toolbox_factory):
    tb = toolbox_factory(hooks=["count_calls"], sinks=["counter"])

    @tb
    def work():
        return 1

    _hammer(work)
    assert metrics.counts()["work"] == _TOTAL   # before-hook RMW
    assert sinks.emit_count() == _TOTAL          # sink RMW


def test_rate_limit_counts_exactly_under_threads(toolbox_factory):
    # Limit == total, so the count climbs to exactly _TOTAL and never exceeds it
    # (no RateLimitExceeded) — but only if the increment is race-free.
    tb = toolbox_factory(wrappers=["rate_limit"], variables={"RATE_LIMIT": _TOTAL})

    @tb
    def work():
        return 1

    _hammer(work)
    assert wrappers._rate["work"] == _TOTAL


def test_memoize_is_consistent_under_threads(toolbox_factory):
    computed = []
    comp_lock = threading.Lock()

    tb = toolbox_factory(wrappers=["memoize"])

    @tb
    def square(n):
        with comp_lock:
            computed.append(n)
        return n * n

    results = []
    res_lock = threading.Lock()

    def worker():
        r = square(7)
        with res_lock:
            results.append(r)

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results == [49] * 16          # every caller gets the right value
    assert len(computed) <= 16           # benign double-compute, never corruption
    assert wrappers._memo[("square", (7,), ())] == 49
