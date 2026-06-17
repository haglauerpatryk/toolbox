from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Entry:
    name: str
    func: Callable
    meta: dict = field(default_factory=dict)


class Registry:
    def __init__(self, kind):
        self.kind = kind
        self._entries = {}

    def register(self, name, **meta):
        def decorator(func):
            if name in self._entries:
                raise ValueError(f"duplicate {self.kind} '{name}' already registered")
            self._entries[name] = Entry(name=name, func=func, meta=meta)
            return func
        return decorator

    def get(self, name):
        if name not in self._entries:
            raise KeyError(f"unknown {self.kind} '{name}'")
        return self._entries[name]

    def names(self):
        return list(self._entries)

    def __contains__(self, name):
        return name in self._entries
