import atexit
import queue
import sys
import threading
from functools import partial


class _Dispatcher:
    def __init__(self, maxsize=1000):
        self._queue = queue.Queue(maxsize=maxsize)
        self._thread = None
        self._lock = threading.Lock()
        self.dropped = 0

    def submit(self, job):
        self._ensure_worker()
        try:
            self._queue.put_nowait(job)
        except queue.Full:
            self.dropped += 1

    def _ensure_worker(self):
        if self._thread is not None:
            return
        with self._lock:
            if self._thread is not None:
                return
            thread = threading.Thread(
                target=self._run, name="toolbox-sink-dispatch", daemon=True
            )
            thread.start()
            self._thread = thread
            atexit.register(self._flush)

    def _run(self):
        while True:
            job = self._queue.get()
            try:
                job()
            except Exception as exc:
                print(f"[toolbox] background sink failed: {exc}", file=sys.stderr)
            finally:
                self._queue.task_done()

    def _flush(self):
        self._queue.join()


_dispatcher = _Dispatcher()


def submit(job):
    _dispatcher.submit(job)


def background(sink):
    def offpath_sink(ctx):
        submit(partial(sink, ctx))

    return offpath_sink
