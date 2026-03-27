"""AgentPent — LLM Client.

OpenAI / Codex API ile iletişim kuran async istemci.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from openai import AsyncOpenAI

from config.settings import settings

logger = logging.getLogger("agentpent.llm")


class LLMClient:
    """OpenAI API üzerinden LLM çağrıları yapan async istemci."""

    def __init__(self):
        self._client: Optional[AsyncOpenAI] = None

    def _get_client(self) -> AsyncOpenAI:
        """Lazy init — ilk kullanımda oluştur."""
        if self._client is None:
            api_key = settings.openai_api_key
            if not api_key:
                raise RuntimeError(
                    "AGENTPENT_OPENAI_API_KEY ayarlanmamış. "
                    ".env dosyasını kontrol et veya ortam değişkenini ayarla."
                )
            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=settings.openai_base_url,
            )
        return self._client

    # ── Chat Completion ──────────────────────────────────

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        response_format: Optional[dict] = None,
        images: Optional[list[str]] = None,
    ) -> str:
        """Tek bir chat completion çağrısı yapar, text yanıtı döner."""

        model = model or settings.default_model
        temperature = temperature if temperature is not None else settings.temperature
        max_tokens = max_tokens or settings.max_tokens

        full_messages: list[dict[str, Any]] = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
            
        for msg in messages:
            if images and msg == messages[-1] and msg["role"] == "user":
                content_list = [{"type": "text", "text": msg["content"]}]
                for img in images:
                    content_list.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img}"}
                    })
                full_messages.append({"role": "user", "content": content_list})
            else:
                full_messages.append(msg)

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": full_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        logger.debug("LLM çağrısı → model=%s, mesaj=%d", model, len(full_messages))

        response = await self._get_client().chat.completions.create(**kwargs)
        content = response.choices[0].message.content or ""
        logger.debug("LLM yanıtı ← %d karakter", len(content))
        return content

    # ── Structured Output ────────────────────────────────

    async def chat_json(
        self,
        messages: list[dict[str, Any]],
        *,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        images: Optional[list[str]] = None,
    ) -> dict:
        """JSON formatında yanıt döndüren chat çağrısı."""

        raw = await self.chat(
            messages,
            model=model,
            system_prompt=system_prompt,
            response_format={"type": "json_object"},
            images=images,
        )
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.error("JSON parse hatası — raw: %s", raw[:500])
            return {"error": "JSON parse failed", "raw": raw}

    # ── Agent Call ────────────────────────────────────────

    async def agent_call(
        self,
        agent_system_prompt: str,
        task: str,
        context: str = "",
        *,
        model: Optional[str] = None,
        images: Optional[list[str]] = None,
    ) -> str:
        """Bir agent'ı çağırır: system prompt + görev + bağlam."""

        messages: list[dict[str, Any]] = []
        if context:
            messages.append({"role": "user", "content": f"## Bağlam\n\n{context}"})
        messages.append({"role": "user", "content": f"## Görev\n\n{task}"})

        return await self.chat(
            messages,
            model=model,
            system_prompt=agent_system_prompt,
            images=images,
        )

    async def agent_call_json(
        self,
        agent_system_prompt: str,
        task: str,
        context: str = "",
        *,
        model: Optional[str] = None,
        images: Optional[list[str]] = None,
    ) -> dict:
        """Agent'ı çağırır ve JSON formatında yanıt alır."""

        messages: list[dict[str, Any]] = []
        if context:
            messages.append({"role": "user", "content": f"## Bağlam\n\n{context}"})
        messages.append({"role": "user", "content": f"## Görev\n\n{task}"})

        return await self.chat_json(
            messages,
            model=model,
            system_prompt=agent_system_prompt,
            images=images,
        )


# Singleton
llm = LLMClient()
