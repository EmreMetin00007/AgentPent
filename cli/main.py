"""AgentPent — CLI Arayüzü.

Typer + Rich ile terminal arayüzü.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from config.settings import settings
from core.mission import AttackPhase, MissionStatus
from core.orchestrator import Orchestrator

app = typer.Typer(
    name="agentpent",
    help="🎯 AgentPent — LLM-Merkezli Multi-Agent Pentester",
    add_completion=False,
)
console = Console()


def _setup_logging():
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(message)s",
        handlers=[
            RichHandler(console=console, show_path=False, markup=True),
            logging.FileHandler(log_dir / "agentpent.log", encoding="utf-8"),
        ],
    )


BANNER = r"""
    ╔══════════════════════════════════════════════════╗
    ║                                                  ║
    ║     █████╗  ██████╗ ███████╗███╗   ██╗████████╗  ║
    ║    ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝  ║
    ║    ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║     ║
    ║    ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║     ║
    ║    ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║     ║
    ║    ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝     ║
    ║                                                  ║
    ║    ██████╗ ███████╗███╗   ██╗████████╗           ║
    ║    ██╔══██╗██╔════╝████╗  ██║╚══██╔══╝           ║
    ║    ██████╔╝█████╗  ██╔██╗ ██║   ██║              ║
    ║    ██╔═══╝ ██╔══╝  ██║╚██╗██║   ██║              ║
    ║    ██║     ███████╗██║ ╚████║   ██║              ║
    ║    ╚═╝     ╚══════╝╚═╝  ╚═══╝   ╚═╝              ║
    ║                                                  ║
    ║  🎯 LLM-Centered Multi-Agent Pentester v0.1.0    ║
    ║  🔓 Autonomous Bug Bounty & Red Team Framework   ║
    ║  👤 Author: whoami                               ║
    ║                                                  ║
    ╚══════════════════════════════════════════════════╝
"""


def _banner():
    console.print(Panel(BANNER, style="bold red", border_style="bright_red"))


# ── Commands ─────────────────────────────────────────────


@app.command()
def mission(
    name: str = typer.Option("Pentest Mission", "--name", "-n", help="Mission adı"),
    target: Optional[List[str]] = typer.Option(None, "--target", "-t", help="Hedef IP/domain"),
    profile: str = typer.Option("default", "--profile", "-p", help="Scope profili"),
    phase: Optional[str] = typer.Option(None, "--phase", help="Tek faz çalıştır"),
):
    """Yeni bir pentest mission'ı başlat."""
    _setup_logging()
    _banner()

    if not target:
        console.print("[red]En az bir hedef belirtmelisiniz (--target / -t)[/]")
        raise typer.Exit(1)

    console.print("[bold green]Mission:[/] {}".format(name))
    console.print("[bold green]Hedefler:[/] {}".format(", ".join(target)))
    console.print("[bold green]Profil:[/] {}".format(profile))
    console.print()

    orch = Orchestrator()
    m = orch.create_mission(name=name, targets=target, scope_profile=profile)

    if phase:
        try:
            p = AttackPhase(phase)
        except ValueError:
            console.print("[red]Geçersiz faz: {}[/]".format(phase))
            console.print("Geçerli fazlar: {}".format([p.value for p in AttackPhase]))
            raise typer.Exit(1)
        console.print("[yellow]Tek faz çalıştırılıyor: {}[/]".format(p.value))
        asyncio.run(orch.run_single_phase(p, m))
    else:
        console.print("[yellow]Tam operasyon başlatılıyor...[/]")
        asyncio.run(orch.run(m))

    _print_results(m)


@app.command()
def scope(
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
):
    """Scope profillerini listele."""
    _setup_logging()
    from core.scope_guard import scope_guard

    table = Table(title="Scope Profilleri", border_style="bright_blue")
    table.add_column("Profil", style="cyan")
    table.add_column("Aktif", style="green")

    for name in scope_guard.profile_names:
        is_active = "✅" if name == scope_guard._active_profile else ""
        table.add_row(name, is_active)

    console.print(table)

    if profile:
        scope_guard.set_profile(profile)
        console.print("\n[green]Profil ayarlandı: {}[/]".format(profile))


@app.command()
def check(
    target: str = typer.Argument(..., help="Kontrol edilecek hedef"),
    port: Optional[int] = typer.Option(None, "--port", "-p"),
    profile: str = typer.Option("default", "--profile"),
):
    """Bir hedefin kapsamda olup olmadığını kontrol et."""
    _setup_logging()
    from core.scope_guard import scope_guard

    scope_guard.set_profile(profile)
    result = scope_guard.check(target, port)

    port_str = ":{}".format(port) if port else ""
    if result:
        console.print("[bold green]✅ KAPSAM İÇİ:[/] {}{}".format(target, port_str))
    else:
        console.print("[bold red]❌ KAPSAM DIŞI:[/] {}{}".format(target, port_str))


@app.command()
def agents():
    """Kayıtlı agent'ları listele."""
    _banner()
    table = Table(title="Kayıtlı Agent'lar", border_style="bright_blue")
    table.add_column("#", style="dim")
    table.add_column("Agent", style="cyan bold")
    table.add_column("Faz", style="yellow")
    table.add_column("Araçlar", style="green")
    table.add_column("Açıklama")

    from agents.commander.agent import CommanderAgent
    table.add_row("1", "commander", "ALL", "-", CommanderAgent.description)

    orch = Orchestrator()
    for idx, (name, agent) in enumerate(sorted(orch._agents.items()), start=2):
        tools_str = ", ".join(agent.available_tools) if agent.available_tools else "-"
        table.add_row(str(idx), name, agent.phase.value, tools_str, agent.description)

    console.print(table)
    console.print("\n[dim]Toplam {} agent kayıtlı.[/]".format(1 + len(orch._agents)))


@app.command()
def report(
    format: str = typer.Option("html", "--format", "-f", help="Rapor formatı: html, json, markdown"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Çıktı dosya yolu"),
    demo: bool = typer.Option(False, "--demo", help="Demo rapor oluştur (test amaçlı)"),
):
    """Mission sonuçlarından rapor oluştur."""
    _setup_logging()
    _banner()

    from core.report_generator import report_generator

    if demo:
        # Demo mission oluştur
        from core.mission import Mission, MissionStatus, Finding, Severity, AttackPhase
        m = Mission(
            name="Demo Pentest Mission",
            target_scope=["10.10.10.5", "example.lab"],
        )
        m.status = MissionStatus.COMPLETED
        m.add_finding(Finding(
            title="Apache Path Traversal (CVE-2021-41773)",
            severity=Severity.CRITICAL, target="10.10.10.5", port=80,
            service="Apache httpd 2.4.49", cve_ids=["CVE-2021-41773"],
            cvss_score=9.8, description="Path traversal zafiyeti",
            remediation="Apache 2.4.51+ sürümüne güncelle",
            agent_source="scanner", phase=AttackPhase.SCANNING,
            exploitable=True,
            mitre_tactics=["TA0001", "TA0002"],
            mitre_techniques=["T1190"]
        ))
        m.add_finding(Finding(
            title="SQL Injection — login.php",
            severity=Severity.CRITICAL, target="10.10.10.5", port=80,
            service="PHP/MySQL", description="Boolean-based blind SQLi",
            remediation="Parameterized query kullan",
            agent_source="webapp", phase=AttackPhase.VULNERABILITY_ANALYSIS,
            exploitable=True,
            mitre_tactics=["TA0006"],
            mitre_techniques=["T1110"]
        ))
        m.add_finding(Finding(
            title="SSH Açık Port",
            severity=Severity.INFO, target="10.10.10.5", port=22,
            service="OpenSSH 8.9p1", description="SSH portu açık",
            agent_source="recon", phase=AttackPhase.RECONNAISSANCE,
        ))
    else:
        console.print("[yellow]Demo rapor için --demo flag'ini kullanın.[/]")
        console.print("[dim]Gerçek mission raporlaması tam operasyon sonrası çalışır.[/]")
        raise typer.Exit(0)

    ext_map = {"html": ".html", "json": ".json", "markdown": ".md"}
    if not output:
        output = "reports/pentest_report{}".format(ext_map.get(format, ".html"))

    content = report_generator.generate(
        mission=m,
        format=format,
        output_path=output,
        executive_summary="Bu demo pentest raporunda 10.10.10.5 hedefinde 3 bulgu tespit edildi. "
        "2 kritik zafiyet (Path Traversal, SQL Injection) acil düzeltme gerektirmektedir.",
    )

    console.print("[bold green][+] Rapor oluşturuldu:[/] {}".format(output))
    console.print("[dim]Format: {} | Bulgu: {} | Risk: {}[/]".format(
        format.upper(), len(m.findings), "CRITICAL" if m.stats.get("CRITICAL") else "LOW"
    ))


# ── Yardımcılar ──────────────────────────────────────────


def _print_results(mission):
    console.print()
    stats = mission.stats
    summary_text = Text()
    summary_text.append("Durum: {}\n".format(mission.status.value.upper()), style="bold")
    summary_text.append("Toplam Bulgu: {}\n".format(len(mission.findings)))
    summary_text.append("CRITICAL: {}  ".format(stats.get("CRITICAL", 0)), style="bold red")
    summary_text.append("HIGH: {}  ".format(stats.get("HIGH", 0)), style="bold yellow")
    summary_text.append("MEDIUM: {}  ".format(stats.get("MEDIUM", 0)), style="bold blue")
    summary_text.append("LOW: {}  ".format(stats.get("LOW", 0)), style="dim")
    summary_text.append("INFO: {}".format(stats.get("INFO", 0)), style="dim")

    console.print(Panel(summary_text, title="Mission Sonuçları", border_style="bright_green"))

    if mission.findings:
        ftable = Table(title="Bulgular", border_style="bright_blue")
        ftable.add_column("Şiddet", style="bold")
        ftable.add_column("Başlık")
        ftable.add_column("Hedef")
        ftable.add_column("Agent")

        severity_styles = {
            "CRITICAL": "bold red",
            "HIGH": "bold yellow",
            "MEDIUM": "blue",
            "LOW": "dim",
            "INFO": "dim italic",
        }

        for f in mission.findings:
            style = severity_styles.get(f.severity.value, "")
            ftable.add_row(
                Text(f.severity.value, style=style),
                f.title,
                "{}:{}".format(f.target, f.port) if f.port else f.target,
                f.agent_source,
            )
        console.print(ftable)


def main():
    app()


if __name__ == "__main__":
    main()
