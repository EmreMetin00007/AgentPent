"""AgentPent — Rate Limiter Tests."""

from __future__ import annotations

import asyncio
import time

import pytest

from core.rate_limiter import RateLimiter, TokenBucket


class TestTokenBucket:
    @pytest.mark.asyncio
    async def test_acquire_no_wait(self):
        """İlk istek bekleme gerektirmemeli."""
        bucket = TokenBucket(rate=10.0)
        waited = await bucket.acquire()
        assert waited == 0.0

    @pytest.mark.asyncio
    async def test_acquire_with_throttle(self):
        """Tüm tokenlar tüketildikten sonra bekleme olmalı."""
        bucket = TokenBucket(rate=2.0)  # saniyede 2 token
        # İlk 2 token hemen tüketilmeli
        await bucket.acquire()
        await bucket.acquire()
        # 3. istek bekleme gerektirmeli
        start = time.monotonic()
        await bucket.acquire()
        elapsed = time.monotonic() - start
        assert elapsed > 0.1  # En az biraz beklemiş olmalı

    @pytest.mark.asyncio
    async def test_jitter_applied(self):
        """Jitter parametreleri uygulanmalı."""
        bucket = TokenBucket(rate=1.0, jitter_min=0.05, jitter_max=0.1)
        # Token tüket
        await bucket.acquire()
        # Bir sonraki istek jitter + throttle ile beklemeli
        start = time.monotonic()
        await bucket.acquire()
        elapsed = time.monotonic() - start
        assert elapsed > 0.05  # Jitter minimum


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_metrics_tracking(self):
        """Metrikler doğru izlenmeli."""
        limiter = RateLimiter(max_concurrent=5, rate_per_second=100.0)
        await limiter.acquire("target1")
        limiter.release()
        metrics = limiter.metrics
        assert metrics["total_calls"] == 1

    @pytest.mark.asyncio
    async def test_concurrent_limit(self):
        """Eşzamanlılık limiti aşılmamalı."""
        limiter = RateLimiter(max_concurrent=2, rate_per_second=100.0)

        active = 0
        max_active = 0

        async def worker(target: str):
            nonlocal active, max_active
            await limiter.acquire(target)
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.05)
            active -= 1
            limiter.release()

        tasks = [worker(f"t{i}") for i in range(5)]
        await asyncio.gather(*tasks)
        assert max_active <= 2

    @pytest.mark.asyncio
    async def test_per_target_isolation(self):
        """Farklı hedefler bağımsız bucket'lara sahip olmalı."""
        limiter = RateLimiter(max_concurrent=10, rate_per_second=100.0)
        await limiter.acquire("target_a")
        limiter.release()
        await limiter.acquire("target_b")
        limiter.release()
        # Her iki target için ayrı bucket oluşturulmalı
        assert "target_a" in limiter._target_buckets
        assert "target_b" in limiter._target_buckets
