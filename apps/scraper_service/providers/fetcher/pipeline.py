"""
Acquisition Escalation Pipeline as specified in Section 7.
Coordinates HTTP fetching, browser escalation, extraction, media discovery,
caching, domain intelligence, and metrics.
"""

import base64
import datetime
import re
import time
from typing import Optional, List

from apps.scraper_service.config import settings
from apps.scraper_service.core.cache import acquisition_cache
from apps.scraper_service.core.domain_intelligence import domain_intelligence
from apps.scraper_service.core.metrics import metrics_collector
from apps.scraper_service.core.quality import quality_evaluator
from apps.scraper_service.core.rate_limiter import rate_limiter
from apps.scraper_service.core.security import validate_url_security, normalize_url
from apps.scraper_service.extractors.content import content_extractor
from apps.scraper_service.extractors.embeds import embed_extractor
from apps.scraper_service.extractors.media import media_extractor
from apps.scraper_service.models.error import ErrorCode, ScraperErrorDetail
from apps.scraper_service.models.request import FetchMode, FetchRequest
from apps.scraper_service.models.response import (
    AssetData,
    CapturesData,
    FetchProvenance,
    NormalizedResponse,
    PageData,
    QualityData,
    RequestEcho,
)
from apps.scraper_service.providers.fetcher.base import RawFetchResult
from apps.scraper_service.providers.fetcher.browser import browser_fetcher
from apps.scraper_service.providers.fetcher.http import http_fetcher
from apps.scraper_service.providers.proxy.base import BaseProxyProvider
from apps.scraper_service.providers.proxy.memory import NoProxyProvider, StaticProxyProvider
from apps.scraper_service.providers.proxy.webshare import WebshareProxyProvider
from apps.scraper_service.providers.storage.base import BaseStorageProvider
from apps.scraper_service.providers.storage.local import LocalStorageProvider


class AcquisitionPipeline:
    def __init__(
        self,
        storage_provider: Optional[BaseStorageProvider] = None,
        proxy_provider: Optional[BaseProxyProvider] = None,
    ):
        self.storage_provider = storage_provider or LocalStorageProvider(settings.local_storage_dir)
        if proxy_provider:
            self.proxy_provider = proxy_provider
        elif settings.proxy_provider == "webshare" or (settings.webshare_username and settings.webshare_password):
            self.proxy_provider = WebshareProxyProvider(
                username=settings.webshare_username,
                password=settings.webshare_password,
                host=settings.webshare_host,
                port=settings.webshare_port,
                proxy_url=settings.proxy_url,
            )
        elif settings.proxy_url:
            self.proxy_provider = StaticProxyProvider(default_proxy_url=settings.proxy_url)
        else:
            self.proxy_provider = NoProxyProvider()

    async def execute(self, req: FetchRequest) -> NormalizedResponse:
        start_time = time.time()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        errors: List[ScraperErrorDetail] = []
        target_url = req.url.strip()

        # 1. Security & SSRF Validation
        if settings.ssrf_protection_enabled:
            is_safe, sec_error = validate_url_security(target_url, set(settings.allowed_schemes))
            if not is_safe:
                is_dns_error = "DNS resolution failed" in sec_error or "Could not resolve host" in sec_error
                err_code = ErrorCode.DNS_ERROR if is_dns_error else ErrorCode.SSRF_BLOCKED
                err_stage = "dns" if is_dns_error else "security"
                err_message = f"DNS resolution failure: {sec_error}" if is_dns_error else f"SSRF policy violation: {sec_error}"

                err = ScraperErrorDetail(
                    code=err_code,
                    message=err_message,
                    stage=err_stage,
                    retryable=is_dns_error,
                )
                metrics_collector.record_request(err_stage, False, int((time.time() - start_time) * 1000), err.code)
                return NormalizedResponse(
                    request=RequestEcho(url=target_url),
                    page=PageData(final_url=target_url),
                    fetch=FetchProvenance(
                        method="none",
                        duration_ms=int((time.time() - start_time) * 1000),
                        retrieved_at=now_iso,
                    ),
                    quality=QualityData(content_detected=False, extraction_confidence=0.0),
                    errors=[err],
                )

        # 2. Cache check
        if settings.cache_enabled and not req.bypass_cache:
            cached_resp = acquisition_cache.get(target_url, country=req.country)
            if cached_resp:
                # Return cached response with updated fetch info
                cached_resp_copy = cached_resp.model_copy(deep=True)
                cached_resp_copy.fetch.method = "cache"
                cached_resp_copy.fetch.duration_ms = int((time.time() - start_time) * 1000)
                cached_resp_copy.fetch.country = req.country
                metrics_collector.record_request("cache", True, cached_resp_copy.fetch.duration_ms)
                return cached_resp_copy

        # 3. Proxy resolution (default rotating proxy or geo-targeted proxy)
        proxy_url = None
        if req.use_proxy:
            proxy_url, geo_err = self.proxy_provider.get_proxy(req.country)
            if geo_err:
                err = ScraperErrorDetail(
                    code=ErrorCode.GEO_UNAVAILABLE,
                    message=geo_err,
                    stage="proxy",
                    retryable=False,
                )
                return NormalizedResponse(
                    request=RequestEcho(url=target_url),
                    page=PageData(final_url=target_url),
                    fetch=FetchProvenance(
                        method="proxy",
                        duration_ms=int((time.time() - start_time) * 1000),
                        retrieved_at=now_iso,
                        country=req.country,
                        proxy_used=False,
                    ),
                    quality=QualityData(content_detected=False, extraction_confidence=0.0),
                    errors=[err],
                )

        # 4. Courtesy Rate Limiting
        try:
            await rate_limiter.acquire(target_url)
        except RuntimeError as e:
            err = ScraperErrorDetail(
                code=ErrorCode.RATE_LIMITED,
                message=str(e),
                stage="rate_limit",
                retryable=True,
                status_code=429,
            )
            return NormalizedResponse(
                request=RequestEcho(url=target_url),
                page=PageData(final_url=target_url),
                fetch=FetchProvenance(
                    method="rate_limit",
                    duration_ms=int((time.time() - start_time) * 1000),
                    retrieved_at=now_iso,
                ),
                quality=QualityData(content_detected=False, extraction_confidence=0.0),
                errors=[err],
            )

        raw_result: Optional[RawFetchResult] = None
        attempts = 0
        try:
            # 5. Determine initial acquisition stage
            should_use_browser = (
                req.mode == FetchMode.BROWSER
                or req.screenshot
                or req.full_page_screenshot
                or (
                    settings.adaptive_enabled
                    and req.mode == FetchMode.AUTO
                    and domain_intelligence.get_preferred_method(target_url) == "browser"
                )
            )

            # Stage 1: HTTP fetch (if browser not forced)
            if not should_use_browser and req.mode != FetchMode.BROWSER:
                attempts += 1
                raw_result = await http_fetcher.fetch(
                    url=target_url,
                    timeout_ms=req.timeout_ms,
                    proxy_url=proxy_url,
                )

                if raw_result.status_code == 429:
                    rate_limiter.trigger_cooldown(target_url)

                # Check if access was restricted (CAPTCHA, Login wall, Paywall)
                clean_text_len = len(re.sub(r"<[^>]+>", " ", raw_result.html or "").strip())
                restriction = quality_evaluator.detect_access_restriction(raw_result.html, raw_result.status_code, text_len=clean_text_len)
                if restriction in (ErrorCode.CAPTCHA, ErrorCode.PAYWALL, ErrorCode.LOGIN_REQUIRED):
                    errors.append(
                        ScraperErrorDetail(
                            code=restriction,
                            message=f"Access restriction detected: {restriction.value}",
                            stage="http",
                            retryable=False,
                            status_code=raw_result.status_code,
                        )
                    )
                    # Stop here, do not bypass walls
                    return await self._build_response(
                        req=req,
                        raw_result=raw_result,
                        attempts=attempts,
                        start_time=start_time,
                        now_iso=now_iso,
                        errors=errors,
                        is_blocked=True,
                        proxy_used=bool(proxy_url),
                    )

                # Check escalation conditions for AUTO mode:
                # - HTTP failed (403, 503, connection error)
                # - JS-only empty shell
                # - Very short unrendered page
                needs_escalation = False
                if req.mode == FetchMode.AUTO and settings.browser_enabled:
                    if raw_result.error and raw_result.error.retryable:
                        needs_escalation = True
                    elif raw_result.status_code in (403, 503):
                        needs_escalation = True
                    elif quality_evaluator.is_js_shell(raw_result.html):
                        needs_escalation = True

                if needs_escalation:
                    # Escalate to browser
                    should_use_browser = True

            # Stage 2: Browser rendering (if initiated or escalated)
            if should_use_browser and settings.browser_enabled:
                attempts += 1
                browser_result = await browser_fetcher.fetch(
                    url=target_url,
                    timeout_ms=req.timeout_ms,
                    proxy_url=proxy_url,
                    screenshot=req.screenshot,
                    full_page_screenshot=req.full_page_screenshot,
                    wait_selector=req.wait_selector,
                    wait_ms=req.wait_ms,
                    stealth=req.stealth,
                )
                raw_result = browser_result

                # Check restrictions after browser render
                clean_text_len = len(re.sub(r"<[^>]+>", " ", raw_result.html or "").strip())
                restriction = quality_evaluator.detect_access_restriction(raw_result.html, raw_result.status_code, text_len=clean_text_len)
                if restriction in (ErrorCode.CAPTCHA, ErrorCode.PAYWALL, ErrorCode.LOGIN_REQUIRED):
                    errors.append(
                        ScraperErrorDetail(
                            code=restriction,
                            message=f"Access restriction detected: {restriction.value}",
                            stage="browser",
                            retryable=False,
                            status_code=raw_result.status_code,
                        )
                    )

            if not raw_result:
                raw_result = RawFetchResult(
                    final_url=target_url,
                    status_code=0,
                    html="",
                    method="none",
                    duration_ms=int((time.time() - start_time) * 1000),
                    error=ScraperErrorDetail(
                        code=ErrorCode.UNKNOWN,
                        message="Acquisition could not be executed",
                        stage="pipeline",
                        retryable=False,
                    ),
                )

            if raw_result.error:
                errors.append(raw_result.error)

            return await self._build_response(
                req=req,
                raw_result=raw_result,
                attempts=attempts,
                start_time=start_time,
                now_iso=now_iso,
                errors=errors,
                proxy_used=bool(proxy_url),
            )

        finally:
            rate_limiter.release(target_url)

    async def _build_response(
        self,
        req: FetchRequest,
        raw_result: RawFetchResult,
        attempts: int,
        start_time: float,
        now_iso: str,
        errors: List[ScraperErrorDetail],
        is_blocked: bool = False,
        proxy_used: bool = False,
    ) -> NormalizedResponse:
        duration_ms = int((time.time() - start_time) * 1000)
        final_url = raw_result.final_url or req.url

        # Extract content & metadata
        page_data, metadata = content_extractor.extract(
            html=raw_result.html,
            url=final_url,
            include_markdown=req.include_markdown,
            include_html=req.include_html,
        )

        # Discover assets
        images = []
        if req.include_images and raw_result.html:
            images = media_extractor.discover_images(raw_result.html, final_url, metadata)
            if req.download_images and self.storage_provider:
                images = await media_extractor.download_images(images, self.storage_provider)

        videos, embeds = ([], [])
        if raw_result.html:
            videos, embeds = embed_extractor.discover(raw_result.html, final_url)

        assets = AssetData(images=images, videos=videos, embeds=embeds)

        # Handle screenshot
        captures = CapturesData()
        if raw_result.screenshot_bytes:
            metrics_collector.record_request("capture", True, 0, screenshot_captured=True)
            if self.storage_provider:
                key = f"screenshots/{int(time.time())}_{abs(hash(final_url)) % 100000}.jpg"
                storage_url = await self.storage_provider.save(key, raw_result.screenshot_bytes, "image/jpeg")
                if req.full_page_screenshot:
                    captures.full_page_screenshot_url = storage_url
                else:
                    captures.screenshot_url = storage_url
            else:
                b64_data = base64.b64encode(raw_result.screenshot_bytes).decode("utf-8")
                captures.screenshot_data = f"data:image/jpeg;base64,{b64_data}"

        # Evaluate quality
        confidence, factors = quality_evaluator.score_extraction(
            title=page_data.title,
            text=page_data.text,
            author=page_data.author,
            published_at=page_data.published_at,
            html=raw_result.html,
            is_blocked=is_blocked or bool(errors and any(e.code in (ErrorCode.BLOCKED, ErrorCode.CAPTCHA) for e in errors)),
        )

        content_detected = confidence >= 0.25 and bool(page_data.text and len(page_data.text.strip()) > 50)
        quality = QualityData(
            content_detected=content_detected,
            text_length=len(page_data.text or ""),
            extraction_confidence=confidence,
            details=factors,
        )

        # Provenance
        fetch_provenance = FetchProvenance(
            method=raw_result.method,
            status_code=raw_result.status_code,
            attempts=attempts,
            duration_ms=duration_ms,
            retrieved_at=now_iso,
            proxy_used=proxy_used,
            country=req.country,
        )

        # Update intelligence and metrics
        success = (raw_result.status_code in (200, 201, 204) or raw_result.status_code == 0) and not errors
        domain_intelligence.record_result(req.url, raw_result.method, success, duration_ms)

        error_code_str = errors[0].code.value if errors else None
        metrics_collector.record_request(
            stage=raw_result.method,
            success=success,
            duration_ms=duration_ms,
            error_code=error_code_str,
            bytes_count=len(raw_result.html.encode("utf-8")),
            images_count=len(images),
        )

        response = NormalizedResponse(
            request=RequestEcho(url=req.url),
            page=page_data,
            metadata=metadata,
            assets=assets,
            captures=captures,
            fetch=fetch_provenance,
            quality=quality,
            errors=errors,
        )

        # Cache if successful and good quality
        if settings.cache_enabled and success and confidence >= 0.4:
            acquisition_cache.set(req.url, response, ttl=settings.cache_ttl_seconds, country=req.country)

        return response


pipeline = AcquisitionPipeline()
