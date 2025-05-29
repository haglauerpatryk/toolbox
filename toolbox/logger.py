import threading
import inspect
import os

_log_state = threading.local()

def init_log_buffer():
    _log_state.buffer = []

def log(msg):
    if not hasattr(_log_state, "buffer"):
        init_log_buffer()
    _log_state.buffer.append(str(msg))


def _unwrap_function(func):
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__
    return func

def _format_block_header(func, root_dir=None):
    original_func = _unwrap_function(func)

    func_name = original_func.__name__

    try:
        file_path = inspect.getfile(original_func)
        line = inspect.getsourcelines(original_func)[1]

        if root_dir and file_path.startswith(str(root_dir)):
            from pathlib import Path
            file_path = Path(file_path).relative_to(root_dir)
    except Exception:
        file_path = "unknown"
        line = "?"

    header_lines = [
        "=" * 80,
        f"FUNC:    {func_name}",
        f"PATH:    {file_path}:{line}",
    ]
    return "\n".join(header_lines)



def flush_logs_block(func, to_terminal=True, to_file=False, file_path="logs.txt", root_dir=None):
    logs = getattr(_log_state, "buffer", [])
    if not logs:
        return

    block = []
    block.append(_format_block_header(func, root_dir=root_dir))
    block.extend(logs)
    block.append("=" * 80)
    block.append("")  # blank line between blocks

    final_output = "\n".join(block)

    if to_terminal:
        print(final_output)

    if to_file:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "a") as f:
            f.write(final_output + "\n")

    _log_state.buffer = []