"""AgentPent — LLM Client.

OpenAI / OpenRouter API ile iletişim kuran async istemci.
Production features: retry, timeout, error handling.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, List, Optional

from openai import AsyncOpenAI

from config.settings import settings

logger = logging.getLogger("agentpent.llm")

_DEFAULT_RETRIES = 3
_BACKOFF_BASE = 2.0  # seconds

# ── Refusal Detection Patterns ───────────────────────────
_REFUSAL_PATTERNS = [
    re.compile(r"I\s+can'?t\s+(assist|help|provide|generate|create|write)", re.I),
    re.compile(r"I'?m\s+(unable|not able)\s+to", re.I),
    re.compile(r"I\s+cannot\s+(assist|help|provide|generate|create|fulfill)", re.I),
    re.compile(r"(as\s+an\s+AI|as\s+a\s+language\s+model)", re.I),
    re.compile(r"(against\s+my|violat(e|es|ing)\s+(my|the))\s+(guidelines|policies|ethical|safety)", re.I),
    re.compile(r"(harmful|malicious|illegal|unethical)\s+(activities|purposes|intent|use)", re.I),
    re.compile(r"I\s+must\s+(decline|refuse|warn)", re.I),
    re.compile(r"(could\s+be\s+used\s+(for|to)\s+(harm|attack|exploit))", re.I),
    re.compile(r"bu\s+(bir|tür)\s+(siber\s+)?saldırı", re.I),
    re.compile(r"(etik|ahlaki)\s+(kural|kısıtlama|ihlal)", re.I),
    re.compile(r"(gerçekleştiremem|sağlayamam|üretemem)", re.I),
    re.compile(r"güvenlik\s+(politika|kısıtlama)", re.I),
]


class LLMClient:
    """OpenAI API üzerinden LLM çağrıları yapan async istemci."""

    def __init__(self):
        self._client: Optional[AsyncOpenAI] = None
        self._refusal_count = 0
        self._fallback_count = 0

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
                timeout=60.0,
                max_retries=0,  # Kendi retry mekanizmamızı kullanacağız
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
        """Tek bir chat completion çağrısı yapar, text yanıtı döner.

        Retry: 3 deneme, exponential backoff.
        Rate limit (429) ve server error (500+) durumlarında otomatik retry.
        """

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
                        "image_url": {"url": "data:image/png;base64,{}".format(img)}
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

        # Retry loop
        last_exc = None
        for attempt in range(1, _DEFAULT_RETRIES + 1):
            try:
                logger.debug(
                    "LLM çağrısı → model=%s, mesaj=%d (deneme %d)",
                    model, len(full_messages), attempt,
                )

                response = await asyncio.wait_for(
                    self._get_client().chat.completions.create(**kwargs),
                    timeout=120.0,
                )
                content = response.choices[0].message.content or ""
                logger.debug("LLM yanıtı ← %d karakter", len(content))
                return content

            except asyncio.TimeoutError:
                last_exc = TimeoutError("LLM isteği zaman aşımına uğradı (120s)")
                logger.warning(
                    "[LLM] Timeout (deneme %d/%d)", attempt, _DEFAULT_RETRIES
                )
            except Exception as exc:
                last_exc = exc
                exc_str = str(exc).lower()

                # Rate limit veya server error → retry
                is_retryable = any(
                    kw in exc_str
                    for kw in ("429", "rate_limit", "rate limit", "500", "502", "503", "529", "overloaded")
                )

                if is_retryable and attempt < _DEFAULT_RETRIES:
                    wait = _BACKOFF_BASE ** attempt
                    logger.warning(
                        "[LLM] Retryable hata (deneme %d/%d): %s — %.1fs bekle",
                        attempt, _DEFAULT_RETRIES, str(exc)[:100], wait,
                    )
                    await asyncio.sleep(wait)
                elif not is_retryable:
                    # Non-retryable hata → hemen fırlat
                    raise

            if attempt < _DEFAULT_RETRIES:
                wait = _BACKOFF_BASE ** attempt
                await asyncio.sleep(wait)

        raise last_exc or RuntimeError("LLM çağrısı başarısız — tüm denemeler tükendi")

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
            messages.append({"role": "user", "content": "## Bağlam\n\n{}".format(context)})
        messages.append({"role": "user", "content": "## Görev\n\n{}".format(task)})

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
            messages.append({"role": "user", "content": "## Bağlam\n\n{}".format(context)})
        messages.append({"role": "user", "content": "## Görev\n\n{}".format(task)})

        return await self.chat_json(
            messages,
            model=model,
            system_prompt=agent_system_prompt,
            images=images,
        )

    # ── Refusal Detection ─────────────────────────────────

    @staticmethod
    def detect_refusal(text: str) -> bool:
        """LLM yanıtında refusal (red) pattern'i tespit et."""
        if not text or len(text) < 20:
            return False
        # İlk 500 karakterde refusal pattern ara
        check_text = text[:500]
        for pattern in _REFUSAL_PATTERNS:
            if pattern.search(check_text):
                return True
        return False

    # ── Fallback Chain ────────────────────────────────────

    async def chat_with_fallback(
        self,
        messages: list[dict[str, Any]],
        *,
        primary_model: Optional[str] = None,
        fallback_models: Optional[List[str]] = None,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[dict] = None,
        images: Optional[list[str]] = None,
    ) -> str:
        """Fallback chain ile chat çağrısı.

        Primary model reddederse sırayla fallback modelleri dener.
        """
        model = primary_model or settings.default_model
        models_to_try = [model]

        if settings.enable_fallback_chain and fallback_models:
            models_to_try.extend(fallback_models)

        last_response = ""
        for i, try_model in enumerate(models_to_try):
            try:
                response = await self.chat(
                    messages,
                    model=try_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system_prompt=system_prompt,
                    response_format=response_format,
                    images=images,
                )
                last_response = response

                if self.detect_refusal(response):
                    self._refusal_count += 1
                    if i < len(models_to_try) - 1:
                        self._fallback_count += 1
                        logger.warning(
                            "[LLM] Refusal tespit edildi (model=%s). "
                            "Fallback modele geçiliyor: %s",
                            try_model, models_to_try[i + 1],
                        )
                        continue
                    else:
                        logger.warning(
                            "[LLM] Tüm modeller reddetti. Son yanıt döndürülüyor."
                        )
                        return response

                # Refusal yok → başarılı
                if i > 0:
                    logger.info(
                        "[LLM] Fallback başarılı: %s (deneme %d/%d)",
                        try_model, i + 1, len(models_to_try),
                    )
                return response

            except Exception as exc:
                logger.error(
                    "[LLM] Fallback model hatası: %s — %s", try_model, exc
                )
                if i == len(models_to_try) - 1:
                    raise
                continue

        return last_response

    @property
    def refusal_metrics(self) -> dict:
        return {
            "total_refusals": self._refusal_count,
            "fallback_attempts": self._fallback_count,
        }


# Singleton
llm = LLMClient()
