import json
import sys

from ping.matcher import TargetMatcher


def _targets(path, **data):
    data.setdefault("enabled", True)
    path.write_text(json.dumps(data))


def test_matches_by_bare_name(tmp_path):
    p = tmp_path / "t.json"
    _targets(p, functions=["test_matches_by_bare_name"])
    assert TargetMatcher(str(p)).matches(sys._getframe()) is True


def test_matches_by_full_name(tmp_path):
    p = tmp_path / "t.json"
    frame = sys._getframe()
    full = f"{frame.f_globals['__name__']}.{frame.f_code.co_qualname}"
    _targets(p, functions=[full])
    assert TargetMatcher(str(p)).matches(frame) is True


def test_matches_by_file(tmp_path):
    p = tmp_path / "t.json"
    _targets(p, files=[__file__])
    assert TargetMatcher(str(p)).matches(sys._getframe()) is True


def test_no_targets_is_false(tmp_path):
    p = tmp_path / "t.json"
    _targets(p)
    assert TargetMatcher(str(p)).matches(sys._getframe()) is False


def test_disabled_is_false(tmp_path):
    p = tmp_path / "t.json"
    _targets(p, functions=["test_disabled_is_false"], enabled=False)
    assert TargetMatcher(str(p)).matches(sys._getframe()) is False


def test_missing_file_is_false(tmp_path):
    assert TargetMatcher(str(tmp_path / "nope.json")).matches(sys._getframe()) is False
