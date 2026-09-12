"""
Tests for Webshare Proxy Provider and Pipeline Proxy Integration.
"""

from unittest.mock import AsyncMock, patch
import pytest

from apps.scraper_service.models.error import ErrorCode
from apps.scraper_service.models.request import FetchMode, FetchRequest
from apps.scraper_service.providers.fetcher.base import RawFetchResult
from apps.scraper_service.providers.fetcher.pipeline import AcquisitionPipeline
from apps.scraper_service.providers.proxy.webshare import WebshareProxyProvider
from apps.scraper_service.providers.storage.local import LocalStorageProvider


def test_webshare_provider_default_and_geo():
    provider = WebshareProxyProvider(
        username="myuser",
        password="mypassword",
        host="p.webshare.io",
        port=80,
    )

    # 1. Default rotating proxy (automatically includes -rotate for p.webshare.io)
    proxy_url, err = provider.get_proxy()
    assert err is None
    assert proxy_url == "http://myuser-rotate:mypassword@p.webshare.io:80"

    # 2. Geo-targeting: US
    proxy_us, err = provider.get_proxy("us")
    assert err is None
    assert proxy_us == "http://myuser-rotate-country-us:mypassword@p.webshare.io:80"

    # 3. Geo-targeting: Uppercase Germany
    proxy_de, err = provider.get_proxy("DE")
    assert err is None
    assert proxy_de == "http://myuser-rotate-country-de:mypassword@p.webshare.io:80"

    # 4. Invalid country codes
    _, err_long = provider.get_proxy("USA")
    assert "Invalid ISO 3166-1" in err_long

    _, err_digits = provider.get_proxy("12")
    assert "Invalid ISO 3166-1" in err_digits


def test_webshare_special_characters_url_encoding():
    provider = WebshareProxyProvider(
        username="user@domain",
        password="p@ss:w0rd!#",
        host="p.webshare.io",
        port=80,
    )
    proxy_url, err = provider.get_proxy("gb")
    assert err is None
    assert "user%40domain-rotate-country-gb" in proxy_url
    assert "p%40ss%3Aw0rd%21%23" in proxy_url


def test_webshare_residential_gateway():
    provider = WebshareProxyProvider(
        username="res_user",
        password="res_password",
        host="rp.webshare.io",
        port=80,
    )
    proxy_url, err = provider.get_proxy()
    assert err is None
    assert proxy_url == "http://res_user-rotate:res_password@rp.webshare.io:80"


def test_webshare_auto_extract_from_proxy_url():
    provider = WebshareProxyProvider(
        proxy_url="http://auto_user:auto_pass@p.webshare.io:80"
    )
    assert provider.username == "auto_user"
    assert provider.password == "auto_pass"

    proxy_url, err = provider.get_proxy()
    assert err is None
    assert proxy_url == "http://auto_user-rotate:auto_pass@p.webshare.io:80"

    # Dynamic geo-targeting using auto-extracted credentials
    proxy_fr, err = provider.get_proxy("fr")
    assert err is None
    assert proxy_fr == "http://auto_user-rotate-country-fr:auto_pass@p.webshare.io:80"


def test_webshare_unconfigured():
    provider = WebshareProxyProvider()
    proxy_url, err = provider.get_proxy()
    assert proxy_url is None
    assert "not configured" in err


@pytest.mark.asyncio
async def test_pipeline_webshare_integration(tmp_path):
    storage = LocalStorageProvider(base_dir=str(tmp_path))
    webshare_provider = WebshareProxyProvider(
        username="testuser",
        password="testpassword",
        host="p.webshare.io",
        port=80,
    )
    pipeline = AcquisitionPipeline(storage_provider=storage, proxy_provider=webshare_provider)

    mock_raw = RawFetchResult(
        final_url="https://example.com/geo-test",
        status_code=200,
        html="<html><body><h1>Geo Test</h1><p>Content from rotating proxy.</p></body></html>",
        method="http",
        duration_ms=210,
    )

    with patch("apps.scraper_service.providers.fetcher.pipeline.http_fetcher.fetch", new_callable=AsyncMock) as mock_http:
        mock_http.return_value = mock_raw

        # Request without country: should use default rotating webshare proxy
        req_default = FetchRequest(url="https://example.com/geo-test", mode=FetchMode.HTTP)
        resp_default = await pipeline.execute(req_default)

        assert resp_default.fetch.status_code == 200
        assert resp_default.fetch.proxy_used is True
        mock_http.assert_called_with(
            url="https://example.com/geo-test",
            timeout_ms=30000,
            proxy_url="http://testuser-rotate:testpassword@p.webshare.io:80",
        )

        # Request with country: should dynamically inject country into webshare username
        req_geo = FetchRequest(url="https://example.com/geo-test", mode=FetchMode.HTTP, country="jp")
        resp_geo = await pipeline.execute(req_geo)

        assert resp_geo.fetch.status_code == 200
        assert resp_geo.fetch.proxy_used is True
        assert resp_geo.fetch.country == "jp"
        mock_http.assert_called_with(
            url="https://example.com/geo-test",
            timeout_ms=30000,
            proxy_url="http://testuser-rotate-country-jp:testpassword@p.webshare.io:80",
        )


@pytest.mark.asyncio
async def test_pipeline_webshare_invalid_country(tmp_path):
    storage = LocalStorageProvider(base_dir=str(tmp_path))
    webshare_provider = WebshareProxyProvider(
        username="testuser",
        password="testpassword",
    )
    pipeline = AcquisitionPipeline(storage_provider=storage, proxy_provider=webshare_provider)

    req_invalid = FetchRequest(url="https://example.com/invalid-geo", country="INVALID")
    resp = await pipeline.execute(req_invalid)

    assert len(resp.errors) == 1
    assert resp.errors[0].code == ErrorCode.GEO_UNAVAILABLE
    assert "Invalid ISO 3166-1" in resp.errors[0].message
