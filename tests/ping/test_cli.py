import json

from ping import cli


def test_add_classifies_and_persists(tmp_path, monkeypatch):
    targets = tmp_path / "targets.json"
    monkeypatch.setattr(cli, "_TARGETS", targets)

    assert cli.main(["add", "mymod.myfunc"]) == 0
    assert cli.main(["add", "pkg/file.py"]) == 0
    data = json.loads(targets.read_text())
    assert "mymod.myfunc" in data["functions"]
    assert any(p.endswith("file.py") for p in data["files"])


def test_rm_and_off(tmp_path, monkeypatch):
    targets = tmp_path / "targets.json"
    monkeypatch.setattr(cli, "_TARGETS", targets)
    cli.main(["add", "a.b"])

    assert cli.main(["rm", "a.b"]) == 0
    assert json.loads(targets.read_text())["functions"] == []

    cli.main(["off"])
    assert json.loads(targets.read_text())["enabled"] is False
