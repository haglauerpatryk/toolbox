from toolbox.logger import flush_logs_block
from pathlib import Path

_log_output_registry = {}

def log_output(name):
    def decorator(func):
        _log_output_registry[name] = func
        return func
    return decorator


class LogDispatcher:
    def __init__(self, enabled_outputs, file_path, root_dir):
        self.enabled_outputs = enabled_outputs
        self.file_path = file_path
        self.root_dir = Path(root_dir)

    def dispatch(self, func):
        for name in self.enabled_outputs:
            method = _log_output_registry.get(name)
            if method:
                method(self, func)

    @log_output("terminal")
    def log_to_terminal(self, func):
        flush_logs_block(func, to_terminal=True, to_file=False)

    @log_output("file")
    def log_to_file(self, func):
        flush_logs_block(func, to_terminal=False, to_file=True, file_path=self.file_path, root_dir=self.root_dir)