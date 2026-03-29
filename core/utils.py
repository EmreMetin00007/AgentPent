"""AgentPent — Shared Utilities.

Ortak yardımcı fonksiyonlar. Duplicate kodun tek noktada toplanması.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger("agentpent.utils")


def extract_json_from_llm(text: str) -> Optional[Dict[str, Any]]:
    """LLM yanıtından JSON bloğunu güvenli şekilde çıkarır.

    Desteklenen formatlar:
    - ```json ... ```
    - ``` ... ```
    - Doğrudan JSON metin
    - JSON'un yanında açıklama metni (ilk { ... son } arası)
    """
    if not text or not text.strip():
        return None

    # 1. ```json ... ``` blokları
    json_blocks = re.findall(r"```json\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if json_blocks:
        for block in json_blocks:
            try:
                return json.loads(block.strip())
            except json.JSONDecodeError:
                continue

    # 2. ``` ... ``` blokları
    code_blocks = re.findall(r"```\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if code_blocks:
        for block in code_blocks:
            try:
                return json.loads(block.strip())
            except json.JSONDecodeError:
                continue

    # 3. Doğrudan JSON
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # 4. İlk { ile son } arasını bul
    first_brace = stripped.find("{")
    last_brace = stripped.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        candidate = stripped[first_brace : last_brace + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    logger.debug("JSON parse edilemedi — ham metin (ilk 200): %s", text[:200])
    return None


def truncate_output(text: str, max_chars: int = 3000) -> str:
    """Uzun araç çıktılarını LLM context'e sığacak şekilde keser."""
    if not text or len(text) <= max_chars:
        return text
    half = max_chars // 2
    return (
        text[:half]
        + f"\n\n... [{len(text) - max_chars} karakter kesildi] ...\n\n"
        + text[-half:]
    )


def sanitize_target(target: str) -> str:
    """Hedef string'ini normalize eder."""
    target = target.strip().lower()
    # Protokol varsa kaldır (scope check için)
    for prefix in ("http://", "https://", "ftp://"):
        if target.startswith(prefix):
            target = target[len(prefix) :]
    # Trailing slash kaldır
    target = target.rstrip("/")
    # Port ayır
    if ":" in target and not target.startswith("["):
        parts = target.rsplit(":", 1)
        if parts[1].isdigit():
            target = parts[0]
    return target



# ── Tool parametre şemaları — LLM'e araç kullanımını öğretir ──
TOOL_PARAM_SCHEMAS: Dict[str, str] = {
    "nmap": "target (str, ZORUNLU), scan_type (str: quick|full|service|vuln|stealth|udp), ports (str: '80,443' veya '1-1000'), extra_flags (list[str])",
    "sqlmap": "target (str URL, ZORUNLU — ör: http://IP/page.php?id=1), method (str: GET|POST), data (str: POST body), level (int: 1-5), risk (int: 1-3), dbs (bool), dump (bool)",
    "ffuf": "target (str URL+FUZZ, ZORUNLU — ör: http://IP/FUZZ), wordlist (str, varsayılan: /usr/share/wordlists/dirb/common.txt), mode (str: dir|vhost|param), extensions (str: '.php,.html'), filter_status (str: '404'), threads (int)",
    "xsstrike": "target (str URL+parametre, ZORUNLU — ör: http://IP/page?q=test), crawl (bool), data (str: POST body)",
    "nikto": "target (str URL, ZORUNLU — ör: http://IP), port (int), ssl (bool), tuning (str)",
    "browser_vision": "target (str URL, ZORUNLU)",
    "http_repeater": "url (str, ZORUNLU), method (str: GET|POST|PUT), headers (dict), data (str: body), timeout (int)",
    "kaliterminal": "command (str, ZORUNLU — tam shell komutu)",
    "whois": "target (str IP/domain, ZORUNLU)",
    "nuclei": "target (str, ZORUNLU), templates (str), severity (str: critical,high,medium,low)",
    "graph_add_node": "id (str, ZORUNLU), type (str: host|service|vuln|credential|session)",
    "graph_add_edge": "source (str, ZORUNLU), target (str, ZORUNLU), relation (str)",
    "graph_view": "(parametre gerekmez)",
    "rag_search": "query (str, ZORUNLU)",
    "rag_store": "key (str, ZORUNLU), value (str, ZORUNLU)",
    "linpeas": "target (str, ZORUNLU)",
    "metasploit": "target (str, ZORUNLU), module (str), payload (str), options (dict)",
    "exploit_builder": "target (str, ZORUNLU), vuln_id (str), exploit_type (str)",
}


def build_tool_definitions(tools: Dict[str, Any]) -> str:
    """Agent'ın kayıtlı araçlarından LLM için tool definition metni üretir."""
    if not tools:
        return ""

    lines = ["## Kullanılabilir Araçlar\n"]
    lines.append("Aşağıdaki araçları çağırabilirsin. Bir aracı çağırmak için yanıtına şu JSON formatını ekle:\n")
    lines.append('```json')
    lines.append('{')
    lines.append('  "tool_calls": [')
    lines.append('    {"tool": "araç_adı", "params": {"param1": "değer1"}}')
    lines.append('  ]')
    lines.append('}')
    lines.append('```\n')
    lines.append("İşin bittiğinde araç çağrısı yapmadan son yanıtını ver.\n")

    for name, tool in tools.items():
        desc = getattr(tool, "description", "")
        param_schema = TOOL_PARAM_SCHEMAS.get(name, "")
        if param_schema:
            lines.append(f"- **{name}**: {desc}\n  Parametreler: {param_schema}")
        else:
            lines.append(f"- **{name}**: {desc}")

    return "\n".join(lines)

