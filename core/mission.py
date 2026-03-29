"""AgentPent — Mission & Finding data models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class MissionStatus(str, Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABORTED = "aborted"


class AttackPhase(str, Enum):
    RECONNAISSANCE = "reconnaissance"
    SCANNING = "scanning"
    VULNERABILITY_ANALYSIS = "vulnerability_analysis"
    EXPLOITATION = "exploitation"
    POST_EXPLOITATION = "post_exploitation"
    REPORTING = "reporting"


# ── Data Models ──────────────────────────────────────────


class Finding(BaseModel):
    """Tek bir güvenlik bulgusunu temsil eder."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    severity: Severity = Severity.INFO
    title: str
    description: str = ""
    target: str  # IP / URL / hostname
    port: Optional[int] = None
    service: Optional[str] = None
    cve_ids: List[str] = Field(default_factory=list)
    cvss_score: Optional[float] = None
    evidence: str = ""
    remediation: str = ""
    agent_source: str = ""  # Hangi agent buldu
    phase: AttackPhase = AttackPhase.RECONNAISSANCE
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    exploitable: bool = False
    exploit_result: Optional[str] = None
    mitre_tactics: List[str] = Field(default_factory=list)
    mitre_techniques: List[str] = Field(default_factory=list)

    def short(self) -> str:
        """Kısa özet: [CRITICAL] SQL Injection on 10.0.0.5:3306"""
        port_str = f":{self.port}" if self.port else ""
        return f"[{self.severity.value}] {self.title} on {self.target}{port_str}"


class Mission(BaseModel):
    """Bir pentest görevini (engagement) temsil eder."""

    model_config = {"arbitrary_types_allowed": True}

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str = "Unnamed Mission"
    target_scope: List[str] = Field(default_factory=list)  # IP / domain / CIDR
    scope_profile: str = "default"
    status: MissionStatus = MissionStatus.PLANNING
    current_phase: AttackPhase = AttackPhase.RECONNAISSANCE
    phases_completed: List[AttackPhase] = Field(default_factory=list)
    findings: List[Finding] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    attack_graph: Any = Field(default=None, exclude=True)  # AttackGraph instance
    commander_notes: str = ""

    # ── Convenience ──────────────────────────────────────

    def add_finding(self, finding: Finding) -> None:
        self.findings.append(finding)
        self.updated_at = datetime.now(timezone.utc)
        self._rebuild_graph()

    def _rebuild_graph(self) -> None:
        """Attack graph'ı mevcut finding'lerden yeniden oluştur."""
        try:
            from core.attack_graph import AttackGraph
            self.attack_graph = AttackGraph.from_findings(self.findings)
        except Exception:
            pass  # Graph oluşturma opsiyonel

    def advance_phase(self) -> Optional[AttackPhase]:
        """Mevcut fazı tamamladı olarak işaretle ve bir sonraki faza geç."""
        order = list(AttackPhase)
        idx = order.index(self.current_phase)
        self.phases_completed.append(self.current_phase)
        if idx + 1 < len(order):
            self.current_phase = order[idx + 1]
            self.updated_at = datetime.now(timezone.utc)
            return self.current_phase
        self.status = MissionStatus.COMPLETED
        self.updated_at = datetime.now(timezone.utc)
        return None

    @property
    def stats(self) -> Dict[str, int]:
        counts: Dict[str, int] = {s.value: 0 for s in Severity}
        for f in self.findings:
            counts[f.severity.value] += 1
        return counts
