"""AgentPent — Orchestrator.

Ana iş akışı motoru. Commander agent'ı kullanarak
tüm pentest operasyonunu yönetir.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional

from agents.base_agent import AgentResult, BaseAgent
from agents.commander.agent import CommanderAgent
from core.memory import ConversationMemory
from core.mission import AttackPhase, Mission, MissionStatus
from core.scope_guard import scope_guard
from config.settings import settings

logger = logging.getLogger("agentpent.orchestrator")


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
        logger.info("=" * 60)
        logger.info("OPERASYON BAŞLATILDI: %s", mission.name)
        logger.info("=" * 60)

        try:
            while self._running and mission.status == MissionStatus.ACTIVE:
                phase = mission.current_phase
                logger.info("-" * 40)
                logger.info("FAZ: %s", phase.value.upper())
                logger.info("-" * 40)

                decision = await self.commander.decide_next(mission, self._memory)
                logger.info("Commander kararı: %s", decision.get("decision"))

                # ── 🛡️ Multi-Agent Debate Loop (Jüri) ────────────────
                import json
                critic = self.get_agent("critic")
                thinker = self.get_agent("thinker")
                # Sadece spesifik işler atanırken tartış
                if decision.get("tasks") and decision.get("decision") in ("specific_agent", "next_phase", ""):
                    for _ in range(2):
                        vetoed = False
                        
                        # 1. 🧠 Thinker (Mantık / Derin Düşünce) Kontrolü
                        if thinker:
                            prompt_t = f"Commander planı: {json.dumps(decision, ensure_ascii=False)}\nDerinlemesine düşün (Reasoning) ve potansiyel riskleri/mantık hatalarını incele."
                            t_res = await thinker.run(prompt_t, mission, self._memory)
                            try:
                                t_data = json.loads(t_res.raw_response)
                                if not t_data.get("approved", True):
                                    reason = t_data.get("reason", "Bilinmeyen itiraz.")
                                    logger.warning("🧠 Thinker Veto Etti: %s", reason)
                                    self._memory.add_system(f"🚨 THINKER REDDETTİ: {reason}. Lütfen planı buna göre güncelle.")
                                    decision = await self.commander.decide_next(mission, self._memory)
                                    vetoed = True
                                else:
                                    logger.info("🧠 Thinker ONAYLADI: %s", t_data.get("reason", "Sorun yok."))
                            except Exception as e:
                                logger.debug("Thinker parse hatası: %s", e)

                        # 2. 🛡️ Critic (OPSEC / Halisülasyon) Kontrolü
                        if not vetoed and critic:
                            prompt_c = f"İncele (OPSEC/Halisülasyon/Mantık):\n{json.dumps(decision, ensure_ascii=False)}"
                            critic_res = await critic.run(prompt_c, mission, self._memory)
                            try:
                                c_data = json.loads(critic_res.raw_response)
                                if not c_data.get("approved", True):
                                    reason = c_data.get("reason", "Bilinmeyen itiraz.")
                                    logger.warning("🛡️ Critic Veto Etti: %s", reason)
                                    self._memory.add_system(f"🚨 CRITIC REDDETTİ: {reason}. Lütfen planı buna göre güncelle/düzelt.")
                                    decision = await self.commander.decide_next(mission, self._memory)
                                    vetoed = True
                                else:
                                    logger.info("🛡️ Critic ONAYLADI: %s", c_data.get("reason", "Sorun yok."))
                            except Exception as e:
                                logger.debug("Critic parse hatası: %s", e)

                        # Eğer kimse veto etmediyse döngüyü kır, işleme başla
                        if not vetoed:
                            logger.info("⚖️ Komite (Critic & Thinker) Konsensüsü Sağlandı. İşleme geçiliyor...")
                            break
                # ── 🛡️ ────────────────────────────────────────────────

                action = decision.get("decision", "next_phase")

                if action == "abort":
                    logger.warning("Commander: ABORT kararı")
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
                    next_phase = mission.advance_phase()
                    if next_phase is None:
                        logger.info("Tüm fazlar tamamlandı!")
                        break
                    logger.info("Sonraki faz: %s", next_phase.value)

                if decision.get("notes"):
                    mission.commander_notes = decision["notes"]

        except Exception as exc:
            logger.error("Operasyon hatası: %s", exc, exc_info=True)
            mission.status = MissionStatus.ABORTED

        finally:
            self._running = False
            self._memory.save(mission.id)

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

        if parallel and len(agent_names) > 1:
            coros = []
            for name in agent_names:
                agent = self._agents.get(name)
                if not agent:
                    logger.warning("Agent bulunamadı: %s (atlanıyor)", name)
                    continue
                task = task_map.get(
                    name,
                    "{} fazını çalıştır: {}".format(name, ", ".join(mission.target_scope)),
                )
                coros.append(agent.run(task, mission, self._memory))
            if coros:
                results = await asyncio.gather(*coros, return_exceptions=False)
        else:
            for name in agent_names:
                agent = self._agents.get(name)
                if not agent:
                    logger.warning("Agent bulunamadı: %s (atlanıyor)", name)
                    continue
                task = task_map.get(
                    name,
                    "{} fazını çalıştır: {}".format(name, ", ".join(mission.target_scope)),
                )
                result = await agent.run(task, mission, self._memory)
                results.append(result)

        return results

    # ── Kontrol ──────────────────────────────────────────

    def stop(self) -> None:
        logger.warning("KILLSWITCH AKTİF — operasyon durduruluyor")
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
