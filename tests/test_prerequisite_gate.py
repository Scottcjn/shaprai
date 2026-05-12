"""Unit tests for prerequisite gate orchestration."""

import pytest

from shaprai import prerequisites
from shaprai.prerequisites import PrerequisiteStatus, SystemCheck


def _status(name, ok=True):
    return PrerequisiteStatus(
        name=name,
        installed=ok,
        reachable=ok,
        version="ok" if ok else None,
        error=None if ok else "missing",
    )


def _check(all_ok=True):
    return SystemCheck(
        beacon=_status("beacon-skill", all_ok),
        grazer=_status("grazer-skill", all_ok),
        atlas=_status("atlas", all_ok),
        rustchain=_status("rustchain", all_ok),
    )


def test_check_prerequisites_returns_system_check_when_not_strict(monkeypatch):
    monkeypatch.setattr(prerequisites, "_check_beacon", lambda: _status("beacon-skill"))
    monkeypatch.setattr(prerequisites, "_check_grazer", lambda: _status("grazer-skill"))
    monkeypatch.setattr(prerequisites, "_check_atlas", lambda: _status("atlas"))
    monkeypatch.setattr(prerequisites, "_check_rustchain", lambda: _status("rustchain"))

    result = prerequisites.check_prerequisites(strict=False)

    assert result.all_ok is True
    assert result.beacon.name == "beacon-skill"
    assert result.rustchain.name == "rustchain"


def test_check_prerequisites_strict_raises_on_failure(monkeypatch, capsys):
    monkeypatch.setattr(prerequisites, "_check_beacon", lambda: _status("beacon-skill"))
    monkeypatch.setattr(prerequisites, "_check_grazer", lambda: _status("grazer-skill", ok=False))
    monkeypatch.setattr(prerequisites, "_check_atlas", lambda: _status("atlas"))
    monkeypatch.setattr(prerequisites, "_check_rustchain", lambda: _status("rustchain"))

    with pytest.raises(SystemExit) as exc:
        prerequisites.check_prerequisites(strict=True)

    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "BLOCKED: Missing prerequisites: grazer-skill" in captured.err


def test_require_elyan_ecosystem_returns_check_when_all_ok(monkeypatch, capsys):
    monkeypatch.setattr(prerequisites, "check_prerequisites", lambda strict=False: _check(True))

    result = prerequisites.require_elyan_ecosystem()

    assert result.all_ok is True
    captured = capsys.readouterr()
    assert "All prerequisites satisfied" in captured.out


def test_require_elyan_ecosystem_exits_when_any_check_fails(monkeypatch, capsys):
    monkeypatch.setattr(prerequisites, "check_prerequisites", lambda strict=False: _check(False))

    with pytest.raises(SystemExit) as exc:
        prerequisites.require_elyan_ecosystem()

    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "ShaprAI requires beacon-skill" in captured.err
    assert "BLOCKED: Missing prerequisites" in captured.out
