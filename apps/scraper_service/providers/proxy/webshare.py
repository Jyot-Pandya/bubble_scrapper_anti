"""
Webshare Proxy Provider implementation.
Supports Webshare rotating datacenter and residential proxy backbones,
dynamic geo-targeting by country ISO code, and session stickiness.
"""

from typing import Optional, Tuple
from urllib.parse import quote, unquote, urlsplit
from apps.scraper_service.providers.proxy.base import BaseProxyProvider


class WebshareProxyProvider(BaseProxyProvider):
    """
    Adapter for Webshare proxy network (webshare.io).

    Webshare supports rotating requests on every connection and dynamic
    geo-targeting by appending '-country-<cc>' to the proxy username.
    Host options:
    - p.webshare.io:80 (Datacenter rotating)
    - rp.webshare.io:80 (Residential rotating)
    """

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        host: str = "p.webshare.io",
        port: int = 80,
        proxy_url: Optional[str] = None,
    ):
        self.username = username
        self.password = password
        self.host = host or "p.webshare.io"
        self.port = port or 80
        self.custom_proxy_url = proxy_url

        # If a full proxy_url is provided, auto-extract credentials and host/port if missing
        if self.custom_proxy_url and (not self.username or not self.password):
            try:
                parsed = urlsplit(self.custom_proxy_url)
                if parsed.username and not self.username:
                    self.username = unquote(parsed.username)
                if parsed.password and not self.password:
                    self.password = unquote(parsed.password)
                if parsed.hostname:
                    self.host = parsed.hostname
                if parsed.port:
                    self.port = parsed.port
            except Exception:
                pass

    def get_proxy(self, country: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Returns (proxy_url, error_message).
        If country is specified, injects '-country-<cc>' into the Webshare username.
        """
        # If user provided a raw proxy_url without explicit credentials, and no country is requested, use it
        if self.custom_proxy_url and not country and not (self.username and self.password):
            return self.custom_proxy_url, None

        if not self.username or not self.password:
            return None, "Webshare credentials (username and password) are not configured."

        user = self.username
        # Webshare rotating gateway (p.webshare.io / rp.webshare.io) requires '-rotate' in username
        is_webshare_rotating = "p.webshare.io" in self.host or "rp.webshare.io" in self.host
        base_user = user
        if "-country-" in base_user:
            base_user = base_user.split("-country-")[0]
        if "-rotate" in base_user:
            base_user = base_user.split("-rotate")[0]

        if is_webshare_rotating:
            if country:
                cc = country.strip().lower()
                if len(cc) != 2 or not cc.isalpha():
                    return None, f"Invalid ISO 3166-1 country code '{country}'. Expected 2-letter alphabetic code."
                user = f"{base_user}-rotate-country-{cc}"
            else:
                user = f"{base_user}-rotate"
        else:
            if country:
                cc = country.strip().lower()
                if len(cc) != 2 or not cc.isalpha():
                    return None, f"Invalid ISO 3166-1 country code '{country}'. Expected 2-letter alphabetic code."
                user = f"{base_user}-country-{cc}"
            else:
                user = base_user

        # URL encode credentials in case of special characters in passwords
        encoded_user = quote(user, safe="")
        encoded_pass = quote(self.password, safe="")

        proxy_str = f"http://{encoded_user}:{encoded_pass}@{self.host}:{self.port}"
        return proxy_str, None

    def report_success(self, proxy_url: str):
        pass

    def report_failure(self, proxy_url: str, error: str):
        pass
