"""
Proxy provider interface as specified in Section 10 and Section 21.
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple


class BaseProxyProvider(ABC):
    @abstractmethod
    def get_proxy(self, country: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Returns (proxy_url, error_message).
        If country is requested but unsupported, returns (None, "geo_unavailable message").
        """
        pass

    @abstractmethod
    def report_success(self, proxy_url: str):
        """Records proxy success."""
        pass

    @abstractmethod
    def report_failure(self, proxy_url: str, error: str):
        """Records proxy failure."""
        pass
