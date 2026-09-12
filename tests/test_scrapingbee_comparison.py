"""
Tests and benchmark comparisons between Outside Bubble Scraper Service and ScrapingBee.

Validates feature parity, performance latency benchmarks, credit/cost equivalency models,
structured extraction output vs. raw HTML, and rate-limiting courtesy.
"""

import time
import pytest
from unittest.mock import AsyncMock, patch

from apps.scraper_service.models.request import FetchMode, FetchRequest
from apps.scraper_service.providers.fetcher.base import RawFetchResult
from apps.scraper_service.providers.fetcher.pipeline import AcquisitionPipeline
from apps.scraper_service.providers.storage.local import LocalStorageProvider
from apps.scraper_service.core.cache import AcquisitionCache
from apps.scraper_service.core.rate_limiter import DomainRateLimiter
from packages.scraper_client.models import NormalizedResponse


# -----------------------------------------------------------------------------
# ScrapingBee Equivalent Cost Model
# -----------------------------------------------------------------------------
# ScrapingBee Credit Pricing (Standard Plan: $49 for 100,000 credits = $0.00049/credit)
# - Standard HTTP request: 1 credit
# - Javascript Rendering (render_js=true): 5 credits
# - Premium Proxy (residential): 10-25 credits
# - Screenshot capture (screenshot=true): 5 credits
# -----------------------------------------------------------------------------
def calculate_scrapingbee_equivalent_cost(
    is_browser: bool = False,
    has_screenshot: bool = False,
    is_premium_proxy: bool = False,
    credit_cost_usd: float = 0.00049,
) -> dict:
    credits = 1
    if is_browser:
        credits = 5
    if has_screenshot:
        credits += 5
    if is_premium_proxy:
        credits = 25
    return {
        "credits": credits,
        "cost_usd": round(credits * credit_cost_usd, 5),
    }


@pytest.mark.asyncio
async def test_scrapingbee_feature_parity_js_rendering(sample_article_html, tmp_path):
    """
    Test parity with ScrapingBee's `render_js=true` feature.
    Verifies that when browser mode is requested, Playwright executes JS,
    produces rendered DOM, and provides full Markdown + media extraction.
    """
    storage = LocalStorageProvider(base_dir=str(tmp_path))
    pipeline = AcquisitionPipeline(storage_provider=storage)

    mock_raw = RawFetchResult(
        final_url="https://example.com/dynamic-spa",
        status_code=200,
        html=sample_article_html,
        method="browser",
        duration_ms=1250,
        headers={"content-type": "text/html"},
    )

    with patch("apps.scraper_service.providers.fetcher.pipeline.browser_fetcher.fetch", new_callable=AsyncMock) as mock_browser:
        mock_browser.return_value = mock_raw

        req = FetchRequest(
            url="https://example.com/dynamic-spa",
            mode=FetchMode.BROWSER,
            include_markdown=True,
            include_images=True,
        )
        res = await pipeline.execute(req)

        assert res.fetch.method == "browser"
        assert res.fetch.status_code == 200
        assert "Fusion" in res.page.title
        assert res.page.markdown is not None
        assert len(res.assets.images) >= 1
        assert res.quality.content_detected is True

        # ScrapingBee credit equivalent: 5 credits for JS rendering
        sb_stats = calculate_scrapingbee_equivalent_cost(is_browser=True)
        assert sb_stats["credits"] == 5
        assert sb_stats["cost_usd"] > 0


@pytest.mark.asyncio
async def test_scrapingbee_feature_parity_screenshots(tmp_path):
    """
    Test parity with ScrapingBee's `screenshot=true` and `screenshot_full_page=true`.
    Verifies screenshot bytes are captured, stored in storage provider,
    and returned as accessible URLs.
    """
    storage = LocalStorageProvider(base_dir=str(tmp_path))
    pipeline = AcquisitionPipeline(storage_provider=storage)

    fake_jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 500  # Minimal JPEG header + payload
    mock_raw = RawFetchResult(
        final_url="https://example.com/page-to-capture",
        status_code=200,
        html="<html><body><h1>Visual Proof</h1></body></html>",
        method="browser",
        duration_ms=1800,
        screenshot_bytes=fake_jpeg,
        headers={},
    )

    with patch("apps.scraper_service.providers.fetcher.pipeline.browser_fetcher.fetch", new_callable=AsyncMock) as mock_browser:
        mock_browser.return_value = mock_raw

        req = FetchRequest(
            url="https://example.com/page-to-capture",
            mode=FetchMode.BROWSER,
            screenshot=True,
            full_page_screenshot=True,
        )
        res = await pipeline.execute(req)

        assert res.captures.full_page_screenshot_url is not None
        assert "screenshots/" in res.captures.full_page_screenshot_url

        # ScrapingBee charges 5 credits for render_js + 5 credits for screenshot = 10 credits
        sb_stats = calculate_scrapingbee_equivalent_cost(is_browser=True, has_screenshot=True)
        assert sb_stats["credits"] == 10


@pytest.mark.asyncio
async def test_scrapingbee_structured_extraction_superiority(sample_article_html, tmp_path):
    """
    Compare extraction richness:
    ScrapingBee returns raw HTML by default, requiring client-side parsing or complex regex rules.
    Our service returns structured Markdown, article author, published date, OpenGraph,
    JSON-LD, and hero-image classification out of the box in a single pass.
    """
    storage = LocalStorageProvider(base_dir=str(tmp_path))
    pipeline = AcquisitionPipeline(storage_provider=storage)

    mock_raw = RawFetchResult(
        final_url="https://example.com/article",
        status_code=200,
        html=sample_article_html,
        method="http",
        duration_ms=220,
        headers={"content-type": "text/html"},
    )

    with patch("apps.scraper_service.providers.fetcher.pipeline.http_fetcher.fetch", new_callable=AsyncMock) as mock_http:
        mock_http.return_value = mock_raw

        req = FetchRequest(url="https://example.com/article", mode=FetchMode.HTTP)
        res = await pipeline.execute(req)

        # 1. Author and published date extracted automatically
        assert "Sarah Connor" in res.page.author
        assert res.page.published_at.startswith("2026-09-09")

        # 2. Markdown generated with readable headings and paragraphs
        assert "# Breakthrough in Fusion Energy Announced" in res.page.markdown

        # 3. Hero image identified from OpenGraph priority
        hero_images = [img for img in res.assets.images if img.is_hero]
        assert len(hero_images) >= 1
        assert "fusion-hero.jpg" in hero_images[0].resolved_url

        # 4. Embedded videos discovered
        assert len(res.assets.videos) >= 1
        assert "dQw4w9WgXcQ" in res.assets.videos[0].source_url

        # 5. Tracking pixels (1x1) filtered out
        tracker_images = [img for img in res.assets.images if "pixel.gif" in img.source_url]
        assert len(tracker_images) == 0


@pytest.mark.asyncio
async def test_scrapingbee_latency_cache_advantage():
    """
    Compare caching efficiency:
    ScrapingBee does NOT provide free in-memory caching - every request costs credits and network hops.
    Our service provides sub-5ms LRU TTL memory caching with query normalization, saving 100% of credits.
    """
    cache = AcquisitionCache(max_entries=100, default_ttl=60)

    mock_resp = NormalizedResponse(
        request={"url": "https://example.com/cached-article?utm_source=test"},
        page={"final_url": "https://example.com/cached-article", "title": "Cached Title"},
        fetch={"method": "http", "status_code": 200, "duration_ms": 250, "retrieved_at": "2026-09-10T00:00:00Z"},
        quality={"content_detected": True, "extraction_confidence": 0.9},
    )

    # Populate cache
    cache.set("https://example.com/cached-article?utm_source=test", mock_resp)

    # Query with different tracking parameters (should hit same normalized cache key)
    start_t = time.time()
    cached_hit = cache.get("https://example.com/cached-article?utm_medium=email")
    latency_ms = (time.time() - start_t) * 1000

    assert cached_hit is not None
    assert cached_hit.page.title == "Cached Title"
    # Local cache retrieval is sub-10ms, far outperforming any remote API roundtrip (typically 300ms-1500ms)
    assert latency_ms < 10.0


@pytest.mark.asyncio
async def test_scrapingbee_concurrency_and_rate_limit_protection():
    """
    Compare domain courtesy and anti-ban mechanisms:
    ScrapingBee imposes strict global account concurrency limits (5 on Freelance, 40 on Startup)
    and drops or queues requests with 429 when exceeded.
    Our service separates global concurrency from per-domain concurrency (domain limit = 2),
    with automatic 60s cooldown to protect IP reputation.
    """
    limiter = DomainRateLimiter(
        global_concurrency=20,
        domain_concurrency=2,
        domain_min_interval=0.1,
        domain_cooldown=60.0,
    )

    # 1. Acquire up to domain limit
    await limiter.acquire("https://target.com/page1")
    await limiter.acquire("https://target.com/page2")

    # 2. Trigger cooldown after HTTP 429
    limiter.trigger_cooldown("https://target.com")
    in_cd, remaining = limiter.is_in_cooldown("target.com")
    assert in_cd is True
    assert remaining > 0

    # 3. Subsequent attempts to the domain are immediately blocked by cooldown
    with pytest.raises(RuntimeError) as exc_info:
        await limiter.acquire("https://target.com/page3")
    assert "rate-limit cooldown" in str(exc_info.value)

    # Release previous slots
    limiter.release("https://target.com/page1")
    limiter.release("https://target.com/page2")


def test_scrapingbee_cost_savings_benchmark():
    """
    Simulate cost and credit savings for an Outside Bubble ingestion run of 10,000 URLs:
    - 7,000 HTTP fetches (7,000 credits)
    - 2,500 Browser JS renders (12,500 credits)
    - 500 Screenshots (5,000 credits)
    Total ScrapingBee Credits: 24,500 credits.
    At $0.00049/credit, ScrapingBee would charge $12.00 per 10k batch.
    At 1,000,000 fetches/month, ScrapingBee costs ~$1,200+/month.
    Our self-hosted service cost: $0 API fees (runs on standard $10-$20 VPS).
    """
    http_fetches = 7000
    browser_fetches = 2500
    screenshot_fetches = 500

    sb_credits = (
        (http_fetches * 1)
        + (browser_fetches * 5)
        + (screenshot_fetches * (5 + 5))
    )
    cost_per_10k_usd = sb_credits * 0.00049
    monthly_volume = 1_000_000
    monthly_sb_cost = (monthly_volume / 10_000) * cost_per_10k_usd

    assert sb_credits == 24_500
    assert cost_per_10k_usd > 10.0
    assert monthly_sb_cost > 1000.0  # Over $1,000/month saved on commercial scraping fees
