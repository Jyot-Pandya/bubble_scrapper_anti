"""
API route handlers for Scraper Service as specified in Section 5.
"""

import asyncio
import datetime
from typing import List
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from apps.scraper_service.config import settings
from apps.scraper_service.core.cache import acquisition_cache
from apps.scraper_service.core.domain_intelligence import domain_intelligence
from apps.scraper_service.core.metrics import metrics_collector
from apps.scraper_service.models.error import ErrorCode, ScraperErrorDetail
from apps.scraper_service.models.request import BatchFetchRequest, FetchRequest
from apps.scraper_service.models.response import NormalizedResponse, PageData, RequestEcho, FetchProvenance, QualityData
from apps.scraper_service.providers.fetcher.pipeline import pipeline

router = APIRouter()


@router.post("/fetch", response_model=NormalizedResponse, summary="Fetch and extract a single URL")
async def fetch_url(request: FetchRequest) -> NormalizedResponse:
    """
    Primary synchronous endpoint. Takes a URL and acquisition parameters,
    executes multi-stage acquisition and returns a fully normalized response.
    """
    return await pipeline.execute(request)


@router.post("/fetch/batch", response_model=List[NormalizedResponse], summary="Batch fetch multiple URLs")
async def fetch_batch(batch_request: BatchFetchRequest) -> List[NormalizedResponse]:
    """
    Batch acquisition endpoint using bounded concurrency.
    Does not launch one browser process per URL.
    """
    # Compile list of FetchRequests
    requests_to_run: List[FetchRequest] = []
    if batch_request.requests:
        requests_to_run = batch_request.requests
    elif batch_request.urls:
        for url in batch_request.urls:
            requests_to_run.append(
                FetchRequest(
                    url=url,
                    mode=batch_request.mode,
                    include_markdown=batch_request.include_markdown,
                    include_html=batch_request.include_html,
                    include_images=batch_request.include_images,
                    download_images=batch_request.download_images,
                    screenshot=batch_request.screenshot,
                    full_page_screenshot=batch_request.full_page_screenshot,
                    country=batch_request.country,
                    timeout_ms=batch_request.timeout_ms,
                    bypass_cache=batch_request.bypass_cache,
                    stealth=batch_request.stealth,
                )
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'requests' or 'urls' must be supplied in BatchFetchRequest.",
        )

    concurrency = min(batch_request.concurrency, 20)
    sem = asyncio.Semaphore(concurrency)

    async def run_with_sem(req: FetchRequest) -> NormalizedResponse:
        async with sem:
            try:
                return await pipeline.execute(req)
            except Exception as e:
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                return NormalizedResponse(
                    request=RequestEcho(url=req.url),
                    page=PageData(final_url=req.url),
                    fetch=FetchProvenance(
                        method="none",
                        duration_ms=0,
                        retrieved_at=now_iso,
                    ),
                    quality=QualityData(content_detected=False, extraction_confidence=0.0),
                    errors=[
                        ScraperErrorDetail(
                            code=ErrorCode.UNKNOWN,
                            message=f"Batch execution error: {str(e)}",
                            stage="batch",
                            retryable=True,
                        )
                    ],
                )

    results = await asyncio.gather(*(run_with_sem(r) for r in requests_to_run))
    return list(results)


@router.get("/health", summary="Health check endpoint")
async def health_check():
    """
    Returns service health, browser status, and cache size.
    """
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.version,
        "browser_enabled": settings.browser_enabled,
        "cache_entries": acquisition_cache.size(),
    }


@router.get("/metrics", summary="Observability metrics endpoint")
async def get_metrics():
    """
    Returns structured observability metrics as defined in Section 19.
    """
    return metrics_collector.get_metrics()


@router.get("/domains", summary="Domain intelligence summary")
async def get_domain_intelligence():
    """
    Returns domain history and preferred acquisition method for tracked domains.
    """
    return domain_intelligence.summary()


@router.post("/cache/clear", summary="Clear cache")
async def clear_cache():
    """
    Clears the internal acquisition cache.
    """
    acquisition_cache.clear()
    return {"status": "cleared", "cache_entries": 0}
