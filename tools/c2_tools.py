"""AgentPent — Reverse Shell / C2 Handler Tools.

Ajanların hedefte dinleyici açmasını (listener),
bağlanan tersine bağlantıları (reverse shell) listelemesini
ve aktif oturumlara asenkron komut göndermesini sağlar.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar, Dict

from core.c2_server import c2_manager
from tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger("agentpent.tools.c2")


class C2StartListenerTool(BaseTool):
    """Hedef makineden gelecek bağlantılar için arka planda port dinler."""

    name: ClassVar[str] = "c2_start_listener"
    description: ClassVar[str] = (
        "Reverse Shell yakalamak için AgentPent platformunun kendi içinde "
        "asenkron bir TCP Listener (Dinleyici) başlatır. "
        "Parametre: port (int) — Dinlenecek port (Ör: 4444)."
    )

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        port = params.get("port")
        if not port or not isinstance(port, int):
            try:
                port = int(str(port))
            except ValueError:
                return ToolResult(tool_name=self.name, success=False, error="Geçerli bir tamsayı 'port' parametresi gerekli.")

        logger.info("[C2ListenerTool] İstendi: port %d", port)
        success = await c2_manager.start_listener(port)

        if success:
            return ToolResult(
                tool_name=self.name,
                command=f"listen: {port}",
                success=True,
                stdout=f"BAŞARILI: 0.0.0.0:{port} portunda Reverse Shell dinleyicisi başlatıldı. Bağlantıları görmek için 'c2_list_sessions' kullanın."
            )
        else:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Port {port} dinlenemedi (Başka bir araç tarafından kullanılıyor olabilir)."
            )

    def parse_output(self, raw: str) -> Dict[str, Any]:
        return {"c2_output": raw}


class C2ListSessionsTool(BaseTool):
    """Mevcut Reverse Shell oturumlarını (session) listeler."""

    name: ClassVar[str] = "c2_list_sessions"
    description: ClassVar[str] = (
        "Bağlanmış ve aktif olan Reverse Shell veya C2 oturumlarının listesini "
        "döndürür. Buradan session_id öğrenilerek komut gönderilebilir. "
        "Parametre yok."
    )

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        sessions = c2_manager.list_sessions()

        if not sessions:
            return ToolResult(
                tool_name=self.name,
                success=True,
                stdout="Aktif bir oturum (session) bulunamadı. Bağlantı bekleyen shell'ler varsa henüz ulaşmadı."
            )

        output_lines = [f"Aktif C2 Oturumları ({len(sessions)}):"]
        for s in sessions:
            output_lines.append(f"- Session ID: {s['session_id']} | Kaynak: {s['host']} | Zaman: {s['connected_at']}")

        out_str = "\n".join(output_lines)
        return ToolResult(
            tool_name=self.name,
            success=True,
            stdout=out_str,
            parsed_data={"sessions": sessions}
        )

    def parse_output(self, raw: str) -> Dict[str, Any]:
        return {"c2_output": raw}


class C2InteractTool(BaseTool):
    """Bir Reverse Shell session'ı içerisine interaktif komut yollar."""

    name: ClassVar[str] = "c2_interact"
    description: ClassVar[str] = (
        "Belirli bir Reverse Shell oturumunun 'içerisine' komut yollar ve "
        "çıktısını okur (Post-Exploitation veya yanal hareket için). "
        "Parametreler: session_id (Oturum ID), command (Çalıştırılacak bash/cmd komutu)"
    )

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        session_id = params.get("session_id", "")
        command = params.get("command", "")

        if not session_id or not command:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="session_id ve command parametreleri gereklidir."
            )

        session = c2_manager.get_session(session_id)
        if not session:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"ERROR: Session ID '{session_id}' geçersiz veya bağlantı koptu. (Örn id: 6b3c4f2)"
            )

        logger.info("[C2InteractTool] %s oturumuna komut: %s", session_id, command)
        
        # Timeout'lu komut koşumu
        result_text = await session.execute(command, timeout=30.0)

        return ToolResult(
            tool_name=self.name,
            command=f"interact {session_id}: {command}",
            success=True,
            stdout=result_text
        )

    def parse_output(self, raw: str) -> Dict[str, Any]:
        return {"c2_output": raw}
