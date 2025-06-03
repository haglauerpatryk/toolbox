import time
from toolbox.logger import log

_feature_hook_registry = {}

def feature_hook(name, stage):
    def decorator(func):
        _feature_hook_registry.setdefault(name, []).append({
            "stage": stage,
            "func": func
        })
        return func
    return decorator


class HookMethods:
    @feature_hook(name="track_time", stage="before")
    def _start_timer(self, *args, context=None, **kwargs):
        context["start_time"] = time.perf_counter()

    @feature_hook(name="track_time", stage="after")
    def _stop_timer(self, result, context=None):
        elapsed = time.perf_counter() - context.get("start_time", 0)
        log(f"RUNTIME: {elapsed:.3f}s")

    @feature_hook(name="track_info", stage="before")
    def get_path(self, *args, context=None, **kwargs):
        context["path"] = "/fake/path/example.txt"
        log(f"[BEFORE] Path set to: {context['path']}")

    @feature_hook(name="track_info", stage="after")
    def print_summary(self, result, context=None):
        log(f"[AFTER] Result summary: {result}, path was: {context.get('path')}")

    @feature_hook(name="handle_problem", stage="on_error")
    def handle_exception(self, e, context=None):
        log(f"[ERROR] Caught: {e}")
