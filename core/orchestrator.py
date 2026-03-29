"""AgentPent — Orchestrator.

Ana iş akışı motoru. Commander agent'ı kullanarak
tüm pentest operasyonunu yönetir.

Production features:
- Retry/backoff ile hata toleransı
- Mission timeout
- Structured audit trail
- Graceful shutdown
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, List, Optional

from agents.base_agent import AgentResult, BaseAgent
from agents.commander.agent import CommanderAgent
from core.audit import audit
from core.memory import ConversationMemory
from core.mission import AttackPhase, Mission, MissionStatus
from core.scope_guard import scope_guard
from core.utils import extract_json_from_llm
from config.settings import settings

logger = logging.getLogger("agentpent.orchestrator")

# ── Retry Helpers ────────────────────────────────────────

_DEFAULT_MAX_RETRIES = 3
_DEFAULT_BACKOFF_BASE = 1.5  # saniye


async def _retry_async(coro_factory, *, max_retries=_DEFAULT_MAX_RETRIES, label=""):
    """Async callable'ı exponential backoff ile retry et."""
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            return await coro_factory()
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                wait = _DEFAULT_BACKOFF_BASE ** attempt
                logger.warning(
                    "[Retry] %s — deneme %d/%d başarısız: %s (%.1fs bekle)",
                    label, attempt, max_retries, exc, wait,
                )
                await asyncio.sleep(wait)
            else:
                logger.error(
                    "[Retry] %s — %d deneme sonrası başarısız: %s",
                    label, max_retries, exc,
                )
    raise last_exc  # type: ignore[misc]


class Orchestrator:
    """Pentest operasyonunu orkestre eden ana motor."""

    def __init__(self):
        self.commander = CommanderAgent()
        self._agents: Dict[str, BaseAgent] = {}
        self._memory = ConversationMemory()
        self._mission: Optional[Mission] = None
        self._running = False
        self.commander.model = settings.planning_model
        self._register_default_agents()

    def _register_default_agents(self) -> None:
        """Keşif + Analiz + Exploitation agent'larını otomatik kaydet."""
        agent_imports = [
            # Faz 2 — Keşif
            ("agents.recon.agent", "ReconAgent"),
            ("agents.scanner.agent", "ScannerAgent"),
            ("agents.osint.agent", "OSINTAgent"),
            ("agents.vuln_analyzer.agent", "VulnAnalyzerAgent"),
            ("agents.webapp.agent", "WebAppAgent"),
            ("agents.exploit.agent", "ExploitAgent"),
            # Critic / Red Teamer
            ("agents.critic.agent", "CriticAgent"),
            ("agents.thinker.agent", "ThinkerAgent"),
            # Faz 4 — İleri Yetenekler
            ("agents.post_exploit.agent", "PostExploitAgent"),
            ("agents.network.agent", "NetworkAgent"),
            ("agents.evasion.agent", "EvasionAgent"),
            ("agents.social_eng.agent", "SocialEngAgent"),
            ("agents.persist.agent", "PersistAgent"),
            # Faz 5 — Raporlama
            ("agents.reporter.agent", "ReporterAgent"),
        ]
        for module_path, class_name in agent_imports:
            try:
                import importlib
                mod = importlib.import_module(module_path)
                AgentClass = getattr(mod, class_name)
                self.register_agent(AgentClass())
            except (ImportError, AttributeError) as exc:
                logger.debug("Agent yüklenemedi (%s): %s", class_name, exc)

    # ── Agent Kayıt ──────────────────────────────────────

    def register_agent(self, agent: BaseAgent) -> None:
        self._agents[agent.name] = agent
        logger.info("Agent kaydedildi: %s", agent.name)

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        return self._agents.get(name)

    @property
    def registered_agents(self) -> List[str]:
        return list(self._agents.keys())

    # ── Mission Yönetimi ─────────────────────────────────

    def create_mission(
        self,
        name: str,
        targets: List[str],
        scope_profile: str = "default",
    ) -> Mission:
        scope_guard.set_profile(scope_profile)
        mission = Mission(
            name=name,
            target_scope=targets,
            scope_profile=scope_profile,
        )
        self._mission = mission
        self._memory.clear()
        self._memory.add_system(
            "Yeni mission başlatıldı: {}\nHedefler: {}\nScope profili: {}".format(
                name, ", ".join(targets), scope_profile
            )
        )
        audit.set_mission(mission.id)
        audit.log("mission_created", detail={
            "name": name, "targets": targets, "profile": scope_profile,
        })

        # Graph tools modülünü mission graph'ına bağla
        try:
            from tools.graph_tools import set_active_graph
            from core.attack_graph import AttackGraph
            mission.attack_graph = AttackGraph()
            set_active_graph(mission.attack_graph)
        except ImportError:
            pass

        logger.info("Mission oluşturuldu: %s (hedef: %s)", name, targets)
        return mission

    @property
    def mission(self) -> Optional[Mission]:
        return self._mission

    @property
    def memory(self) -> ConversationMemory:
        return self._memory

    # ── Ana Çalıştırma ───────────────────────────────────

    async def run(self, mission: Optional[Mission] = None) -> Mission:
        mission = mission or self._mission
        if not mission:
            raise ValueError("Aktif mission yok — önce create_mission() çağır")

        mission.status = MissionStatus.ACTIVE
        self._running = True
        mission_start = time.monotonic()
        timeout = settings.mission_timeout_seconds

        logger.info("=" * 60)
        logger.info("OPERASYON BAŞLATILDI: %s", mission.name)
        logger.info("=" * 60)

        try:
            while self._running and mission.status == MissionStatus.ACTIVE:
                # Mission timeout kontrolü
                elapsed = time.monotonic() - mission_start
                if elapsed > timeout:
                    logger.warning(
                        "⏰ Mission timeout! (%.0fs > %ds)", elapsed, timeout
                    )
                    audit.log("mission_timeout", detail={
                        "elapsed_seconds": round(elapsed),
                        "timeout": timeout,
                    })
                    mission.status = MissionStatus.COMPLETED
                    break

                phase = mission.current_phase
                logger.info("-" * 40)
                logger.info("FAZ: %s", phase.value.upper())
                logger.info("-" * 40)

                # Commander kararı — retry ile
                decision = await _retry_async(
                    lambda: self.commander.decide_next(mission, self._memory),
                    label="commander.decide_next",
                )
                logger.info("Commander kararı: %s", decision.get("decision"))
                audit.decision(
                    decision.get("decision", "unknown"),
                    detail={"reasoning": str(decision.get("reasoning", ""))[:300]},
                )

                # ── Multi-Agent Debate Loop (Jüri) ────────────────
                import json
                critic = self.get_agent("critic")
                thinker = self.get_agent("thinker")

                if decision.get("tasks") and decision.get("decision") in (
                    "specific_agent", "next_phase", ""
                ):
                    for _ in range(2):
                        vetoed = False

                        # 1. Thinker Kontrolü
                        if thinker:
                            try:
                                prompt_t = "Commander planı: {}\nDerinlemesine düşün ve potansiyel riskleri incele.".format(
                                    json.dumps(decision, ensure_ascii=False)
                                )
                                t_res = await _retry_async(
                                    lambda: thinker.run(prompt_t, mission, self._memory),
                                    label="thinker.review",
                                )
                                t_data = extract_json_from_llm(t_res.raw_response)
                                if t_data and not t_data.get("approved", True):
                                    reason = t_data.get("reason", "Bilinmeyen itiraz.")
                                    logger.warning("🧠 Thinker Veto Etti: %s", reason)
                                    audit.veto("thinker", reason)
                                    self._memory.add_system(
                                        "🚨 THINKER REDDETTİ: {}. Planı güncelle.".format(reason)
                                    )
                                    decision = await _retry_async(
                                        lambda: self.commander.decide_next(mission, self._memory),
                                        label="commander.re-decide(thinker)",
                                    )
                                    vetoed = True
                                else:
                                    r = t_data.get("reason", "OK") if t_data else "Parse edilemedi"
                                    logger.info("🧠 Thinker ONAYLADI: %s", r)
                            except Exception as e:
                                logger.warning("Thinker hatası (atlanıyor): %s", e)

                        # 2. Critic Kontrolü
                        if not vetoed and critic:
                            try:
                                prompt_c = "İncele (OPSEC/Halisülasyon):\n{}".format(
                                    json.dumps(decision, ensure_ascii=False)
                                )
                                critic_res = await _retry_async(
                                    lambda: critic.run(prompt_c, mission, self._memory),
                                    label="critic.review",
                                )
                                c_data = extract_json_from_llm(critic_res.raw_response)
                                if c_data and not c_data.get("approved", True):
                                    reason = c_data.get("reason", "Bilinmeyen itiraz.")
                                    logger.warning("🛡️ Critic Veto Etti: %s", reason)
                                    audit.veto("critic", reason)
                                    self._memory.add_system(
                                        "🚨 CRITIC REDDETTİ: {}. Planı güncelle.".format(reason)
                                    )
                                    decision = await _retry_async(
                                        lambda: self.commander.decide_next(mission, self._memory),
                                        label="commander.re-decide(critic)",
                                    )
                                    vetoed = True
                                else:
                                    r = c_data.get("reason", "OK") if c_data else "Parse edilemedi"
                                    logger.info("🛡️ Critic ONAYLADI: %s", r)
                            except Exception as e:
                                logger.warning("Critic hatası (atlanıyor): %s", e)

                        if not vetoed:
                            logger.info("⚖️ Konsensüs sağlandı. İşleme geçiliyor...")
                            break

                action = decision.get("decision", "next_phase")

                if action == "abort":
                    logger.warning("Commander: ABORT kararı")
                    audit.decision("abort")
                    mission.status = MissionStatus.ABORTED
                    break

                target_agents = decision.get("target_agents", [])
                if not target_agents:
                    phase_config = self.commander.get_phase_agents(phase)
                    target_agents = phase_config.get("agents", [])

                results = await self._run_agents(
                    target_agents,
                    decision.get("tasks", []),
                    mission,
                    parallel=decision.get("parallel", False),
                )

                for result in results:
                    for finding in result.findings:
                        mission.add_finding(finding)

                if action in ("next_phase", ""):
                    prev_phase = mission.current_phase
                    next_phase = mission.advance_phase()
                    audit.phase_transition(
                        prev_phase.value,
                        next_phase.value if next_phase else "completed",
                        len(mission.findings),
                    )
                    if next_phase is None:
                        logger.info("Tüm fazlar tamamlandı!")
                        break
                    logger.info("Sonraki faz: %s", next_phase.value)

                if decision.get("notes"):
                    mission.commander_notes = decision["notes"]

        except Exception as exc:
            logger.error("Operasyon hatası: %s", exc, exc_info=True)
            audit.log("mission_error", success=False, detail={"error": str(exc)})
            mission.status = MissionStatus.ABORTED

        finally:
            self._running = False
            self._memory.save(mission.id)
            audit.log("mission_completed", detail={
                "status": mission.status.value,
                "findings": len(mission.findings),
                "duration_seconds": round(time.monotonic() - mission_start),
            })
            audit.close()

        logger.info("=" * 60)
        logger.info("OPERASYON TAMAMLANDI: %s", mission.status.value)
        logger.info(
            "Toplam bulgu: %d (C:%d H:%d M:%d L:%d I:%d)",
            len(mission.findings),
            mission.stats.get("CRITICAL", 0),
            mission.stats.get("HIGH", 0),
            mission.stats.get("MEDIUM", 0),
            mission.stats.get("LOW", 0),
            mission.stats.get("INFO", 0),
        )
        logger.info("=" * 60)
        return mission

    async def run_single_phase(
        self,
        phase: AttackPhase,
        mission: Optional[Mission] = None,
    ) -> List[AgentResult]:
        mission = mission or self._mission
        if not mission:
            raise ValueError("Aktif mission yok")
        mission.current_phase = phase
        phase_config = self.commander.get_phase_agents(phase)
        agents = phase_config.get("agents", [])
        return await self._run_agents(
            agents, [], mission, parallel=phase_config.get("parallel", False)
        )

    # ── Agent Çalıştırma ─────────────────────────────────

    async def _run_agents(
        self,
        agent_names: List[str],
        tasks: List[Dict],
        mission: Mission,
        parallel: bool = False,
    ) -> List[AgentResult]:
        results: List[AgentResult] = []

        task_map: Dict[str, str] = {}
        for t in tasks:
            agent_name = t.get("agent", "")
            task_desc = t.get("task", "")
            if agent_name:
                task_map[agent_name] = task_desc

        async def _run_single_agent(name: str) -> AgentResult:
            agent = self._agents.get(name)
            if not agent:
                logger.warning("Agent bulunamadı: %s (atlanıyor)", name)
                return AgentResult(
                    agent_name=name, success=False,
                    error="Agent bulunamadı: {}".format(name),
                )
            task = task_map.get(
                name,
                "{} fazını çalıştır: {}".format(name, ", ".join(mission.target_scope)),
            )
            try:
                return await _retry_async(
                    lambda: agent.run(task, mission, self._memory),
                    label=f"agent.{name}",
                )
            except Exception as exc:
                logger.error("Agent %s başarısız (tüm retry'lar): %s", name, exc)
                audit.log(
                    "agent_failed", agent=name, success=False,
                    detail={"error": str(exc)},
                )
                return AgentResult(
                    agent_name=name, success=False, error=str(exc),
                )

        if parallel and len(agent_names) > 1:
            coros = [_run_single_agent(name) for name in agent_names]
            results = list(await asyncio.gather(*coros, return_exceptions=False))
        else:
            for name in agent_names:
                result = await _run_single_agent(name)
                results.append(result)

        return results

    # ── Kontrol ──────────────────────────────────────────

    def stop(self) -> None:
        logger.warning("KILLSWITCH AKTİF — operasyon durduruluyor")
        audit.log("killswitch")
        self._running = False
        if self._mission:
            self._mission.status = MissionStatus.PAUSED

    def pause(self) -> None:
        self._running = False
        if self._mission:
            self._mission.status = MissionStatus.PAUSED
            self._memory.save(self._mission.id)

    def resume(self) -> None:
        if self._mission and self._mission.status == MissionStatus.PAUSED:
            self._mission.status = MissionStatus.ACTIVE
