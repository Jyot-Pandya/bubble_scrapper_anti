"""
Tests for multi-stage acquisition escalation pipeline.
"""

from unittest.mock import AsyncMock, patch
import pytest

from apps.scraper_service.models.error import ErrorCode, ScraperErrorDetail
from apps.scraper_service.models.request import FetchMode, FetchRequest
from apps.scraper_service.providers.fetcher.base import RawFetchResult
from apps.scraper_service.providers.fetcher.pipeline import AcquisitionPipeline
from apps.scraper_service.providers.storage.local import LocalStorageProvider


@pytest.mark.asyncio
async def test_pipeline_http_success(sample_article_html, tmp_path):
    storage = LocalStorageProvider(base_dir=str(tmp_path))
    pipeline = AcquisitionPipeline(storage_provider=storage)

    mock_raw = RawFetchResult(
        final_url="https://example.com/fusion-news",
        status_code=200,
        html=sample_article_html,
        method="http",
        duration_ms=150,
    )

    with patch("apps.scraper_service.providers.fetcher.pipeline.http_fetcher.fetch", new_callable=AsyncMock) as mock_http:
        mock_http.return_value = mock_raw

        req = FetchRequest(url="https://example.com/fusion-news", mode=FetchMode.AUTO)
        resp = await pipeline.execute(req)

        assert resp.fetch.method == "http"
        assert resp.fetch.status_code == 200
        assert "Fusion" in resp.page.title
        assert resp.quality.content_detected is True
        assert resp.quality.extraction_confidence > 0.7
        assert len(resp.assets.images) >= 2
        assert len(resp.assets.videos) == 1
        assert len(resp.errors) == 0


@pytest.mark.asyncio
async def test_pipeline_escalation_on_js_shell(sample_js_shell_html, sample_article_html, tmp_path):
    storage = LocalStorageProvider(base_dir=str(tmp_path))
    pipeline = AcquisitionPipeline(storage_provider=storage)

    # HTTP returns JS shell
    mock_http_raw = RawFetchResult(
        final_url="https://example.com/spa-article",
        status_code=200,
        html=sample_js_shell_html,
        method="http",
        duration_ms=100,
    )

    # Browser returns rendered article
    mock_browser_raw = RawFetchResult(
        final_url="https://example.com/spa-article",
        status_code=200,
        html=sample_article_html,
        method="browser",
        duration_ms=800,
    )

    with patch("apps.scraper_service.providers.fetcher.pipeline.http_fetcher.fetch", new_callable=AsyncMock) as mock_http, \
         patch("apps.scraper_service.providers.fetcher.pipeline.browser_fetcher.fetch", new_callable=AsyncMock) as mock_browser:

        mock_http.return_value = mock_http_raw
        mock_browser.return_value = mock_browser_raw

        req = FetchRequest(url="https://example.com/spa-article", mode=FetchMode.AUTO)
        resp = await pipeline.execute(req)

        # Pipeline must have escalated to browser!
        assert mock_http.called
        assert mock_browser.called
        assert resp.fetch.method == "browser"
        assert resp.fetch.attempts == 2
        assert resp.quality.content_detected is True


@pytest.mark.asyncio
async def test_pipeline_stops_on_captcha(sample_captcha_html, tmp_path):
    storage = LocalStorageProvider(base_dir=str(tmp_path))
    pipeline = AcquisitionPipeline(storage_provider=storage)

    mock_raw = RawFetchResult(
        final_url="https://example.com/blocked",
        status_code=403,
        html=sample_captcha_html,
        method="http",
        duration_ms=120,
    )

    with patch("apps.scraper_service.providers.fetcher.pipeline.http_fetcher.fetch", new_callable=AsyncMock) as mock_http, \
         patch("apps.scraper_service.providers.fetcher.pipeline.browser_fetcher.fetch", new_callable=AsyncMock) as mock_browser:

        mock_http.return_value = mock_raw

        req = FetchRequest(url="https://example.com/blocked", mode=FetchMode.AUTO)
        resp = await pipeline.execute(req)

        # Should NOT escalate to browser on CAPTCHA / wall
        assert not mock_browser.called
        assert len(resp.errors) >= 1
        assert resp.errors[0].code == ErrorCode.CAPTCHA
