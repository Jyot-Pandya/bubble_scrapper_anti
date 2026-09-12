"""
High-performance direct HTTP fetcher using httpx as specified in Section 8.
"""

import time
import socket
import ssl
from typing import Optional, Dict

import httpx

from apps.scraper_service.models.error import ErrorCode, ScraperErrorDetail
from apps.scraper_service.providers.fetcher.base import BaseFetcher, RawFetchResult
from apps.scraper_service.config import settings


class HttpFetcher(BaseFetcher):
    def __init__(self, user_agent: Optional[str] = None, max_response_bytes: int = None):
        self.user_agent = user_agent or settings.default_user_agent
        self.max_response_bytes = max_response_bytes or settings.max_response_bytes
        self._headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Ch-Ua": '"Not?A_Brand";v="99", "Chromium";v="128"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }

    async def fetch(
        self,
        url: str,
        timeout_ms: int = 30000,
        proxy_url: Optional[str] = None,
        **kwargs,
    ) -> RawFetchResult:
        start_time = time.time()
        timeout = timeout_ms / 1000.0

        headers = dict(self._headers)
        if kwargs.get("stealth", True) and "OutsideBubble" in headers.get("User-Agent", ""):
            headers["User-Agent"] = headers["User-Agent"].split("OutsideBubble")[0].strip()

        client_kwargs = {
            "headers": headers,
            "follow_redirects": True,
            "timeout": httpx.Timeout(timeout, connect=min(timeout, 10.0)),
        }
        if proxy_url:
            client_kwargs["proxy"] = proxy_url

        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                resp = await client.get(url)
                duration_ms = int((time.time() - start_time) * 1000)

                # Check content-type to reject binary payloads unless html/text
                content_type = resp.headers.get("content-type", "").lower()
                is_text = any(t in content_type for t in ("text/", "html", "xml", "json"))

                # Check body size
                if len(resp.content) > self.max_response_bytes:
                    return RawFetchResult(
                        final_url=str(resp.url),
                        status_code=resp.status_code,
                        html="",
                        method="http",
                        duration_ms=duration_ms,
                        error=ScraperErrorDetail(
                            code=ErrorCode.UNSUPPORTED_CONTENT,
                            message=f"Response size exceeded limit ({len(resp.content)} > {self.max_response_bytes} bytes)",
                            stage="http",
                            retryable=False,
                            status_code=resp.status_code,
                        ),
                    )

                if not is_text and resp.status_code == 200:
                    return RawFetchResult(
                        final_url=str(resp.url),
                        status_code=resp.status_code,
                        html="",
                        method="http",
                        duration_ms=duration_ms,
                        error=ScraperErrorDetail(
                            code=ErrorCode.UNSUPPORTED_CONTENT,
                            message=f"Unsupported non-HTML/text content type: {content_type}",
                            stage="http",
                            retryable=False,
                            status_code=resp.status_code,
                        ),
                    )

                # Check status code errors
                error_detail = None
                if resp.status_code == 429:
                    error_detail = ScraperErrorDetail(
                        code=ErrorCode.RATE_LIMITED,
                        message="HTTP 429 Too Many Requests",
                        stage="http",
                        retryable=True,
                        status_code=429,
                    )
                elif resp.status_code in (401, 407):
                    error_detail = ScraperErrorDetail(
                        code=ErrorCode.LOGIN_REQUIRED,
                        message=f"HTTP {resp.status_code} Unauthorized / Authentication Required",
                        stage="http",
                        retryable=False,
                        status_code=resp.status_code,
                    )
                elif resp.status_code == 403:
                    error_detail = ScraperErrorDetail(
                        code=ErrorCode.BLOCKED,
                        message="HTTP 403 Forbidden / Access Denied",
                        stage="http",
                        retryable=True,
                        status_code=403,
                    )
                elif resp.status_code == 451:
                    error_detail = ScraperErrorDetail(
                        code=ErrorCode.ROBOTS_RESTRICTED,
                        message="HTTP 451 Unavailable For Legal Reasons",
                        stage="http",
                        retryable=False,
                        status_code=451,
                    )
                elif resp.status_code >= 400:
                    error_detail = ScraperErrorDetail(
                        code=ErrorCode.UNKNOWN,
                        message=f"HTTP Error {resp.status_code}",
                        stage="http",
                        retryable=(resp.status_code >= 500),
                        status_code=resp.status_code,
                    )

                # Decode html with fallback
                html_text = resp.text

                return RawFetchResult(
                    final_url=str(resp.url),
                    status_code=resp.status_code,
                    html=html_text,
                    method="http",
                    duration_ms=duration_ms,
                    headers=dict(resp.headers),
                    error=error_detail,
                )

        except httpx.ConnectTimeout:
            duration_ms = int((time.time() - start_time) * 1000)
            return RawFetchResult(
                final_url=url,
                status_code=0,
                html="",
                method="http",
                duration_ms=duration_ms,
                error=ScraperErrorDetail(
                    code=ErrorCode.CONNECTION_TIMEOUT,
                    message="Connection timed out while reaching target host",
                    stage="http",
                    retryable=True,
                ),
            )
        except httpx.ReadTimeout:
            duration_ms = int((time.time() - start_time) * 1000)
            return RawFetchResult(
                final_url=url,
                status_code=0,
                html="",
                method="http",
                duration_ms=duration_ms,
                error=ScraperErrorDetail(
                    code=ErrorCode.READ_TIMEOUT,
                    message="Read timed out waiting for server response",
                    stage="http",
                    retryable=True,
                ),
            )
        except (httpx.ConnectError, socket.gaierror) as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return RawFetchResult(
                final_url=url,
                status_code=0,
                html="",
                method="http",
                duration_ms=duration_ms,
                error=ScraperErrorDetail(
                    code=ErrorCode.DNS_ERROR,
                    message=f"Connection or DNS resolution failure: {str(e)}",
                    stage="http",
                    retryable=True,
                ),
            )
        except (ssl.SSLError, httpx.ProtocolError) as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return RawFetchResult(
                final_url=url,
                status_code=0,
                html="",
                method="http",
                duration_ms=duration_ms,
                error=ScraperErrorDetail(
                    code=ErrorCode.TLS_ERROR,
                    message=f"TLS/SSL handshake or protocol failure: {str(e)}",
                    stage="http",
                    retryable=False,
                ),
            )
        except httpx.ProxyError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            is_auth = "407" in str(e)
            return RawFetchResult(
                final_url=url,
                status_code=407 if is_auth else 502,
                html="",
                method="http",
                duration_ms=duration_ms,
                error=ScraperErrorDetail(
                    code=ErrorCode.PROXY_FAILURE,
                    message=f"Proxy error: {str(e)}",
                    stage="proxy",
                    retryable=False,
                    status_code=407 if is_auth else 502,
                ),
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return RawFetchResult(
                final_url=url,
                status_code=0,
                html="",
                method="http",
                duration_ms=duration_ms,
                error=ScraperErrorDetail(
                    code=ErrorCode.UNKNOWN,
                    message=f"Unexpected acquisition error: {str(e)}",
                    stage="http",
                    retryable=False,
                ),
            )


http_fetcher = HttpFetcher()
