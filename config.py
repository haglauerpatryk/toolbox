# Base configuration, authored in Python. Treat this as the production source
# of truth; file, directory, and dict sources layer on top of it, and the order
# they appear in `config_sources` is the only thing that decides precedence.
BASE = {
    "my_toolbox": {
        "hooks": {"always": ["track_info"]},
        "sinks": {"always": ["logging"]},
    },
    "error_toolbox": {
        "hooks": {"always": ["handle_problem"]},
    },
}
