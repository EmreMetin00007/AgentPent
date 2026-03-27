"""AgentPent — RAG Memory Tools.

Ajanların geçmiş penetrasyon testi tecrübelerini veritabanında aramasını
veya başarılı payload'larını veritabanına kaydetmesini sağlayan araçlar.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar, Dict

from core.rag_memory import RAGMemory
from tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger("agentpent.tools.rag")
rag_db = RAGMemory()


class RAGSearchTool(BaseTool):
    """Geçmiş başarılı payload veya zafiyet sömürü taktiklerini arar."""

    name: ClassVar[str] = "rag_search"
    description: ClassVar[str] = (
        "Geçmiş operasyonlarda kaydedilmiş başarılı pentest tecrübelerini, "
        "zafiyet payload'larını veya taktikleri anlamsal (vektörel) olarak arar. "
        "Parametre: query (ör: 'SQLi login bypass', 'SSRF AWS metadata')"
    )

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        query = params.get("query", "")
        if not query:
            return ToolResult(tool_name=self.name, success=False, error="query parametresi gerekli.")

        logger.info("[RAGSearchTool] Aranıyor: %s", query)
        results = await rag_db.search(query, top_k=3)

        if not results:
            return ToolResult(
                tool_name=self.name,
                command=f"search: {query}",
                success=True,
                stdout="Geçmiş kayıtlarda bu konuyla eşleşen bir tecrübe/payload bulunamadı."
            )

        output_lines = [f"RAG Arama Sonuçları ('{query}'):"]
        for i, res in enumerate(results, 1):
            score_acc = int(res.get("score", 0) * 100)
            output_lines.append(f"\n[{i}] Eşleşme (%{score_acc})")
            output_lines.append(f"Konu: {res.get('topic')}")
            output_lines.append(f"Bağlam: {res.get('context')}")
            output_lines.append(f"Payload/Komut: {res.get('payload')}")

        out_str = "\n".join(output_lines)
        return ToolResult(
            tool_name=self.name,
            command=f"search: {query}",
            success=True,
            stdout=out_str,
            parsed_data={"results": results}
        )

    def parse_output(self, raw: str) -> Dict[str, Any]:
        return {"rag_output": raw}


class RAGStoreTool(BaseTool):
    """Başarılı olan bir saldırı vektörünü hafızaya ekler."""

    name: ClassVar[str] = "rag_store"
    description: ClassVar[str] = (
        "Başarılı olan, işe yarayan bir zafiyet sömürüsünü, komutu veya payload'ı "
        "gelecekteki görevler ve diğer ajanlar için hafızaya kaydeder. "
        "Parametreler: topic (Konu/Zafiyet adı), payload (İşe yarayan kod/payload), "
        "context (Opsiyonel: Hangi şartlarda çalıştı?)"
    )

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        topic = params.get("topic", "")
        payload = params.get("payload", "")
        context = params.get("context", "")

        if not topic or not payload:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="topic ve payload parametreleri gereklidir."
            )

        logger.info("[RAGStoreTool] Kaydediliyor: %s", topic)
        success = await rag_db.add_experience(topic, payload, context)

        if success:
            return ToolResult(
                tool_name=self.name,
                command=f"store: {topic}",
                success=True,
                stdout=f"BAŞARILI: '{topic}' tecrübesi hafızaya kaydedildi. Gelecekte 'rag_search' ile bulunabilir."
            )
        else:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="Veritabanına veya Embedding API'ye bağlanırken hata oluştu (OpenAI key kontrol et)."
            )

    def parse_output(self, raw: str) -> Dict[str, Any]:
        return {"rag_output": raw}
