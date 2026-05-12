"""Unit tests for prerequisite status aggregation and summaries."""

from shaprai.prerequisites import PrerequisiteStatus, SystemCheck


def _status(name, installed=True, reachable=True, version="1.0.0", error=None):
    return PrerequisiteStatus(
        name=name,
        installed=installed,
        reachable=reachable,
        version=version,
        error=error,
    )


class TestPrerequisiteStatus:
    def test_ok_requires_installed_and_reachable(self):
        assert _status("beacon").ok is True
        assert _status("beacon", installed=False, reachable=True).ok is False
        assert _status("beacon", installed=True, reachable=False).ok is False
        assert _status("beacon", installed=False, reachable=False).ok is False

    def test_error_detail_can_explain_failed_status(self):
        status = _status(
            "grazer",
            installed=False,
            reachable=False,
            version=None,
            error="Not installed",
        )

        assert status.ok is False
        assert status.error == "Not installed"


class TestSystemCheck:
    def test_all_ok_true_when_every_prerequisite_is_ok(self):
        check = SystemCheck(
            beacon=_status("beacon-skill"),
            grazer=_status("grazer-skill"),
            atlas=_status("atlas", version="beacon-component"),
            rustchain=_status("rustchain", version="2.2.1"),
        )

        assert check.all_ok is True
        assert "All prerequisites satisfied" in check.summary

    def test_all_ok_false_when_any_prerequisite_fails(self):
        check = SystemCheck(
            beacon=_status("beacon-skill"),
            grazer=_status("grazer-skill", installed=False, error="missing"),
            atlas=_status("atlas", version="beacon-component"),
            rustchain=_status("rustchain", version="2.2.1"),
        )

        assert check.all_ok is False
        assert "BLOCKED: Missing prerequisites: grazer-skill" in check.summary

    def test_summary_lists_install_guidance_for_each_failed_component(self):
        check = SystemCheck(
            beacon=_status("beacon-skill", installed=False, error="missing"),
            grazer=_status("grazer-skill", installed=False, error="missing"),
            atlas=_status("atlas", reachable=False, version="beacon-component"),
            rustchain=_status("rustchain", reachable=False, version=None, error="down"),
        )

        summary = check.summary

        assert "[FAIL] beacon-skill" in summary
        assert "[FAIL] grazer-skill" in summary
        assert "[FAIL] atlas" in summary
        assert "[FAIL] rustchain" in summary
        assert "pip install beacon-skill" in summary
        assert "pip install grazer-skill" in summary
        assert "Atlas is part of beacon-skill" in summary
        assert "RustChain node must be running" in summary

    def test_summary_prefers_version_over_error_for_display_detail(self):
        check = SystemCheck(
            beacon=_status("beacon-skill", version="installed", error="ignored"),
            grazer=_status(
                "grazer-skill",
                installed=False,
                reachable=False,
                version=None,
                error="missing",
            ),
            atlas=_status("atlas", version="beacon-component"),
            rustchain=_status("rustchain", version="2.2.1"),
        )

        summary = check.summary

        assert "[PASS] beacon-skill: installed" in summary
        assert "[FAIL] grazer-skill: missing" in summary
