import importlib
import importlib.util
import os
import pkgutil
import sys

PREFIX = "toolbox_"


def discover(features=None, auto=True):
    loaded = []
    if auto:
        loaded.extend(_auto_scan())
    for entry in (features or []):
        loaded.extend(_load_entry(entry))
    return loaded


def _auto_scan():
    found = []
    for module in pkgutil.iter_modules():
        if module.name.startswith(PREFIX):
            importlib.import_module(module.name)
            found.append(module.name)
    return found


def _load_entry(entry):
    is_path = os.sep in entry or entry.endswith(".py")
    if not is_path:
        importlib.import_module(entry)
        return [entry]
    if os.path.isdir(entry):
        loaded = []
        for name in sorted(os.listdir(entry)):
            if name.endswith(".py") and not name.startswith("_"):
                loaded.extend(_load_file(os.path.join(entry, name)))
        return loaded
    return _load_file(entry)


def _load_file(path):
    mod_name = PREFIX + "file_" + os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(mod_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return [path]
