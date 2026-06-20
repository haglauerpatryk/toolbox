# A Python base config — the production source of truth that file/dir sources
# layer on top of. Pair it with the overlays/ directory to see ordered merging.
BASE = {
    "service": {
        "hooks": {"always": ["track_info"]},
        "sinks": {"always": ["memory"]},
    }
}
