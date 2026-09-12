"""
Tests for URL normalization and deduplication key generation.
"""

from apps.scraper_service.core.security import normalize_url


def test_scheme_and_host_lowercased():
    url = "HTTPS://EXAMPLE.COM/Path/To/Page"
    norm = normalize_url(url)
    assert norm.startswith("https://example.com/Path/To/Page")


def test_standard_ports_removed():
    url_http = "http://example.com:80/article"
    url_https = "https://example.com:443/article"
    assert normalize_url(url_http) == "http://example.com/article"
    assert normalize_url(url_https) == "https://example.com/article"


def test_fragments_stripped():
    url = "https://example.com/article#section-3"
    assert normalize_url(url) == "https://example.com/article"


def test_tracking_parameters_stripped():
    url = "https://example.com/article?utm_source=twitter&utm_medium=social&utm_campaign=launch&fbclid=IwAR123&gclid=ABC456&_ga=1.234&id=42&category=science"
    norm = normalize_url(url)
    assert "utm_" not in norm
    assert "fbclid" not in norm
    assert "gclid" not in norm
    assert "_ga" not in norm
    # Preserved query parameters should be sorted
    assert norm == "https://example.com/article?category=science&id=42"


def test_query_params_sorted():
    url1 = "https://example.com/search?z=3&a=1&m=2"
    url2 = "https://example.com/search?a=1&m=2&z=3"
    assert normalize_url(url1) == normalize_url(url2)
