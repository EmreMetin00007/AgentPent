"""AgentPent — Base Agent.

Tüm özelleşmiş agent'ların miras aldığı taban sınıf.
ReAct (Reason + Act) loop ile araçları otonom çağırabilir.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.llm_client import llm
from core.memory import ConversationMemory
from core.mission import AttackPhase, Finding, Mission
from core.utils import build_tool_definitions, extract_json_from_llm, truncate_output
from core.audit import audit
from core.prompt_engine import (
    OFFENSIVE_AGENTS,
    build_system_prompt,
    get_fallback_chain,
    get_model_for_agent,
)
from config.settings import settings

logger = logging.getLogger("agentpent.agent")


class BaseAgent(ABC):
    """Tüm AgentPent agent'larının taban sınıfı."""

    name: str = "base"
    description: str = ""
    phase: AttackPhase = AttackPhase.RECONNAISSANCE
    model: Optional[str] = None

    def __init__(self):
        self._system_prompt: str = ""
        self._tools: Dict[str, Any] = {}
        self._load_prompt()

    # ── Prompt Yükleme ───────────────────────────────────

    def _load_prompt(self) -> None:
        """Agent'ın .md dosyasından ham talimat metnini yükle.

        Dosya formatı:
          [opsiyonel CRITICAL DIRECTIVE bloğu]
          ---
          YAML frontmatter
          ---
          Agent talimat metni  ← biz bunu alıyoruz

        CRITICAL DIRECTIVE artık prompt_engine tarafından dinamik ekleniyor.
        """
        prompt_path = Path(__file__).parent / self.name / "{}.md".format(self.name)
        if prompt_path.exists():
            raw = prompt_path.read_text(encoding="utf-8")

            # YAML frontmatter'ı bul ve sonrasını al
            # Dosya "---" ile veya başka bir şeyle başlayabilir
            parts = raw.split("---")
            if len(parts) >= 3:
                # En az 2 tane '---' var → YAML frontmatter mevcut
                # parts[0] = CRITICAL DIRECTIVE (veya boş)
                # parts[1] = YAML frontmatter
                # parts[2+] = Agent talimat metni
                self._system_prompt = "---".join(parts[2:]).strip()
            else:
                # Frontmatter yok → tüm dosyayı al
                self._system_prompt = raw.strip()

            logger.debug("Prompt yüklendi: %s (%d chars)", prompt_path, len(self._system_prompt))
        else:
            self._system_prompt = self._default_prompt()

    def _default_prompt(self) -> str:
        return "Sen {} adlı bir pentest agent'ısın. Görevin: {}".format(
            self.name, self.description
        )

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    # ── Tool Kayıt ───────────────────────────────────────

    def register_tool(self, name: str, tool: Any) -> None:
        self._tools[name] = tool

    def get_tool(self, name: str) -> Any:
        return self._tools.get(name)

    @property
    def available_tools(self) -> List[str]:
        return list(self._tools.keys())

    # ── ReAct Loop ───────────────────────────────────────

    async def run(
        self,
        task: str,
        mission: Mission,
        memory: ConversationMemory,
        context: str = "",
    ) -> AgentResult:
        """ReAct (Reason + Act) döngüsü ile görev çalıştır.

        1. LLM'e görev + tool tanımları gönderilir
        2. LLM tool_calls JSON döndürürse → araç çalıştırılır → sonuç LLM'e geri beslenir
        3. LLM tool_calls döndürmezse → son yanıt process_response'a gider
        4. max_iterations aşılırsa döngü kesilir
        """
        logger.info("[%s] Görev başlatıldı: %s", self.name, task[:100])
        memory.add_user(task, agent=self.name, phase=self.phase.value)

        full_context = self._build_context(mission, context)
        max_iter = settings.max_react_iterations
        iteration = 0
        all_tool_outputs: Dict[str, str] = {}

        # Model seçimi — offensive agent'lar uncensored model kullanır
        effective_model = get_model_for_agent(
            self.name,
            self.model or settings.default_model,
            settings.offensive_model,
        )

        # System prompt — prompt_engine ile jailbreak katmanları ekle
        enhanced_prompt = build_system_prompt(
            agent_name=self.name,
            agent_prompt=self.system_prompt,
            model=effective_model,
        )
        if self._tools:
            tool_defs = build_tool_definitions(self._tools)
            enhanced_prompt = enhanced_prompt + "\n\n" + tool_defs

        # Fallback chain hazırla
        fallback_chain = get_fallback_chain(
            settings.fallback_models, effective_model
        )

        # Konuşma mesajları — ReAct döngüsü boyunca biriktir
        messages: list[dict[str, Any]] = []
        if full_context:
            messages.append({"role": "user", "content": "## Bağlam\n\n{}".format(full_context)})
        messages.append({"role": "user", "content": "## Görev\n\n{}".format(task)})

        start_time = time.monotonic()

        while iteration < max_iter:
            iteration += 1
            logger.debug("[%s] ReAct iterasyon %d/%d", self.name, iteration, max_iter)

            # LLM çağrısı — fallback chain ile
            llm_start = time.monotonic()
            response = await llm.chat_with_fallback(
                messages,
                primary_model=effective_model,
                fallback_models=fallback_chain,
                system_prompt=enhanced_prompt,
            )
            llm_duration = (time.monotonic() - llm_start) * 1000

            # Token tahmini — izleme için (~4 char = 1 token)
            est_prompt_tokens = sum(len(m.get("content", "")) for m in messages) // 4
            est_prompt_tokens += len(enhanced_prompt) // 4

            audit.llm_call(
                agent=self.name,
                model=effective_model,
                prompt_tokens=est_prompt_tokens,
                duration_ms=llm_duration,
            )

            # Tool call kontrolü
            parsed = extract_json_from_llm(response)
            tool_calls = None
            if parsed and isinstance(parsed.get("tool_calls"), list):
                tool_calls = parsed["tool_calls"]

            if not tool_calls:
                # LLM araç çağırmadı → son yanıt
                logger.debug("[%s] ReAct tamamlandı (iterasyon %d) — son yanıt", self.name, iteration)
                break

            # Tool call'ları çalıştır
            messages.append({"role": "assistant", "content": response})

            tool_results_text = []
            for tc in tool_calls:
                tool_name = tc.get("tool", "")
                params = tc.get("params", {})

                tool = self._tools.get(tool_name)
                if not tool:
                    result_text = f"[HATA] Araç bulunamadı: {tool_name}"
                    logger.warning("[%s] Bilinmeyen araç: %s", self.name, tool_name)
                else:
                    try:
                        tool_start = time.monotonic()
                        result = await tool.execute(params)
                        tool_duration = (time.monotonic() - tool_start) * 1000

                        audit.tool_call(
                            tool=tool_name,
                            target=params.get("target", ""),
                            params=params,
                            result_success=result.success,
                            duration_ms=tool_duration,
                            agent=self.name,
                            phase=self.phase.value,
                        )

                        if result.success:
                            output = result.stdout or ""
                            if result.parsed_data:
                                import json
                                output += "\n\n## Parsed Data:\n" + json.dumps(
                                    result.parsed_data, indent=2, ensure_ascii=False, default=str
                                )
                            result_text = truncate_output(output)
                        else:
                            result_text = f"[HATA] {result.error or 'Bilinmeyen hata'}"

                        all_tool_outputs[f"{tool_name}_{iteration}"] = result_text[:500]

                    except Exception as exc:
                        result_text = f"[EXCEPTION] {tool_name}: {exc}"
                        logger.error("[%s] Araç hatası: %s — %s", self.name, tool_name, exc)

                tool_results_text.append(f"### {tool_name}\n{result_text}")

            # Araç sonuçlarını mesajlara ekle
            combined = "\n\n".join(tool_results_text)
            messages.append({"role": "user", "content": f"## Araç Sonuçları ({iteration})\n\n{combined}"})
            memory.add_tool_result(combined[:1000], agent=self.name, phase=self.phase.value)

        else:
            logger.warning("[%s] ReAct max iterasyon aşıldı (%d)", self.name, max_iter)

        total_duration = (time.monotonic() - start_time) * 1000

        memory.add_assistant(response, agent=self.name, phase=self.phase.value)
        result = await self.process_response(response, mission, memory)

        # Tool output'larını birleştir
        result.tool_outputs.update(all_tool_outputs)
        result.tool_outputs["_react_iterations"] = str(iteration)
        result.tool_outputs["_total_duration_ms"] = str(round(total_duration))

        logger.info(
            "[%s] Tamamlandı — %d bulgu, %d iterasyon, %.0fms",
            self.name, len(result.findings), iteration, total_duration,
        )
        return result

    def _build_context(self, mission: Mission, extra: str = "") -> str:
        """Token-optimize edilmiş mission bağlamı."""
        parts = [
            "## Mission",
            "Hedef: {} | Faz: {} | Bulgular: {}".format(
                ", ".join(mission.target_scope),
                mission.current_phase.value,
                mission.stats,
            ),
        ]
        if mission.commander_notes:
            # Sadece son 300 karakter
            notes = mission.commander_notes[-300:]
            parts.append("Commander: {}".format(notes))
        if extra:
            # Extra context'i de kısalt
            parts.append(extra[:500])
        return "\n".join(parts)

    @abstractmethod
    async def process_response(
        self,
        response: str,
        mission: Mission,
        memory: ConversationMemory,
    ) -> AgentResult:
        ...


class AgentResult:
    """Bir agent çalışmasının sonucu."""

    def __init__(
        self,
        agent_name: str,
        raw_response: str = "",
        findings: Optional[List[Finding]] = None,
        tool_outputs: Optional[Dict[str, str]] = None,
        next_actions: Optional[List[str]] = None,
        success: bool = True,
        error: Optional[str] = None,
    ):
        self.agent_name = agent_name
        self.raw_response = raw_response
        self.findings = findings or []
        self.tool_outputs = tool_outputs or {}
        self.next_actions = next_actions or []
        self.success = success
        self.error = error

    def summary(self) -> str:
        status = "✅" if self.success else "❌"
        return "{} [{}] Bulgular: {} | Araçlar: {} | Önerilen Aksiyonlar: {}".format(
            status, self.agent_name, len(self.findings),
            len(self.tool_outputs), len(self.next_actions),
        )
