"""
Official Scraper Client SDK for Outside Bubble and other applications.
Provides synchronous and asynchronous clients with retry logic and full model typing.
"""

from typing import List, Optional, Union, Dict, Any
import httpx

from .exceptions import ScraperAPIError, ScraperTimeoutError, ScraperClientError
from .models import FetchMode, FetchRequest, BatchFetchRequest, NormalizedResponse


class ScraperClient:
    """
    Synchronous client for Outside Bubble Scraper Service.
    """
    def __init__(self, base_url: str = "http://localhost:8000", timeout_seconds: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_seconds

    def fetch(
        self,
        url: str,
        mode: Union[FetchMode, str] = FetchMode.AUTO,
        include_markdown: bool = True,
        include_html: bool = False,
        include_images: bool = True,
        download_images: bool = False,
        screenshot: bool = False,
        full_page_screenshot: bool = False,
        country: Optional[str] = None,
        timeout_ms: int = 30000,
        bypass_cache: bool = False,
        wait_selector: Optional[str] = None,
        wait_ms: Optional[int] = None,
        stealth: bool = True,
        use_proxy: bool = True,
    ) -> NormalizedResponse:
        req = FetchRequest(
            url=url,
            mode=FetchMode(mode) if isinstance(mode, str) else mode,
            include_markdown=include_markdown,
            include_html=include_html,
            include_images=include_images,
            download_images=download_images,
            screenshot=screenshot,
            full_page_screenshot=full_page_screenshot,
            country=country,
            timeout_ms=timeout_ms,
            bypass_cache=bypass_cache,
            wait_selector=wait_selector,
            wait_ms=wait_ms,
            stealth=stealth,
            use_proxy=use_proxy,
        )

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(f"{self.base_url}/fetch", json=req.model_dump())
                if resp.status_code != 200:
                    raise ScraperAPIError(resp.status_code, resp.text)
                return NormalizedResponse.model_validate(resp.json())
        except httpx.TimeoutException as e:
            raise ScraperTimeoutError(f"Request to scraper service timed out: {str(e)}")
        except httpx.RequestError as e:
            raise ScraperClientError(f"Scraper connection failure: {str(e)}")

    def fetch_batch(
        self,
        urls: List[str],
        mode: Union[FetchMode, str] = FetchMode.AUTO,
        concurrency: int = 5,
        include_markdown: bool = True,
        include_images: bool = True,
        screenshot: bool = False,
    ) -> List[NormalizedResponse]:
        batch_req = BatchFetchRequest(
            urls=urls,
            mode=FetchMode(mode) if isinstance(mode, str) else mode,
            concurrency=concurrency,
            include_markdown=include_markdown,
            include_images=include_images,
            screenshot=screenshot,
        )
        try:
            with httpx.Client(timeout=self.timeout * max(1, len(urls) // concurrency)) as client:
                resp = client.post(f"{self.base_url}/fetch/batch", json=batch_req.model_dump())
                if resp.status_code != 200:
                    raise ScraperAPIError(resp.status_code, resp.text)
                return [NormalizedResponse.model_validate(item) for item in resp.json()]
        except httpx.TimeoutException as e:
            raise ScraperTimeoutError(f"Batch request to scraper service timed out: {str(e)}")
        except httpx.RequestError as e:
            raise ScraperClientError(f"Scraper connection failure: {str(e)}")

    def health(self) -> Dict[str, Any]:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{self.base_url}/health")
            return resp.json()

    def metrics(self) -> Dict[str, Any]:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{self.base_url}/metrics")
            return resp.json()


class AsyncScraperClient:
    """
    Asynchronous client for Outside Bubble Scraper Service.
    """
    def __init__(self, base_url: str = "http://localhost:8000", timeout_seconds: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_seconds

    async def fetch(
        self,
        url: str,
        mode: Union[FetchMode, str] = FetchMode.AUTO,
        include_markdown: bool = True,
        include_html: bool = False,
        include_images: bool = True,
        download_images: bool = False,
        screenshot: bool = False,
        full_page_screenshot: bool = False,
        country: Optional[str] = None,
        timeout_ms: int = 30000,
        bypass_cache: bool = False,
        wait_selector: Optional[str] = None,
        wait_ms: Optional[int] = None,
        stealth: bool = True,
        use_proxy: bool = True,
    ) -> NormalizedResponse:
        req = FetchRequest(
            url=url,
            mode=FetchMode(mode) if isinstance(mode, str) else mode,
            include_markdown=include_markdown,
            include_html=include_html,
            include_images=include_images,
            download_images=download_images,
            screenshot=screenshot,
            full_page_screenshot=full_page_screenshot,
            country=country,
            timeout_ms=timeout_ms,
            bypass_cache=bypass_cache,
            wait_selector=wait_selector,
            wait_ms=wait_ms,
            stealth=stealth,
            use_proxy=use_proxy,
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/fetch", json=req.model_dump())
                if resp.status_code != 200:
                    raise ScraperAPIError(resp.status_code, resp.text)
                return NormalizedResponse.model_validate(resp.json())
        except httpx.TimeoutException as e:
            raise ScraperTimeoutError(f"Request to scraper service timed out: {str(e)}")
        except httpx.RequestError as e:
            raise ScraperClientError(f"Scraper connection failure: {str(e)}")

    async def fetch_batch(
        self,
        urls: List[str],
        mode: Union[FetchMode, str] = FetchMode.AUTO,
        concurrency: int = 5,
        include_markdown: bool = True,
        include_images: bool = True,
        screenshot: bool = False,
    ) -> List[NormalizedResponse]:
        batch_req = BatchFetchRequest(
            urls=urls,
            mode=FetchMode(mode) if isinstance(mode, str) else mode,
            concurrency=concurrency,
            include_markdown=include_markdown,
            include_images=include_images,
            screenshot=screenshot,
        )
        try:
            async with httpx.AsyncClient(timeout=self.timeout * max(1, len(urls) // concurrency)) as client:
                resp = await client.post(f"{self.base_url}/fetch/batch", json=batch_req.model_dump())
                if resp.status_code != 200:
                    raise ScraperAPIError(resp.status_code, resp.text)
                return [NormalizedResponse.model_validate(item) for item in resp.json()]
        except httpx.TimeoutException as e:
            raise ScraperTimeoutError(f"Batch request to scraper service timed out: {str(e)}")
        except httpx.RequestError as e:
            raise ScraperClientError(f"Scraper connection failure: {str(e)}")

    async def health(self) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{self.base_url}/health")
            return resp.json()

    async def metrics(self) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{self.base_url}/metrics")
            return resp.json()
