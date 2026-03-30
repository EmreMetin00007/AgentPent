"""CLI behavior tests."""

from __future__ import annotations

from typer.testing import CliRunner

from cli import main as cli_main
from core.mission import AttackPhase, Finding, Mission, MissionStatus, Severity


runner = CliRunner()


class _FakeStream:
    def __init__(self, encoding: str):
        self.encoding = encoding


def test_supports_unicode_output_for_utf8():
    assert cli_main._supports_unicode_output(_FakeStream("utf-8")) is True


def test_supports_unicode_output_for_cp1254():
    assert cli_main._supports_unicode_output(_FakeStream("cp1254")) is False


def test_build_plain_help_root():
    help_text = cli_main._build_plain_help()
    assert "Usage:" in help_text
    assert "agents" in help_text
    assert "report" in help_text


def test_build_plain_help_for_check():
    help_text = cli_main._build_plain_help("check")
    assert "check TARGET" in help_text
    assert "--port" in help_text


def test_main_uses_plain_help_on_non_unicode_terminal(monkeypatch, capsys):
    called = []

    monkeypatch.setattr(cli_main, "UNICODE_OUTPUT", False)
    monkeypatch.setattr(cli_main, "enforce_supported_python", lambda: None)
    monkeypatch.setattr(cli_main, "app", lambda: called.append("app"))
    monkeypatch.setattr(cli_main.sys, "argv", ["cli.main", "--help"])

    cli_main.main()

    captured = capsys.readouterr()
    assert "Usage:" in captured.out
    assert not called


def test_check_command_ascii_fallback(monkeypatch):
    monkeypatch.setattr(cli_main, "UNICODE_OUTPUT", False)

    result = runner.invoke(cli_main.app, ["check", "127.0.0.1", "--port", "80"])

    assert result.exit_code == 0
    assert "IN-SCOPE: 127.0.0.1:80" in result.stdout


def test_agents_command_ascii_fallback(monkeypatch):
    monkeypatch.setattr(cli_main, "UNICODE_OUTPUT", False)

    result = runner.invoke(cli_main.app, ["agents"])

    assert result.exit_code == 0
    assert "Registered Agents" in result.stdout
    assert "commander" in result.stdout


def test_mission_single_phase_summary_uses_completed_status(monkeypatch):
    class FakeOrchestrator:
        def create_mission(self, name, targets, scope_profile="default"):
            return Mission(name=name, target_scope=targets, scope_profile=scope_profile)

        async def run_single_phase(self, phase, mission_obj):
            assert phase == AttackPhase.RECONNAISSANCE
            mission_obj.status = MissionStatus.COMPLETED
            mission_obj.add_finding(Finding(
                title="Smoke finding",
                severity=Severity.INFO,
                target=mission_obj.target_scope[0],
                agent_source="recon",
                phase=phase,
            ))
            return []

    monkeypatch.setattr(cli_main, "UNICODE_OUTPUT", False)
    monkeypatch.setattr(cli_main, "Orchestrator", FakeOrchestrator)

    result = runner.invoke(cli_main.app, [
        "mission",
        "--name", "Smoke",
        "--target", "127.0.0.1",
        "--phase", "reconnaissance",
    ])

    assert result.exit_code == 0
    assert "Status: COMPLETED" in result.stdout
    assert "Total findings: 1" in result.stdout
    assert "Status: PLANNING" not in result.stdout
