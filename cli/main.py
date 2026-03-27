"""AgentPent CLI."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, TextIO

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from config.settings import settings
from core.mission import AttackPhase
from core.orchestrator import Orchestrator
from core.runtime import enforce_supported_python

app = typer.Typer(
    name="agentpent",
    help="AgentPent - LLM-centered multi-agent pentester",
    add_completion=False,
)
console = Console(emoji=False)


ASCII_BANNER = "=" * 60 + "\nAgentPent | LLM-Centered Multi-Agent Pentester\n" + "=" * 60
UNICODE_BANNER = "AgentPent | LLM-Centered Multi-Agent Pentester"

PLAIN_HELP: Dict[Optional[str], str] = {
    None: (
        "Usage:\n"
        "  python -m cli.main [OPTIONS] COMMAND [ARGS]...\n\n"
        "Commands:\n"
        "  mission  Start a new pentest mission\n"
        "  scope    List scope profiles\n"
        "  check    Check whether a target is in scope\n"
        "  agents   List registered agents\n"
        "  report   Generate a report\n"
    ),
    "mission": (
        "Usage:\n"
        "  python -m cli.main mission [OPTIONS]\n\n"
        "Options:\n"
        "  --name, -n TEXT\n"
        "  --target, -t TEXT\n"
        "  --profile, -p TEXT\n"
        "  --phase TEXT\n"
    ),
    "scope": (
        "Usage:\n"
        "  python -m cli.main scope [OPTIONS]\n\n"
        "Options:\n"
        "  --profile, -p TEXT\n"
    ),
    "check": (
        "Usage:\n"
        "  python -m cli.main check TARGET [OPTIONS]\n\n"
        "Options:\n"
        "  --port, -p INTEGER\n"
        "  --profile TEXT\n"
    ),
    "agents": (
        "Usage:\n"
        "  python -m cli.main agents\n"
    ),
    "report": (
        "Usage:\n"
        "  python -m cli.main report [OPTIONS]\n\n"
        "Options:\n"
        "  --format, -f [html|json|markdown]\n"
        "  --output, -o TEXT\n"
        "  --demo\n"
    ),
}


def _stream_encoding(stream: Optional[TextIO] = None) -> str:
    stream = stream or sys.stdout
    return getattr(stream, "encoding", None) or "utf-8"


def _safe_text(text: str, stream: Optional[TextIO] = None) -> str:
    encoding = _stream_encoding(stream)
    try:
        return text.encode(encoding, errors="replace").decode(encoding, errors="replace")
    except LookupError:
        return text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")


def _supports_unicode_output(stream: Optional[TextIO] = None) -> bool:
    encoding = _stream_encoding(stream)
    try:
        "AgentPent - scope -> ok".encode(encoding)
        "AgentPent ✓".encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return False
    return True


UNICODE_OUTPUT = _supports_unicode_output()


class _SafeConsoleFormatter(logging.Formatter):
    """Sanitize console log output for non-Unicode terminals."""

    def format(self, record: logging.LogRecord) -> str:
        return _safe_text(super().format(record), sys.stderr)


def _setup_logging() -> None:
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    handlers: List[logging.Handler] = []
    if UNICODE_OUTPUT:
        handlers.append(RichHandler(console=console, show_path=False, markup=True))
    else:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(_SafeConsoleFormatter("%(message)s"))
        handlers.append(stream_handler)

    handlers.append(logging.FileHandler(log_dir / "agentpent.log", encoding="utf-8"))

    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(message)s",
        handlers=handlers,
        force=True,
    )


def _echo(message: str, *, style: Optional[str] = None) -> None:
    message = _safe_text(message)
    if UNICODE_OUTPUT and style:
        console.print(Text(message, style=style))
    else:
        typer.echo(message)


def _target_label(target: str, port: Optional[int] = None) -> str:
    return "{}:{}".format(target, port) if port is not None else target


def _build_scope_message(result: bool, target: str, port: Optional[int] = None) -> str:
    prefix = "IN-SCOPE" if result else "OUT-OF-SCOPE"
    return "{}: {}".format(prefix, _target_label(target, port))


def _print_banner() -> None:
    if UNICODE_OUTPUT:
        console.print(Panel(UNICODE_BANNER, style="bold red", border_style="bright_red"))
    else:
        typer.echo(_safe_text(ASCII_BANNER))


def _build_plain_help(command: Optional[str] = None) -> str:
    return PLAIN_HELP.get(command, PLAIN_HELP[None])


def _command_from_args(args: Sequence[str]) -> Optional[str]:
    for arg in args:
        if arg in {"-h", "--help"}:
            continue
        if arg.startswith("-"):
            continue
        return arg
    return None


def _should_use_plain_help(args: Sequence[str]) -> bool:
    return not UNICODE_OUTPUT and any(arg in {"-h", "--help"} for arg in args)


@app.command()
def mission(
    name: str = typer.Option("Pentest Mission", "--name", "-n", help="Mission name"),
    target: Optional[List[str]] = typer.Option(None, "--target", "-t", help="Target IP or domain"),
    profile: str = typer.Option("default", "--profile", "-p", help="Scope profile"),
    phase: Optional[str] = typer.Option(None, "--phase", help="Run only one phase"),
) -> None:
    """Start a new pentest mission."""
    _setup_logging()
    _print_banner()

    if not target:
        _echo("At least one target is required (--target / -t).", style="bold red")
        raise typer.Exit(1)

    _echo("Mission: {}".format(name), style="bold green")
    _echo("Targets: {}".format(", ".join(target)), style="bold green")
    _echo("Profile: {}".format(profile), style="bold green")
    _echo("")

    orch = Orchestrator()
    mission_obj = orch.create_mission(name=name, targets=target, scope_profile=profile)

    if phase:
        try:
            selected_phase = AttackPhase(phase)
        except ValueError:
            _echo("Invalid phase: {}".format(phase), style="bold red")
            _echo("Valid phases: {}".format([item.value for item in AttackPhase]))
            raise typer.Exit(1)
        _echo("Running single phase: {}".format(selected_phase.value), style="yellow")
        asyncio.run(orch.run_single_phase(selected_phase, mission_obj))
    else:
        _echo("Starting full operation...", style="yellow")
        asyncio.run(orch.run(mission_obj))

    _print_results(mission_obj)


@app.command()
def scope(
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
) -> None:
    """List scope profiles."""
    _setup_logging()
    from core.scope_guard import scope_guard

    if UNICODE_OUTPUT:
        table = Table(title="Scope Profiles", border_style="bright_blue")
        table.add_column("Profile", style="cyan")
        table.add_column("Active", style="green")

        for name in scope_guard.profile_names:
            is_active = "*" if name == scope_guard._active_profile else ""
            table.add_row(name, is_active)

        console.print(table)
    else:
        typer.echo(_safe_text("Scope Profiles"))
        for name in scope_guard.profile_names:
            marker = "*" if name == scope_guard._active_profile else " "
            typer.echo(_safe_text("[{}] {}".format(marker, name)))

    if profile:
        scope_guard.set_profile(profile)
        _echo("Profile set to: {}".format(profile), style="green")


@app.command()
def check(
    target: str = typer.Argument(..., help="Target to validate"),
    port: Optional[int] = typer.Option(None, "--port", "-p"),
    profile: str = typer.Option("default", "--profile"),
) -> None:
    """Check whether a target is within the active scope."""
    _setup_logging()
    from core.scope_guard import scope_guard

    scope_guard.set_profile(profile)
    result = scope_guard.check(target, port)
    _echo(
        _build_scope_message(result, target, port),
        style="bold green" if result else "bold red",
    )


@app.command()
def agents() -> None:
    """List registered agents."""
    _print_banner()

    from agents.commander.agent import CommanderAgent

    orch = Orchestrator()
    rows = [("1", "commander", "ALL", "-", CommanderAgent.description)]
    for idx, (name, agent) in enumerate(sorted(orch._agents.items()), start=2):
        tools_str = ", ".join(agent.available_tools) if agent.available_tools else "-"
        rows.append((str(idx), name, agent.phase.value, tools_str, agent.description))

    if UNICODE_OUTPUT:
        table = Table(title="Registered Agents", border_style="bright_blue")
        table.add_column("#", style="dim")
        table.add_column("Agent", style="cyan bold")
        table.add_column("Phase", style="yellow")
        table.add_column("Tools", style="green")
        table.add_column("Description")

        for row in rows:
            table.add_row(*row)

        console.print(table)
        _echo("Total registered agents: {}".format(len(rows)), style="dim")
        return

    typer.echo(_safe_text("Registered Agents"))
    for row in rows:
        typer.echo(
            _safe_text(
                "{idx}. {name} | phase={phase} | tools={tools} | {description}".format(
                    idx=row[0],
                    name=row[1],
                    phase=row[2],
                    tools=row[3],
                    description=row[4],
                )
            )
        )
    typer.echo(_safe_text("Total registered agents: {}".format(len(rows))))


@app.command()
def report(
    format: str = typer.Option("html", "--format", "-f", help="Report format: html, json, markdown"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output path"),
    demo: bool = typer.Option(False, "--demo", help="Generate a demo report"),
) -> None:
    """Generate a report from mission results."""
    _setup_logging()
    _print_banner()

    from core.report_generator import report_generator

    if demo:
        from core.mission import Finding, Mission, MissionStatus, Severity

        mission_obj = Mission(
            name="Demo Pentest Mission",
            target_scope=["10.10.10.5", "example.lab"],
        )
        mission_obj.status = MissionStatus.COMPLETED
        mission_obj.add_finding(Finding(
            title="Apache Path Traversal (CVE-2021-41773)",
            severity=Severity.CRITICAL,
            target="10.10.10.5",
            port=80,
            service="Apache httpd 2.4.49",
            cve_ids=["CVE-2021-41773"],
            cvss_score=9.8,
            description="Path traversal vulnerability",
            remediation="Upgrade Apache to 2.4.51+",
            agent_source="scanner",
            phase=AttackPhase.SCANNING,
            exploitable=True,
            mitre_tactics=["TA0001", "TA0002"],
            mitre_techniques=["T1190"],
        ))
        mission_obj.add_finding(Finding(
            title="SQL Injection - login.php",
            severity=Severity.CRITICAL,
            target="10.10.10.5",
            port=80,
            service="PHP/MySQL",
            description="Boolean-based blind SQL injection",
            remediation="Use parameterized queries",
            agent_source="webapp",
            phase=AttackPhase.VULNERABILITY_ANALYSIS,
            exploitable=True,
            mitre_tactics=["TA0006"],
            mitre_techniques=["T1110"],
        ))
        mission_obj.add_finding(Finding(
            title="Open SSH Port",
            severity=Severity.INFO,
            target="10.10.10.5",
            port=22,
            service="OpenSSH 8.9p1",
            description="SSH port is open",
            agent_source="recon",
            phase=AttackPhase.RECONNAISSANCE,
        ))
    else:
        _echo("Use --demo to generate a sample report.", style="yellow")
        _echo("Real mission reporting runs after an operation completes.", style="dim")
        raise typer.Exit(0)

    ext_map = {"html": ".html", "json": ".json", "markdown": ".md"}
    if not output:
        output = "reports/pentest_report{}".format(ext_map.get(format, ".html"))

    report_generator.generate(
        mission=mission_obj,
        format=format,
        output_path=output,
        executive_summary=(
            "This demo pentest report found 3 findings on target 10.10.10.5. "
            "Two critical findings require immediate remediation."
        ),
    )

    _echo("Report generated: {}".format(output), style="bold green")
    _echo(
        "Format: {} | Findings: {} | Risk: {}".format(
            format.upper(),
            len(mission_obj.findings),
            "CRITICAL" if mission_obj.stats.get("CRITICAL") else "LOW",
        ),
        style="dim",
    )


def _print_results(mission_obj) -> None:
    stats = mission_obj.stats
    summary_lines = [
        "Status: {}".format(mission_obj.status.value.upper()),
        "Total findings: {}".format(len(mission_obj.findings)),
        "CRITICAL: {}".format(stats.get("CRITICAL", 0)),
        "HIGH: {}".format(stats.get("HIGH", 0)),
        "MEDIUM: {}".format(stats.get("MEDIUM", 0)),
        "LOW: {}".format(stats.get("LOW", 0)),
        "INFO: {}".format(stats.get("INFO", 0)),
    ]

    if UNICODE_OUTPUT:
        summary_text = Text("\n".join(summary_lines))
        console.print(Panel(summary_text, title="Mission Summary", border_style="bright_green"))
    else:
        typer.echo(_safe_text("\n".join(summary_lines)))

    if not mission_obj.findings:
        return

    if UNICODE_OUTPUT:
        findings_table = Table(title="Findings", border_style="bright_blue")
        findings_table.add_column("Severity", style="bold")
        findings_table.add_column("Title")
        findings_table.add_column("Target")
        findings_table.add_column("Agent")

        severity_styles = {
            "CRITICAL": "bold red",
            "HIGH": "bold yellow",
            "MEDIUM": "blue",
            "LOW": "dim",
            "INFO": "dim italic",
        }

        for finding in mission_obj.findings:
            findings_table.add_row(
                Text(finding.severity.value, style=severity_styles.get(finding.severity.value, "")),
                finding.title,
                _target_label(finding.target, finding.port),
                finding.agent_source,
            )
        console.print(findings_table)
        return

    typer.echo(_safe_text("Findings"))
    for finding in mission_obj.findings:
        typer.echo(
            _safe_text(
                "[{severity}] {title} | target={target} | agent={agent}".format(
                    severity=finding.severity.value,
                    title=finding.title,
                    target=_target_label(finding.target, finding.port),
                    agent=finding.agent_source,
                )
            )
        )


def main() -> None:
    enforce_supported_python()
    args = sys.argv[1:]
    if _should_use_plain_help(args):
        typer.echo(_safe_text(_build_plain_help(_command_from_args(args))))
        return
    app()


if __name__ == "__main__":
    main()
