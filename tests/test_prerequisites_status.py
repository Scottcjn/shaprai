import pytest

import shaprai.prerequisites as prerequisites
from shaprai.prerequisites import PrerequisiteStatus, SystemCheck


def _status(name, *, installed=True, reachable=True, version="ok", error=None):
    return PrerequisiteStatus(
        name=name,
        installed=installed,
        reachable=reachable,
        version=version,
        error=error,
    )


def _system_check(*, beacon=None, grazer=None, atlas=None, rustchain=None):
    return SystemCheck(
        beacon=beacon or _status("beacon-skill"),
        grazer=grazer or _status("grazer-skill"),
        atlas=atlas or _status("atlas"),
        rustchain=rustchain or _status("rustchain"),
    )


def test_prerequisite_status_ok_requires_installed_and_reachable():
    assert _status("ready").ok is True
    assert _status("missing", installed=False).ok is False
    assert _status("offline", reachable=False).ok is False
    assert _status("absent-offline", installed=False, reachable=False).ok is False


def test_system_check_summary_reports_all_clear_when_everything_is_ready():
    check = _system_check()

    assert check.all_ok is True
    assert "ShaprAI Prerequisites Check" in check.summary
    assert "[PASS] beacon-skill: ok" in check.summary
    assert "All prerequisites satisfied. ShaprAI ready." in check.summary


def test_system_check_summary_lists_failed_prerequisites_and_guidance():
    check = _system_check(
        beacon=_status("beacon-skill", installed=False, version=None, error="not installed"),
        rustchain=_status("rustchain", reachable=False, version=None, error="node down"),
    )

    summary = check.summary

    assert check.all_ok is False
    assert "[FAIL] beacon-skill: not installed" in summary
    assert "[FAIL] rustchain: node down" in summary
    assert "BLOCKED: Missing prerequisites: beacon-skill, rustchain" in summary
    assert "pip install beacon-skill" in summary
    assert "RustChain node must be running" in summary


def test_check_prerequisites_returns_result_when_non_strict(monkeypatch):
    failing_check = _system_check(
        grazer=_status("grazer-skill", installed=False, error="not installed")
    )

    monkeypatch.setattr(prerequisites, "_check_beacon", lambda: failing_check.beacon)
    monkeypatch.setattr(prerequisites, "_check_grazer", lambda: failing_check.grazer)
    monkeypatch.setattr(prerequisites, "_check_atlas", lambda: failing_check.atlas)
    monkeypatch.setattr(prerequisites, "_check_rustchain", lambda: failing_check.rustchain)

    result = prerequisites.check_prerequisites(strict=False)

    assert result is not failing_check
    assert result.grazer.error == "not installed"
    assert result.all_ok is False


def test_check_prerequisites_exits_when_strict_and_missing_dependency(monkeypatch, capsys):
    failing_check = _system_check(
        atlas=_status("atlas", reachable=False, error="atlas offline")
    )

    monkeypatch.setattr(prerequisites, "_check_beacon", lambda: failing_check.beacon)
    monkeypatch.setattr(prerequisites, "_check_grazer", lambda: failing_check.grazer)
    monkeypatch.setattr(prerequisites, "_check_atlas", lambda: failing_check.atlas)
    monkeypatch.setattr(prerequisites, "_check_rustchain", lambda: failing_check.rustchain)

    with pytest.raises(SystemExit) as exc:
        prerequisites.check_prerequisites(strict=True)

    assert exc.value.code == 1
    assert "BLOCKED: Missing prerequisites: atlas" in capsys.readouterr().err


def test_check_rustchain_uses_health_payload_version(monkeypatch):
    class Response:
        status_code = 200

        def json(self):
            return {"ok": True, "version": "2.2.1-test"}

    monkeypatch.setattr(
        prerequisites.requests,
        "get",
        lambda url, timeout, verify: Response(),
    )

    status = prerequisites._check_rustchain()

    assert status.name == "rustchain"
    assert status.installed is True
    assert status.reachable is True
    assert status.version == "2.2.1-test"
    assert status.error is None


def test_check_rustchain_reports_unreachable_on_request_error(monkeypatch):
    def raise_request_error(*args, **kwargs):
        raise prerequisites.requests.RequestException("offline")

    monkeypatch.setattr(prerequisites.requests, "get", raise_request_error)

    status = prerequisites._check_rustchain()

    assert status.name == "rustchain"
    assert status.installed is True
    assert status.reachable is False
    assert status.version is None
    assert "RustChain node not reachable" in status.error
