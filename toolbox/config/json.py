import json as _json


def deserialize(text):
    text = text.strip()
    return _json.loads(text) if text else {}
