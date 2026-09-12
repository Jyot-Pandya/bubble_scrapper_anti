"""
Tests for Scraper Client library (sync and async).
"""

from unittest.mock import patch, MagicMock, AsyncMock
import pytest
import httpx

from packages.scraper_client.client import ScraperClient, AsyncScraperClient
from packages.scraper_client.exceptions import ScraperAPIError, ScraperTimeoutError
from packages.scraper_client.models import NormalizedResponse, PageData, FetchProvenance, QualityData, RequestEcho


MOCK_RESPONSE_DICT = {
    "request": {"url": "https://example.com/story"},
    "page": {
        "final_url": "https://example.com/story",
        "title": "A Great Story",
        "text": "This is content text",
    },
    "metadata": {},
    "assets": {"images": [], "videos": [], "embeds": []},
    "captures": {},
    "fetch": {
        "method": "http",
        "status_code": 200,
        "attempts": 1,
        "duration_ms": 300,
        "retrieved_at": "2026-09-09T18:00:00Z",
        "proxy_used": False,
    },
    "quality": {
        "content_detected": True,
        "text_length": 19,
        "extraction_confidence": 0.85,
    },
    "errors": [],
}


def test_sync_client_fetch():
    client = ScraperClient(base_url="http://test-scraper:8000")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_RESPONSE_DICT

    with patch("httpx.Client.post", return_value=mock_resp):
        res = client.fetch("https://example.com/story")
        assert isinstance(res, NormalizedResponse)
        assert res.page.title == "A Great Story"
        assert res.fetch.status_code == 200


def test_sync_client_error():
    client = ScraperClient(base_url="http://test-scraper:8000")

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal error"

    with patch("httpx.Client.post", return_value=mock_resp):
        with pytest.raises(ScraperAPIError) as exc_info:
            client.fetch("https://example.com/error")
        assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_async_client_fetch():
    client = AsyncScraperClient(base_url="http://test-scraper:8000")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_RESPONSE_DICT

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        res = await client.fetch("https://example.com/story")
        assert isinstance(res, NormalizedResponse)
        assert res.page.title == "A Great Story"
        assert res.quality.extraction_confidence == 0.85
