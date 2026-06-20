import yaml as _yaml


def deserialize(text):
    return _yaml.safe_load(text) or {}
