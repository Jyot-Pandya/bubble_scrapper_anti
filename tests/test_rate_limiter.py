"""
Tests for domain rate limiting and courtesy pacing.
"""

import asyncio
import pytest
from apps.scraper_service.core.rate_limiter import DomainRateLimiter


@pytest.mark.asyncio
async def test_domain_rate_limiter_acquire_release():
    limiter = DomainRateLimiter(global_concurrency=5, domain_concurrency=2, domain_min_interval=0.01)
    url = "https://example.com/test1"

    await limiter.acquire(url)
    # Acquired successfully
    limiter.release(url)


@pytest.mark.asyncio
async def test_domain_cooldown():
    limiter = DomainRateLimiter(global_concurrency=5, domain_concurrency=2, domain_cooldown=2.0)
    url = "https://rate-limited.com/api"

    # Trigger cooldown
    limiter.trigger_cooldown("rate-limited.com", duration=1.0)
    in_cooldown, remaining = limiter.is_in_cooldown("rate-limited.com")
    assert in_cooldown is True
    assert remaining > 0

    with pytest.raises(RuntimeError) as exc_info:
        await limiter.acquire(url)
    assert "rate-limit cooldown" in str(exc_info.value)
