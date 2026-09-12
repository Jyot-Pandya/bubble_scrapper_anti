"""
Edge cases, boundary values, and error paths tests.
"""

from unittest.mock import AsyncMock, patch
import pytest

from apps.scraper_service.core.security import validate_url_security, normalize_url
from apps.scraper_service.extractors.content import content_extractor
from apps.scraper_service.extractors.media import media_extractor
from apps.scraper_service.extractors.embeds import embed_extractor
from apps.scraper_service.models.error import ErrorCode
from apps.scraper_service.models.request import FetchMode, FetchRequest
from apps.scraper_service.providers.fetcher.base import RawFetchResult
from apps.scraper_service.providers.fetcher.pipeline import AcquisitionPipeline
from apps.scraper_service.providers.proxy.memory import StaticProxyProvider


def test_empty_and_blank_url_normalization():
    assert normalize_url("") == ""
    assert normalize_url("   ") == ""


def test_protocol_relative_url_normalization():
    norm = normalize_url("//example.com/path?utm_source=123")
    assert norm.startswith("https://example.com/path")
    assert "utm_source" not in norm


def test_empty_html_content_extraction():
    page_data, metadata = content_extractor.extract(
        html="",
        url="https://example.com",
    )
    assert page_data.final_url == "https://example.com"
    assert page_data.text is None or page_data.text == ""
    assert metadata.site_name is None
    assert metadata.json_ld == []


def test_html_with_no_title_or_body():
    html = "<html><div><p>Direct paragraph without body or title tags.</p></div></html>"
    page_data, metadata = content_extractor.extract(html, "https://example.com")
    assert page_data.title is None
    assert "Direct paragraph" in (page_data.text or "")


def test_relative_and_protocol_relative_image_discovery():
    html = """
    <html><body>
        <img src="//cdn.example.com/pic1.jpg" alt="Pic 1" width="500" height="300">
        <img src="../pic2.png" alt="Pic 2" width="400" height="200">
        <img src="/static/pic3.webp" alt="Pic 3" width="600" height="400">
        <img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" alt="Spacer">
    </body></html>
    """
    images = media_extractor.discover_images(html, "https://example.com/sub/page")
    assert len(images) == 3
    resolved = [img.resolved_url for img in images]
    assert "https://cdn.example.com/pic1.jpg" in resolved
    assert "https://example.com/pic2.png" in resolved
    assert "https://example.com/static/pic3.webp" in resolved


def test_malformed_video_embeds():
    html = """
    <html><body>
        <iframe src="https://example.com/widget"></iframe>
        <iframe src=""></iframe>
        <iframe data-src="https://www.youtube.com/watch?v=12345678901"></iframe>
        <video><source src="movie.mp4" type="video/mp4"></video>
    </body></html>
    """
    videos, embeds = embed_extractor.discover(html, "https://example.com")
    assert len(videos) == 2
    types = {v.type for v in videos}
    assert "youtube" in types
    assert "html5" in types
    assert len(embeds) == 1  # only non-empty generic iframe


@pytest.mark.asyncio
async def test_geo_proxy_unavailable(tmp_path):
    # Proxy provider only supports US proxy
    provider = StaticProxyProvider(country_proxies={"us": "http://proxy-us:8080"})
    pipeline = AcquisitionPipeline(proxy_provider=provider)

    req = FetchRequest(url="https://example.com", country="jp")
    resp = await pipeline.execute(req)

    assert len(resp.errors) == 1
    assert resp.errors[0].code == ErrorCode.GEO_UNAVAILABLE
    assert "unavailable" in resp.errors[0].message.lower()


@pytest.mark.asyncio
async def test_http_404_handling():
    pipeline = AcquisitionPipeline()

    mock_raw = RawFetchResult(
        final_url="https://example.com/not-found",
        status_code=404,
        html="<html><body><h1>404 Not Found</h1></body></html>",
        method="http",
        duration_ms=80,
    )

    with patch("apps.scraper_service.providers.fetcher.pipeline.http_fetcher.fetch", new_callable=AsyncMock) as mock_http:
        mock_http.return_value = mock_raw
        req = FetchRequest(url="https://example.com/not-found", mode=FetchMode.AUTO)
        resp = await pipeline.execute(req)

        assert resp.fetch.status_code == 404
        assert resp.quality.content_detected is False


@pytest.mark.asyncio
async def test_bypass_cache_flag():
    pipeline = AcquisitionPipeline()

    mock_raw1 = RawFetchResult(
        final_url="https://example.com/cached-test",
        status_code=200,
        html="<html><body><article><h1>Version 1</h1><p>" + "Content paragraph " * 20 + "</p></article></body></html>",
        method="http",
        duration_ms=100,
    )

    mock_raw2 = RawFetchResult(
        final_url="https://example.com/cached-test",
        status_code=200,
        html="<html><body><article><h1>Version 2</h1><p>" + "Content paragraph " * 20 + "</p></article></body></html>",
        method="http",
        duration_ms=120,
    )

    with patch("apps.scraper_service.providers.fetcher.pipeline.http_fetcher.fetch", new_callable=AsyncMock) as mock_http:
        mock_http.return_value = mock_raw1
        req1 = FetchRequest(url="https://example.com/cached-test", mode=FetchMode.AUTO)
        resp1 = await pipeline.execute(req1)
        assert resp1.page.title == "Version 1"

        # Second request without bypass_cache should return cache hit
        req2 = FetchRequest(url="https://example.com/cached-test", mode=FetchMode.AUTO, bypass_cache=False)
        resp2 = await pipeline.execute(req2)
        assert resp2.fetch.method == "cache"

        # Third request WITH bypass_cache should call fetch again
        mock_http.return_value = mock_raw2
        req3 = FetchRequest(url="https://example.com/cached-test", mode=FetchMode.AUTO, bypass_cache=True)
        resp3 = await pipeline.execute(req3)
        assert resp3.fetch.method == "http"
        assert resp3.page.title == "Version 2"


@pytest.mark.asyncio
async def test_dns_resolution_failure_returns_dns_error():
    pipeline = AcquisitionPipeline()
    req = FetchRequest(url="https://this-domain-does-not-exist-xyz-987654321.org", mode=FetchMode.AUTO)
    resp = await pipeline.execute(req)
    assert len(resp.errors) >= 1
    assert resp.errors[0].code == ErrorCode.DNS_ERROR
    assert resp.errors[0].retryable is True


def test_rate_limiter_cooldown_by_full_url():
    from apps.scraper_service.core.rate_limiter import DomainRateLimiter
    limiter = DomainRateLimiter(domain_cooldown=60.0)
    limiter.trigger_cooldown("https://target-domain.com/some/path?param=1", duration=30.0)
    in_cd, rem = limiter.is_in_cooldown("https://target-domain.com/another/path")
    assert in_cd is True
    assert rem > 0
    in_cd2, _ = limiter.is_in_cooldown("target-domain.com")
    assert in_cd2 is True


@pytest.mark.asyncio
async def test_storage_path_traversal_blocked(tmp_path):
    from apps.scraper_service.providers.storage.local import LocalStorageProvider
    storage = LocalStorageProvider(base_dir=str(tmp_path))
    saved_url = await storage.save("../../traversal.txt", b"safe content")
    # File must be stored inside base_dir
    assert (tmp_path / "traversal.txt").exists()
    # Must NOT have written above tmp_path
    assert not (tmp_path.parent / "traversal.txt").exists()


@pytest.mark.asyncio
async def test_image_downloader_ssrf_protection(tmp_path):
    from apps.scraper_service.models.response import ImageData
    from apps.scraper_service.providers.storage.local import LocalStorageProvider
    storage = LocalStorageProvider(base_dir=str(tmp_path))
    unsafe_img = ImageData(
        source_url="http://127.0.0.1:8000/internal-avatar.png",
        resolved_url="http://127.0.0.1:8000/internal-avatar.png",
    )
    res = await media_extractor.download_images([unsafe_img], storage_provider=storage)
    assert res[0].storage_url is None


def test_jsonld_and_picture_source_image_discovery():
    from apps.scraper_service.models.response import Metadata
    html = """
    <html><body>
        <picture>
            <source srcset="/images/hero-large.webp" media="(min-width: 800px)">
            <img src="/images/hero-small.jpg" alt="Responsive Hero" width="800" height="400">
        </picture>
    </body></html>
    """
    meta = Metadata(
        json_ld=[{
            "@context": "https://schema.org",
            "@type": "Article",
            "image": "https://example.com/jsonld-hero.jpg"
        }]
    )
    images = media_extractor.discover_images(html, "https://example.com/article", metadata=meta)
    resolved_urls = [img.resolved_url for img in images]
    assert "https://example.com/jsonld-hero.jpg" in resolved_urls
    assert "https://example.com/images/hero-large.webp" in resolved_urls


def test_integer_and_hex_ip_ssrf_blocked():
    # 2130706433 is 127.0.0.1 as integer
    is_safe1, err1 = validate_url_security("http://2130706433/")
    assert is_safe1 is False
    assert "restricted" in err1.lower() or "blocked" in err1.lower() or "dns" in err1.lower()

    # 0x7f000001 is 127.0.0.1 as hex
    is_safe2, err2 = validate_url_security("http://0x7f000001/")
    assert is_safe2 is False
    assert "restricted" in err2.lower() or "blocked" in err2.lower() or "dns" in err2.lower()

