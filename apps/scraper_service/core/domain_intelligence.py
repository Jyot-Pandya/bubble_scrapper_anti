"""
Adaptive domain intelligence and stage recommendation as specified in Section 20.
"""

from urllib.parse import urlparse
from typing import Dict, Any, Optional


class DomainStats:
    def __init__(self, domain: str):
        self.domain = domain
        self.http_attempts: int = 0
        self.http_successes: int = 0
        self.browser_attempts: int = 0
        self.browser_successes: int = 0
        self.total_duration_ms: int = 0
        self.consecutive_http_failures: int = 0

    def record_http(self, success: bool, duration_ms: int):
        self.http_attempts += 1
        self.total_duration_ms += duration_ms
        if success:
            self.http_successes += 1
            self.consecutive_http_failures = 0
        else:
            self.consecutive_http_failures += 1

    def record_browser(self, success: bool, duration_ms: int):
        self.browser_attempts += 1
        self.total_duration_ms += duration_ms
        if success:
            self.browser_successes += 1

    @property
    def http_success_rate(self) -> float:
        if self.http_attempts == 0:
            return 1.0  # optimistic default
        return round(self.http_successes / self.http_attempts, 2)

    @property
    def browser_success_rate(self) -> float:
        if self.browser_attempts == 0:
            return 1.0
        return round(self.browser_successes / self.browser_attempts, 2)

    @property
    def preferred_method(self) -> str:
        # If repeatedly failing on HTTP (e.g. >= 3 failures) or low success rate on HTTP, prefer browser
        if self.consecutive_http_failures >= 3 or (self.http_attempts >= 5 and self.http_success_rate < 0.25):
            return "browser"
        return "http"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "preferred_method": self.preferred_method,
            "http_attempts": self.http_attempts,
            "http_success_rate": self.http_success_rate,
            "browser_attempts": self.browser_attempts,
            "browser_success_rate": self.browser_success_rate,
            "consecutive_http_failures": self.consecutive_http_failures,
        }


class DomainIntelligence:
    def __init__(self, failure_threshold: int = 3):
        self.failure_threshold = failure_threshold
        self._domains: Dict[str, DomainStats] = {}

    def _extract_domain(self, url: str) -> str:
        try:
            return urlparse(url).netloc.lower().split(":")[0]
        except Exception:
            return "unknown"

    def get_stats(self, domain: str) -> DomainStats:
        if domain not in self._domains:
            self._domains[domain] = DomainStats(domain)
        return self._domains[domain]

    def record_result(self, url: str, method: str, success: bool, duration_ms: int):
        domain = self._extract_domain(url)
        stats = self.get_stats(domain)
        if method == "http":
            stats.record_http(success, duration_ms)
        elif method == "browser":
            stats.record_browser(success, duration_ms)

    def get_preferred_method(self, url: str) -> str:
        domain = self._extract_domain(url)
        if domain in self._domains:
            return self._domains[domain].preferred_method
        return "http"

    def summary(self) -> Dict[str, Any]:
        return {domain: stats.to_dict() for domain, stats in self._domains.items()}


domain_intelligence = DomainIntelligence()
