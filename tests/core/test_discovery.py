import importlib
import os
import sys

from toolbox.discovery import (
    PREFIX,
    _auto_scan,
    _load_entry,
    _load_file,
    discover,
)


def test_load_file_executes_and_registers_module(tmp_path):
    p = tmp_path / "piece.py"
    p.write_text("LOADED = True\n")
    result = _load_file(str(p))
    assert result == [str(p)]
    mod_name = PREFIX + "file_piece"
    assert mod_name in sys.modules
    assert sys.modules[mod_name].LOADED is True


def test_load_entry_single_file(tmp_path):
    p = tmp_path / "single.py"
    p.write_text("OK = 1\n")
    assert _load_entry(str(p)) == [str(p)]


def test_load_entry_directory_loads_public_py_only(tmp_path):
    d = tmp_path / "pieces"
    d.mkdir()
    (d / "a.py").write_text("VAL = 'a'\n")
    (d / "b.py").write_text("VAL = 'b'\n")
    (d / "_private.py").write_text("raise RuntimeError('must not load')\n")
    (d / "notes.txt").write_text("ignore me\n")

    result = _load_entry(str(d) + os.sep)
    assert len(result) == 2
    assert all(r.endswith(".py") for r in result)


def test_load_entry_module_name(monkeypatch, tmp_path):
    (tmp_path / "named_mod.py").write_text("REGISTERED = True\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()

    result = _load_entry("named_mod")
    assert result == ["named_mod"]
    import named_mod

    assert named_mod.REGISTERED is True


def test_auto_scan_finds_prefixed_packages(monkeypatch, tmp_path):
    pkg = tmp_path / "toolbox_fake"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("SCANNED = True\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()

    loaded = _auto_scan()
    assert "toolbox_fake" in loaded
    import toolbox_fake

    assert toolbox_fake.SCANNED is True


def test_discover_no_features_no_auto_is_empty():
    assert discover(features=None, auto=False) == []


def test_discover_combines_features(tmp_path):
    f = tmp_path / "feat.py"
    f.write_text("Z = 1\n")
    loaded = discover(features=[str(f)], auto=False)
    assert loaded == [str(f)]
