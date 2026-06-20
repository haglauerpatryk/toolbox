import os
from copy import deepcopy

from toolbox.config.json import deserialize as _json_deserialize
from toolbox.config.yaml import deserialize as _yaml_deserialize

# Format dispatch lives here, not in the format modules: each deserializer just
# turns text into a dict, and this map decides which one a file extension gets.
# Adding a format = add a module + one entry. (Promote to a registry if formats
# ever need to be user-pluggable.)
DESERIALIZERS = {
    ".yaml": _yaml_deserialize,
    ".yml": _yaml_deserialize,
    ".json": _json_deserialize,
}

_cache = {}


def clear_cache():
    _cache.clear()


def load_config(path):
    if path not in _cache:
        with open(path, "r") as f:
            _cache[path] = _deserialize(path, f.read())
    return _cache[path]


def _deserialize(path, text):
    ext = os.path.splitext(path)[1].lower()
    deserializer = DESERIALIZERS.get(ext, _yaml_deserialize)
    return deserializer(text) or {}


def resolve_sources(sources):
    """Fold an ordered list of config sources into one dict.

    A source is a dict (used as-is, e.g. JSON handed in from an API), a file
    path (deserialized by extension), or a directory (all config files inside,
    sorted, merged). Later sources merge over earlier ones; order is the only
    precedence rule, so callers arrange it to encode their own authority.
    """
    merged = {}
    for source in sources:
        merged = deep_merge_dicts(merged, _load_source(source))
    return merged


def _load_source(source):
    if isinstance(source, dict):
        return source
    if os.path.isdir(source):
        return _load_directory(source)
    return load_config(source)


def _load_directory(path):
    merged = {}
    for name in sorted(os.listdir(path)):
        if name.startswith("_"):
            continue
        if os.path.splitext(name)[1].lower() in DESERIALIZERS:
            merged = deep_merge_dicts(merged, load_config(os.path.join(path, name)))
    return merged


def deep_merge_dicts(a, b):
    result = deepcopy(a)
    for k, v in b.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge_dicts(result[k], v)
        elif k in result and isinstance(result[k], list) and isinstance(v, list):
            result[k] = result[k] + deepcopy(v)
        else:
            result[k] = deepcopy(v)
    return result


def dedupe(names):
    """Drop repeats while preserving first-seen order; report what was removed."""
    seen = set()
    kept = []
    removed = []
    for name in names:
        if name in seen:
            removed.append(name)
        else:
            seen.add(name)
            kept.append(name)
    return kept, removed
