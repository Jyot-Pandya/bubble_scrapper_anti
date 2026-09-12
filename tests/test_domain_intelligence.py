"""
Tests for domain intelligence and adaptive learning.
"""

from apps.scraper_service.core.domain_intelligence import DomainIntelligence


def test_domain_intelligence_adaptive_switch():
    di = DomainIntelligence(failure_threshold=3)
    domain_url = "https://dynamic-spa.com/page"

    assert di.get_preferred_method(domain_url) == "http"

    # Simulate 3 consecutive HTTP failures
    di.record_result(domain_url, "http", success=False, duration_ms=500)
    di.record_result(domain_url, "http", success=False, duration_ms=510)
    di.record_result(domain_url, "http", success=False, duration_ms=520)

    # Now adaptive engine should recommend browser!
    assert di.get_preferred_method(domain_url) == "browser"

    # Simulate browser success
    di.record_result(domain_url, "browser", success=True, duration_ms=1200)
    stats = di.get_stats("dynamic-spa.com")
    assert stats.browser_successes == 1
    assert stats.browser_success_rate == 1.0


def test_domain_intelligence_summary():
    di = DomainIntelligence()
    di.record_result("https://example.com/a", "http", success=True, duration_ms=200)
    summary = di.summary()
    assert "example.com" in summary
    assert summary["example.com"]["http_success_rate"] == 1.0
    assert summary["example.com"]["preferred_method"] == "http"
