"""AgentPent — Web Proxy / Intercept Modülü.

Ajanların kendi gönderdiği veya dış araçların gönderdiği (sqlmap vb.) 
HTTP/HTTPS trafiğini dinlemek, loglamak ve manipüle etmek (Burp Repeater benzeri)
için basit Python tabanlı proxy (TCP Relay).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional
import uuid

logger = logging.getLogger("agentpent.proxy_server")

class Flow:
    """Bir HTTP request ve response çifti."""
    def __init__(self, method: str, url: str, headers: str, body: bytes):
        self.id = str(uuid.uuid4())[:8]
        self.method = method
        self.url = url
        self.request_headers = headers
        self.request_body = body
        self.response_headers = ""
        self.response_body = b""
        self.status_code = 0

class ProxyServer:
    """Minimal Asynchronous HTTP Intercept Proxy."""

    def __init__(self):
        self.flows: Dict[str, Flow] = {}
        self.server: Optional[asyncio.AbstractServer] = None
        self.port: int = 8080

    async def handle_client(self, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter):
        """Web araçlarından gelen istekleri dinle ve hedef sunucuya ilet."""
        # Not: HTTPS bağlantıları için (CONNECT) sertifika gerekir. SSL Bumping olmadan sadece TCP proxy yapılır.
        # Bu basitleştirilmiş örnek HTTP proxy ve HTTP Repeater görevini üstlenir.
        try:
            request_line = await client_reader.readline()
            if not request_line:
                client_writer.close()
                return

            req_str = request_line.decode('utf-8', errors='ignore').strip()
            # Örn: GET http://example.com/ HTTP/1.1
            parts = req_str.split(' ')
            if len(parts) >= 2:
                method = parts[0]
                url = parts[1]
            else:
                method = "UNKNOWN"
                url = "UNKNOWN"

            if method == "CONNECT":
                # HTTPS tünelleme
                host_port = url.split(':')
                host = host_port[0]
                port = int(host_port[1]) if len(host_port) > 1 else 443

                try:
                    server_reader, server_writer = await asyncio.open_connection(host, port)
                    client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                    await client_writer.drain()

                    # Şifreli trafiği (SSL Bumping olmadan) göremiyoruz, sadece aktarıyoruz.
                    await asyncio.gather(
                        self._relay(client_reader, server_writer),
                        self._relay(server_reader, client_writer)
                    )
                except Exception as e:
                    logger.debug(f"[Proxy] CONNECT hatası ({url}): {e}")
                    client_writer.close()
                return

            # Normal HTTP Intercept
            headers = b""
            while True:
                line = await client_reader.readline()
                if line == b"\r\n" or not line:
                    break
                headers += line

            # Body okumak interceptor'da zordur çünkü Content-Length lazım, burada minimal pass yapıyoruz.
            # Raporlama için kaydet
            flow = Flow(method, url, headers.decode('utf-8', errors='ignore'), b"")
            self.flows[flow.id] = flow

            # HTTP Parse edip hedefi bulmak gerekiyor ama proxy olarak bu dosya temsilidir, 
            # gerçekte aiohttp.web veya httpx tabanlı bir Repeater sınıfı yazmak Agent için daha mantıklıdır.
            client_writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\nProxy is just a minimal relay.")
            await client_writer.drain()
            client_writer.close()

        except Exception as exc:
            logger.debug(f"[Proxy] Hata: {exc}")
            client_writer.close()

    async def _relay(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()

    async def start(self, port: int = 8080):
        if self.server:
            return True
        self.port = port
        self.server = await asyncio.start_server(self.handle_client, '127.0.0.1', port)
        asyncio.create_task(self.server.serve_forever())
        logger.info("[Proxy] Local Proxy başlatıldı: 127.0.0.1:%d", port)
        return True

    def stop(self):
        if self.server:
            self.server.close()
            self.server = None
            logger.info("[Proxy] Local Proxy kapatıldı.")
            
    def get_flows(self) -> List[Flow]:
        return list(self.flows.values())


global_proxy = ProxyServer()
