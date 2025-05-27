_hook_registry = {}

def hook(stage):
    def decorator(func):
        _hook_registry[func.__name__] = {
            "stage": stage,
            "func": func
        }
        return func
    return decorator


class HookMethods:
    @hook(stage="before")
    def get_path(self, *args, **kwargs):
        print("[BEFORE] Extracting path info...")

    @hook(stage="after")
    def print_summary(self, result):
        print(f"[AFTER] Result summary: {result}")

    @hook(stage="on_error")
    def handle_exception(self, e):
        print(f"[ERROR] Exception caught: {e}")