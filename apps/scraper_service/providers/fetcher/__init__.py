from apps.scraper_service.providers.fetcher.base import BaseFetcher, RawFetchResult
from apps.scraper_service.providers.fetcher.http import http_fetcher, HttpFetcher
from apps.scraper_service.providers.fetcher.browser import browser_fetcher, BrowserFetcher
from apps.scraper_service.providers.fetcher.pipeline import pipeline, AcquisitionPipeline

__all__ = [
    "BaseFetcher",
    "RawFetchResult",
    "http_fetcher",
    "HttpFetcher",
    "browser_fetcher",
    "BrowserFetcher",
    "pipeline",
    "AcquisitionPipeline",
]
