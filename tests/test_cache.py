"""
Tests for acquisition caching and deduplication.
"""

import time
from apps.scraper_service.core.cache import AcquisitionCache


def test_cache_hit_and_miss():
    cache = AcquisitionCache(max_entries=10, default_ttl=3600)
    url = "https://example.com/article"

    assert cache.get(url) is None

    cache.set(url, {"title": "Test Article"})
    hit = cache.get(url)
    assert hit is not None
    assert hit["title"] == "Test Article"


def test_cache_hit_with_tracking_params():
    cache = AcquisitionCache(max_entries=10, default_ttl=3600)
    url_base = "https://example.com/article"
    url_with_utm = "https://example.com/article?utm_source=newsletter&utm_medium=email"

    cache.set(url_base, {"title": "Found"})
    # Query with tracking params should normalize to same cache key!
    hit = cache.get(url_with_utm)
    assert hit is not None
    assert hit["title"] == "Found"


def test_cache_ttl_expiry():
    cache = AcquisitionCache(max_entries=10, default_ttl=1)
    url = "https://example.com/expiring"

    cache.set(url, "val", ttl=1)
    assert cache.get(url) == "val"

    time.sleep(1.1)
    assert cache.get(url) is None


def test_cache_lru_eviction():
    cache = AcquisitionCache(max_entries=2, default_ttl=3600)
    cache.set("https://example.com/1", "val1")
    cache.set("https://example.com/2", "val2")
    cache.set("https://example.com/3", "val3")

    # Entry 1 should have been evicted
    assert cache.get("https://example.com/1") is None
    assert cache.get("https://example.com/2") == "val2"
    assert cache.get("https://example.com/3") == "val3"
    assert cache.size() == 2
