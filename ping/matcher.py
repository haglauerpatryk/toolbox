"""Decide whether a running frame is one ping should observe.

Targets live in a JSON file the `ping` CLI generates — `functions` (by full
`module.qualname`, or a bare name) and `files` (whole-file watch by source
path), plus an `enabled` flag. The file is re-read at most once per `ttl`
seconds (mtime-checked), so CLI edits take effect on the next call without
restarting the app, while the per-call cost stays a cheap membership test.
"""

import json
import os
import time


class TargetMatcher:
    def __init__(self, path, ttl=1.0):
        self._path = path
        self._ttl = ttl
        self._enabled = True
        self._functions = set()
        self._files = set()
        self._mtime = None
        self._last_check = 0.0
        self._reload()

    def _reload(self):
        try:
            mtime = os.path.getmtime(self._path)
        except OSError:
            self._enabled, self._functions, self._files, self._mtime = True, set(), set(), None
            return
        if mtime == self._mtime:
            return
        try:
            with open(self._path) as fh:
                data = json.load(fh) or {}
        except (OSError, ValueError):
            return
        self._enabled = bool(data.get("enabled", True))
        self._functions = set(data.get("functions", []))
        self._files = {os.path.abspath(p) for p in data.get("files", [])}
        self._mtime = mtime

    def _maybe_reload(self):
        now = time.monotonic()
        if now - self._last_check >= self._ttl:
            self._last_check = now
            self._reload()

    def matches(self, frame):
        self._maybe_reload()
        if not self._enabled or (not self._functions and not self._files):
            return False
        code = frame.f_code
        if self._files and os.path.abspath(code.co_filename) in self._files:
            return True
        if self._functions:
            qual = getattr(code, "co_qualname", code.co_name)
            module = frame.f_globals.get("__name__", "")
            if (
                f"{module}.{qual}" in self._functions
                or qual in self._functions
                or code.co_name in self._functions
            ):
                return True
        return False
