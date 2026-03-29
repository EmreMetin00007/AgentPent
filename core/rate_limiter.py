"""AgentPent — Rate Limiter & Concurrency Control.

Target bazlı token bucket rate limiter ve eşzamanlılık kontrolü.
IDS/IPS tetiklememek için jitter (rastgele gecikme) desteği.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Dict, Optional

from config.settings import settings

logger = logging.getLogger("agentpent.rate_limiter")


class TokenBucket:
    """Token bucket rate limiter — belirli bir hedefe yönelik istek hızını sınırlar."""

    def __init__(self, rate: float, jitter_min: float = 0.0, jitter_max: float = 0.0):
        self.rate = rate  # token/saniye
        self.max_tokens = rate  # bucket kapasitesi
        self._tokens = rate
        self._last_refill = time.monotonic()
        self._jitter_min = jitter_min
        self._jitter_max = jitter_max
        self._lock = asyncio.Lock()

    async def acquire(self) -> float:
        """Bir token tüket. Gerekirse bekle. Beklenen süreyi (saniye) döner."""
        waited = 0.0
        async with self._lock:
            self._refill()

            if self._tokens < 1.0:
                wait_time = (1.0 - self._tokens) / self.rate
                # Jitter ekle
                if self._jitter_max > 0:
                    jitter = random.uniform(self._jitter_min, self._jitter_max)
                    wait_time += jitter
                waited = wait_time
                await asyncio.sleep(wait_time)
                self._refill()

            self._tokens -= 1.0

        return waited

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.max_tokens, self._tokens + elapsed * self.rate)
        self._last_refill = now


class RateLimiter:
    """Merkezi rate limiter — target bazlı throttling ve eşzamanlılık kontrolü."""

    def __init__(
        self,
        max_concurrent: Optional[int] = None,
        rate_per_second: Optional[float] = None,
        jitter_min: float = 0.0,
        jitter_max: float = 0.5,
    ):
        self._max_concurrent = max_concurrent or settings.max_concurrent_tools
        self._rate = rate_per_second or settings.rate_limit_rps
        self._jitter_min = jitter_min
        self._jitter_max = jitter_max

        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._target_buckets: Dict[str, TokenBucket] = {}

        # Metrikler
        self._total_calls = 0
        self._total_wait_time = 0.0
        self._throttled_calls = 0

    def _get_bucket(self, target: str) -> TokenBucket:
        """Target için token bucket döner (lazy init)."""
        if target not in self._target_buckets:
            self._target_buckets[target] = TokenBucket(
                rate=self._rate,
                jitter_min=self._jitter_min,
                jitter_max=self._jitter_max,
            )
        return self._target_buckets[target]

    async def acquire(self, target: str = "global") -> float:
        """Semaphore + token bucket üzerinden slot al. Toplam bekleme süresini döner."""
        self._total_calls += 1

        # 1. Semaphore — eşzamanlılık limiti
        await self._semaphore.acquire()

        # 2. Token bucket — target bazlı hız limiti
        bucket = self._get_bucket(target)
        waited = await bucket.acquire()

        if waited > 0:
            self._throttled_calls += 1
            self._total_wait_time += waited
            logger.debug(
                "[RateLimiter] Throttled: target=%s, wait=%.2fs", target, waited
            )

        return waited

    def release(self) -> None:
        """Semaphore slot'unu serbest bırak."""
        self._semaphore.release()

    @property
    def metrics(self) -> Dict[str, float]:
        return {
            "total_calls": self._total_calls,
            "throttled_calls": self._throttled_calls,
            "total_wait_seconds": round(self._total_wait_time, 2),
            "avg_wait_seconds": round(
                self._total_wait_time / max(self._throttled_calls, 1), 3
            ),
        }


# Singleton
rate_limiter = RateLimiter()
