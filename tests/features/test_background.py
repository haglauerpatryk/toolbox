import importlib
import threading
from functools import partial

import pytest

# The package re-exports a `background` *function*, which shadows the submodule
# of the same name on attribute access; fetch the module explicitly.
bg = importlib.import_module("examples.toolbox_basic.background")
from examples.toolbox_basic.background import _Dispatcher, background


# --- background(sink) wrapper (deterministic, no real thread) ---------------


def test_background_enqueues_partial_of_sink(monkeypatch):
    captured = []
    monkeypatch.setattr(bg, "submit", lambda job: captured.append(job))

    sink_calls = []

    def my_sink(ctx):
        sink_calls.append(ctx)

    offpath = background(my_sink)
    ctx = object()
    assert offpath(ctx) is None  # returns immediately, no result

    assert len(captured) == 1
    job = captured[0]
    assert isinstance(job, partial)
    assert job.func is my_sink
    assert job.args == (ctx,)

    job()  # the worker would run exactly this
    assert sink_calls == [ctx]


# --- _Dispatcher (real worker thread) ---------------------------------------


def test_dispatcher_runs_job_then_flush_returns():
    disp = _Dispatcher()
    results = []
    disp.submit(lambda: results.append("done"))
    disp._flush()
    assert results == ["done"]


def test_dispatcher_runs_jobs_in_order():
    disp = _Dispatcher()
    results = []
    for i in range(5):
        disp.submit(partial(results.append, i))
    disp._flush()
    assert results == [0, 1, 2, 3, 4]


def test_dispatcher_swallows_job_failure_to_stderr(capsys):
    disp = _Dispatcher()

    def boom():
        raise RuntimeError("kaboom")

    disp.submit(boom)
    disp._flush()
    err = capsys.readouterr().err
    assert "background sink failed" in err
    assert "kaboom" in err


def test_dispatcher_failure_does_not_stop_worker(capsys):
    disp = _Dispatcher()
    ran = []
    disp.submit(lambda: (_ for _ in ()).throw(RuntimeError("x")))
    disp.submit(lambda: ran.append("survived"))
    disp._flush()
    assert ran == ["survived"]


def test_dispatcher_bounded_queue_drops_when_full():
    disp = _Dispatcher(maxsize=1)
    started = threading.Event()
    release = threading.Event()

    def blocker():
        started.set()
        release.wait(timeout=5)

    disp.submit(blocker)
    assert started.wait(timeout=5)  # worker has dequeued and is now busy

    ran = []
    disp.submit(lambda: ran.append(1))  # fills the single slot
    disp.submit(lambda: ran.append(2))  # queue full -> dropped
    disp.submit(lambda: ran.append(3))  # queue full -> dropped
    assert disp.dropped == 2

    release.set()
    disp._flush()
    assert ran == [1]


def test_dispatcher_worker_is_daemon_and_single():
    disp = _Dispatcher()
    disp.submit(lambda: None)
    assert disp._thread is not None
    assert disp._thread.daemon is True
    first = disp._thread
    disp.submit(lambda: None)  # must not spawn a second worker
    assert disp._thread is first
    disp._flush()


def test_ensure_worker_double_checked_lock_does_not_double_spawn():
    # Model the race the inner lock guards: a second caller enters _ensure_worker
    # while the worker is being set up, and must bail out without spawning again.
    disp = _Dispatcher()
    disp._lock.acquire()  # hold the lock so the racing caller blocks inside

    racer = threading.Thread(target=disp._ensure_worker)
    racer.start()
    # racer passed the outer guard (_thread is None) and is now blocked on the lock.
    sentinel = threading.current_thread()
    disp._thread = sentinel  # simulate "another thread already started the worker"
    disp._lock.release()

    racer.join(timeout=5)
    assert not racer.is_alive()
    assert disp._thread is sentinel  # inner guard hit: racer did NOT overwrite it


# --- off-path semantics: the contract a background sink must respect ---------


def test_contextvar_does_not_cross_the_worker_thread():
    # A background sink runs on the worker thread, where current_context() is None.
    # Only the explicitly-passed ctx crosses; the contextvar does not.
    from toolbox.context import CallContext, _current, current_context

    disp = _Dispatcher()
    ctx = CallContext(func=lambda: None)
    seen = {}

    def my_sink(c):
        seen["arg"] = c
        seen["current"] = current_context()

    token = _current.set(ctx)  # active on THIS thread only
    try:
        disp.submit(partial(my_sink, ctx))
        disp._flush()
    finally:
        _current.reset(token)

    assert seen["arg"] is ctx  # the explicit argument crosses
    assert seen["current"] is None  # the contextvar does not


def test_worker_sees_live_ctx_not_a_snapshot():
    # background(sink) hands the *live* CallContext to the worker. The caller
    # thread keeps mutating it (wrap()'s `finally` runs sinks while the request
    # thread continues), so an off-path sink reading ctx races that mutation.
    # This pins the shared-object reality so a regression to "snapshot" is caught.
    from toolbox.context import CallContext

    disp = _Dispatcher()
    ctx = CallContext(func=lambda: None)
    gate = threading.Event()
    seen = {}

    def my_sink(c):
        gate.wait(timeout=5)  # worker reads only after the caller mutates
        seen["buffer"] = list(c.buffer)

    disp.submit(partial(my_sink, ctx))
    ctx.buffer.append("late")  # caller mutates the same object post-enqueue
    gate.set()
    disp._flush()

    assert seen["buffer"] == ["late"]  # worker observed the live mutation


def test_module_level_submit_uses_global_dispatcher():
    results = []
    event = threading.Event()
    bg.submit(lambda: (results.append("ran"), event.set()))
    assert event.wait(timeout=5)
    assert results == ["ran"]
