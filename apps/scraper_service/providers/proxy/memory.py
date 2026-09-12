"""
Static and No-op proxy providers.
"""

from typing import Optional, Tuple, Dict
from apps.scraper_service.providers.proxy.base import BaseProxyProvider


class NoProxyProvider(BaseProxyProvider):
    def get_proxy(self, country: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        if country:
            return None, f"Geo-targeting for country '{country}' is not available (no proxy provider configured)."
        return None, None

    def report_success(self, proxy_url: str):
        pass

    def report_failure(self, proxy_url: str, error: str):
        pass


class StaticProxyProvider(BaseProxyProvider):
    def __init__(self, default_proxy_url: Optional[str] = None, country_proxies: Optional[Dict[str, str]] = None):
        self.default_proxy_url = default_proxy_url
        self.country_proxies = {k.lower(): v for k, v in (country_proxies or {}).items()}

    def get_proxy(self, country: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        if country:
            c = country.lower()
            if c in self.country_proxies:
                return self.country_proxies[c], None
            return None, f"Geo-targeting for country '{country}' is unavailable."
        return self.default_proxy_url, None

    def report_success(self, proxy_url: str):
        pass

    def report_failure(self, proxy_url: str, error: str):
        pass
