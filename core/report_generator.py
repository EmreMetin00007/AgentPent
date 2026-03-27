"""AgentPent — Report Generator.

Mission sonuçlarından HTML / JSON / Markdown rapor üretir.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.mission import Finding, Mission, Severity

logger = logging.getLogger("agentpent.core.report_generator")

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
SEVERITY_COLORS = {
    "CRITICAL": "#dc2626",
    "HIGH": "#ea580c",
    "MEDIUM": "#ca8a04",
    "LOW": "#2563eb",
    "INFO": "#6b7280",
}


class ReportData:
    """Rapor için yapılandırılmış veri."""

    def __init__(self, mission: Mission):
        self.mission = mission
        self.generated_at = datetime.now(timezone.utc)
        self.executive_summary: str = ""
        self.risk_rating: str = ""
        self.remediation_priority: List[Dict[str, Any]] = []

    @property
    def stats(self) -> Dict[str, int]:
        return self.mission.stats

    @property
    def total_findings(self) -> int:
        return len(self.mission.findings)

    @property
    def findings_by_severity(self) -> Dict[str, List[Finding]]:
        groups: Dict[str, List[Finding]] = defaultdict(list)
        for f in self.mission.findings:
            groups[f.severity.value].append(f)
        return dict(groups)

    @property
    def findings_by_agent(self) -> Dict[str, List[Finding]]:
        groups: Dict[str, List[Finding]] = defaultdict(list)
        for f in self.mission.findings:
            groups[f.agent_source].append(f)
        return dict(groups)

    @property
    def findings_by_target(self) -> Dict[str, List[Finding]]:
        groups: Dict[str, List[Finding]] = defaultdict(list)
        for f in self.mission.findings:
            groups[f.target].append(f)
        return dict(groups)

    @property
    def overall_risk(self) -> str:
        s = self.stats
        if s.get("CRITICAL", 0) > 0:
            return "CRITICAL"
        if s.get("HIGH", 0) > 0:
            return "HIGH"
        if s.get("MEDIUM", 0) > 0:
            return "MEDIUM"
        if s.get("LOW", 0) > 0:
            return "LOW"
        return "INFO"

    @property
    def exploitable_findings(self) -> List[Finding]:
        return [f for f in self.mission.findings if f.exploitable]

    @property
    def cve_list(self) -> List[str]:
        cves = set()
        for f in self.mission.findings:
            cves.update(f.cve_ids)
        return sorted(cves)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mission": {
                "id": self.mission.id,
                "name": self.mission.name,
                "targets": self.mission.target_scope,
                "status": self.mission.status.value,
                "created_at": self.mission.created_at.isoformat(),
                "phases_completed": [p.value for p in self.mission.phases_completed],
            },
            "report": {
                "generated_at": self.generated_at.isoformat(),
                "overall_risk": self.overall_risk,
                "executive_summary": self.executive_summary,
                "total_findings": self.total_findings,
                "stats": self.stats,
                "cve_list": self.cve_list,
                "exploitable_count": len(self.exploitable_findings),
            },
            "findings": [
                {
                    "id": f.id,
                    "severity": f.severity.value,
                    "title": f.title,
                    "target": f.target,
                    "port": f.port,
                    "service": f.service,
                    "cve_ids": f.cve_ids,
                    "cvss_score": f.cvss_score,
                    "description": f.description,
                    "evidence": f.evidence,
                    "remediation": f.remediation,
                    "agent_source": f.agent_source,
                    "phase": f.phase.value,
                    "exploitable": f.exploitable,
                    "timestamp": f.timestamp.isoformat(),
                    "mitre_tactics": f.mitre_tactics,
                    "mitre_techniques": f.mitre_techniques,
                }
                for f in sorted(
                    self.mission.findings,
                    key=lambda x: SEVERITY_ORDER.index(x.severity.value)
                    if x.severity.value in SEVERITY_ORDER
                    else 99,
                )
            ],
            "remediation_priority": self.remediation_priority,
        }


class ReportGenerator:
    """Rapor formatlarına dönüştürücü."""

    def __init__(self):
        pass

    def generate(
        self,
        mission: Mission,
        format: str = "html",
        output_path: Optional[str] = None,
        executive_summary: str = "",
    ) -> str:
        """Rapor üret. Formatlar: html, json, markdown."""
        report_data = ReportData(mission)
        report_data.executive_summary = executive_summary

        if format == "json":
            content = self._render_json(report_data)
        elif format == "markdown":
            content = self._render_markdown(report_data)
        else:
            content = self._render_html(report_data)

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(content, encoding="utf-8")
            logger.info("Rapor kaydedildi: %s", output_path)

        return content

    # ── JSON ─────────────────────────────────────────────

    def _render_json(self, data: ReportData) -> str:
        return json.dumps(data.to_dict(), indent=2, ensure_ascii=False)

    # ── Markdown ─────────────────────────────────────────

    def _render_markdown(self, data: ReportData) -> str:
        lines = []
        m = data.mission

        lines.append("# Pentest Raporu — {}".format(m.name))
        lines.append("")
        lines.append("**Tarih:** {}".format(data.generated_at.strftime("%Y-%m-%d %H:%M UTC")))
        lines.append("**Hedefler:** {}".format(", ".join(m.target_scope)))
        lines.append("**Genel Risk:** {}".format(data.overall_risk))
        lines.append("**Toplam Bulgu:** {}".format(data.total_findings))
        lines.append("")

        # Executive Summary
        if data.executive_summary:
            lines.append("## Executive Summary")
            lines.append("")
            lines.append(data.executive_summary)
            lines.append("")

        # İstatistikler
        lines.append("## Risk Özeti")
        lines.append("")
        lines.append("| Severity | Adet |")
        lines.append("|----------|------|")
        for sev in SEVERITY_ORDER:
            count = data.stats.get(sev, 0)
            lines.append("| {} | {} |".format(sev, count))
        lines.append("")

        # CVE listesi
        if data.cve_list:
            lines.append("## CVE Listesi")
            lines.append("")
            for cve in data.cve_list:
                lines.append("- {}".format(cve))
            lines.append("")

        # Bulgular
        lines.append("## Bulgular")
        lines.append("")
        for sev in SEVERITY_ORDER:
            findings = data.findings_by_severity.get(sev, [])
            if not findings:
                continue
            lines.append("### {} ({})".format(sev, len(findings)))
            lines.append("")
            for f in findings:
                port_str = ":{}".format(f.port) if f.port else ""
                lines.append("#### {}".format(f.title))
                lines.append("")
                lines.append("- **Hedef:** {}{}".format(f.target, port_str))
                if f.service:
                    lines.append("- **Servis:** {}".format(f.service))
                if f.cve_ids:
                    lines.append("- **CVE:** {}".format(", ".join(f.cve_ids)))
                if f.cvss_score:
                    lines.append("- **CVSS:** {}".format(f.cvss_score))
                if f.description:
                    lines.append("- **Açıklama:** {}".format(f.description))
                if f.evidence:
                    lines.append("- **Kanıt:** {}".format(f.evidence))
                if f.remediation:
                    lines.append("- **Düzeltme:** {}".format(f.remediation))
                if f.mitre_tactics or f.mitre_techniques:
                    lines.append("- **MITRE ATT&CK:** {} / {}".format(
                        ", ".join(f.mitre_tactics), ", ".join(f.mitre_techniques)
                    ))
                lines.append("- **Agent:** {}".format(f.agent_source))
                lines.append("")

        return "\n".join(lines)

    # ── HTML ─────────────────────────────────────────────

    def _render_html(self, data: ReportData) -> str:
        """Inline HTML rapor (Jinja2 bağımlılığı yok)."""
        m = data.mission
        stats = data.stats
        max_count = max(stats.values()) if stats.values() else 1

        # Risk bars
        bars_html = ""
        for sev in SEVERITY_ORDER:
            count = stats.get(sev, 0)
            pct = int((count / max_count) * 100) if max_count > 0 else 0
            color = SEVERITY_COLORS.get(sev, "#6b7280")
            bars_html += '<div class="bar-row"><span class="bar-label">{}</span><div class="bar-track"><div class="bar-fill" style="width:{}%;background:{}"></div></div><span class="bar-count">{}</span></div>\n'.format(sev, pct, color, count)

        # Findings rows
        findings_rows = ""
        for f in sorted(
            m.findings,
            key=lambda x: SEVERITY_ORDER.index(x.severity.value)
            if x.severity.value in SEVERITY_ORDER
            else 99,
        ):
            color = SEVERITY_COLORS.get(f.severity.value, "#6b7280")
            port_str = ":{}".format(f.port) if f.port else ""
            cve_str = ", ".join(f.cve_ids) if f.cve_ids else "-"
            cvss_str = str(f.cvss_score) if f.cvss_score else "-"
            remediation_str = f.remediation if f.remediation else "-"
            
            # MITRE Badge logic
            mitre_badges = ""
            for t in f.mitre_tactics:
                mitre_badges += f'<span class="badge" style="background:#475569;margin-right:2px">{self._escape(t)}</span>'
            for t in f.mitre_techniques:
                mitre_badges += f'<span class="badge" style="background:#334155;margin-right:2px">{self._escape(t)}</span>'
            if not mitre_badges:
                mitre_badges = "-"

            findings_rows += """<tr>
<td><span class="badge" style="background:{color}">{sev}</span></td>
<td><strong>{title}</strong><br><small>{desc}</small></td>
<td>{target}{port}</td>
<td>{cve}</td>
<td>{mitre}</td>
<td>{agent}</td>
<td>{remed}</td>
</tr>\n""".format(
                color=color,
                sev=f.severity.value,
                title=self._escape(f.title),
                desc=self._escape(f.description[:150]),
                target=self._escape(f.target),
                port=port_str,
                cve=cve_str,
                mitre=mitre_badges,
                agent=f.agent_source,
                remed=self._escape(remediation_str[:100]),
            )

        exec_summary = data.executive_summary if data.executive_summary else "Executive summary henüz oluşturulmadı."

        html = """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pentest Raporu — {name}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',system-ui,-apple-system,sans-serif;background:#0f172a;color:#e2e8f0;line-height:1.6}}
.container{{max-width:1200px;margin:0 auto;padding:2rem}}
header{{background:linear-gradient(135deg,#1e293b,#0f172a);border:1px solid #334155;border-radius:12px;padding:2rem;margin-bottom:2rem}}
header h1{{font-size:1.8rem;color:#38bdf8;margin-bottom:.5rem}}
header .meta{{color:#94a3b8;font-size:.9rem}}
header .meta span{{margin-right:1.5rem}}
.card{{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:1.5rem;margin-bottom:1.5rem}}
.card h2{{color:#38bdf8;font-size:1.3rem;margin-bottom:1rem;border-bottom:1px solid #334155;padding-bottom:.5rem}}
.risk-badge{{display:inline-block;padding:.3rem .8rem;border-radius:6px;font-weight:700;font-size:1rem}}
.bar-row{{display:flex;align-items:center;margin-bottom:.5rem}}
.bar-label{{width:80px;font-size:.85rem;font-weight:600}}
.bar-track{{flex:1;height:24px;background:#334155;border-radius:4px;overflow:hidden;margin:0 .8rem}}
.bar-fill{{height:100%;border-radius:4px;transition:width .5s ease}}
.bar-count{{width:30px;text-align:right;font-weight:700}}
table{{width:100%;border-collapse:collapse;font-size:.85rem}}
th{{background:#334155;color:#94a3b8;text-align:left;padding:.6rem .8rem;font-weight:600}}
td{{padding:.6rem .8rem;border-bottom:1px solid #1e293b;vertical-align:top}}
tr:hover td{{background:#334155}}
.badge{{display:inline-block;padding:.15rem .5rem;border-radius:4px;color:#fff;font-size:.75rem;font-weight:700}}
.exec-summary{{color:#cbd5e1;white-space:pre-wrap}}
.footer{{text-align:center;color:#475569;font-size:.8rem;margin-top:2rem;padding-top:1rem;border-top:1px solid #334155}}
</style>
</head>
<body>
<div class="container">
<header>
<h1>🎯 Pentest Raporu — {name}</h1>
<div class="meta">
<span>📅 {date}</span>
<span>🎯 Hedefler: {targets}</span>
<span>📊 Toplam Bulgu: {total}</span>
<span>Risk: <span class="risk-badge" style="background:{risk_color}">{risk}</span></span>
</div>
</header>

<div class="card">
<h2>📋 Executive Summary</h2>
<div class="exec-summary">{exec_summary}</div>
</div>

<div class="card">
<h2>📊 Risk Matrisi</h2>
{bars}
</div>

<div class="card">
<h2>🔍 Bulgular ({total})</h2>
<table>
<thead><tr><th>Severity</th><th>Bulgu</th><th>Hedef</th><th>CVE</th><th>MITRE ATT&CK</th><th>Agent</th><th>Remediation</th></tr></thead>
<tbody>
{findings}
</tbody>
</table>
</div>

<div class="footer">
AgentPent v0.1.0 — LLM-Centered Multi-Agent Pentester | Rapor {date} tarihinde oluşturuldu
</div>
</div>
</body>
</html>""".format(
            name=self._escape(m.name),
            date=data.generated_at.strftime("%Y-%m-%d %H:%M UTC"),
            targets=", ".join(m.target_scope),
            total=data.total_findings,
            risk=data.overall_risk,
            risk_color=SEVERITY_COLORS.get(data.overall_risk, "#6b7280"),
            exec_summary=self._escape(exec_summary),
            bars=bars_html,
            findings=findings_rows,
        )

        return html

    @staticmethod
    def _escape(text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# Singleton
report_generator = ReportGenerator()
