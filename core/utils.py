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
        lines.append(f"- **{name}**: {desc}")

    return "\n".join(lines)
