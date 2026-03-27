"""AgentPent — Web Proxy / HTTP Repeater Modülü.

Ajanların (özellikle WebApp ajanının) doğrudan raw HTTP isteklerini
Burp Suite Repeater mantığıyla göndermesini, header/cookie ve payloadları
manipüle edip tam yanıtı (Header + Body) okumasını sağlar.
"""

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
from typing import Any, ClassVar, Dict

from tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger("agentpent.tools.http_repeater")


class HttpRepeaterTool(BaseTool):
    """Burp Suite Repeater benzeri HTTP Request / Intercept aracı."""

    name: ClassVar[str] = "http_repeater"
    description: ClassVar[str] = (
        "Hedef web sunucularına doğrudan (raw) HTTP istekleri göndermek ve başlıkları/gövdeleri "
        "(headers/body) manipüle etmek için kullanılır (Burp Repeater gibi). "
        "Parametreler: url, method (GET, POST vb.), headers (JSON string veya dict), "
        "data (Gönderilecek raw payload/body), timeout (int, varsayılan 10)"
    )

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        url = params.get("url")
        if not url:
            return ToolResult(tool_name=self.name, success=False, error="url parametresi gerekli.")

        method = params.get("method", "GET").upper()
        data = params.get("data", "")
        headers = params.get("headers", {})
        timeout = int(params.get("timeout", 10))

        # Eğer headers JSON string geldiyse dict'e çevir
        if isinstance(headers, str):
            try:
                headers = json.loads(headers)
            except Exception:
                pass # dict değilse boşver veya string bırakırsan hata verir, biz sadece dict geçmeli diyoruz
                headers = {}

        if not isinstance(headers, dict):
            headers = {}

        # Sadece urllib kullanacağız ki agent hızlıca request atsın
        req_data = data.encode('utf-8') if data else None
        
        try:
            req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
            
            logger.info("[HttpRepeater] İletiliyor: %s %s", method, url)
            
            # Request'i fırlat
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status = response.status
                resp_headers = dict(response.headers)
                body = response.read().decode('utf-8', errors='replace')
        except urllib.error.HTTPError as e:
            # 404, 500 gb hatalar pentest için hatalı sayılmaz, başarılı bir yanıt dönmüştür.
            status = e.code
            resp_headers = dict(e.headers)
            body = e.read().decode('utf-8', errors='replace')
        except Exception as e:
            return ToolResult(tool_name=self.name, success=False, error=f"HTTP Request Başarısız: {e}")

        # Çıktıyı formatla
        output_lines = [
            f"HTTP/1.1 {status}",
        ]
        for k, v in resp_headers.items():
            output_lines.append(f"{k}: {v}")
        
        output_lines.append("") # Boş satır header ve body arasına
        output_lines.append(body if len(body) < 15000 else body[:15000] + "\n...[TRUNCATED_BODY]")

        out_str = "\n".join(output_lines)
        return ToolResult(
            tool_name=self.name,
            command=f"{method} {url}",
            success=True,
            stdout=out_str,
            parsed_data={"status": status, "headers": resp_headers, "body_length": len(body)}
        )

    def parse_output(self, raw: str) -> Dict[str, Any]:
        return {"repeater_output": raw}
