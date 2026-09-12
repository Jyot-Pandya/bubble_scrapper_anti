"""
Playwright-based browser acquisition worker and context pool as specified in Section 9.
"""

import asyncio
import time
from typing import Optional

from playwright.async_api import async_playwright, Browser, Playwright, TimeoutError as PlaywrightTimeoutError

from apps.scraper_service.config import settings
from apps.scraper_service.core.metrics import metrics_collector
from apps.scraper_service.models.error import ErrorCode, ScraperErrorDetail
from apps.scraper_service.providers.fetcher.base import BaseFetcher, RawFetchResult


STEALTH_INIT_SCRIPT = """
// 1. Mask navigator.webdriver
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
});

// 2. Mock window.chrome runtime
window.chrome = {
    runtime: {},
    app: {},
    loadTimes: function() {},
    csi: function() {},
};

// 3. Mock languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en'],
});

// 4. Mock plugins
Object.defineProperty(navigator, 'plugins', {
    get: () => [
        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
        { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' },
    ],
});

// 5. Mock permissions
if (window.navigator.permissions && window.navigator.permissions.query) {
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters && parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
    );
}
"""


class BrowserFetcher(BaseFetcher):
    def __init__(self, pool_size: int = None, headless: bool = None):
        self.pool_size = pool_size or settings.browser_pool_size
        self.headless = headless if headless is not None else settings.browser_headless
        self._semaphore = asyncio.Semaphore(self.pool_size)

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._lock = asyncio.Lock()
        self._is_started = False

    async def start(self):
        async with self._lock:
            if not self._is_started:
                try:
                    self._playwright = await async_playwright().start()
                    self._browser = await self._playwright.chromium.launch(
                        headless=self.headless,
                        args=[
                            "--no-sandbox",
                            "--disable-setuid-sandbox",
                            "--disable-dev-shm-usage",
                            "--disable-accelerated-2d-canvas",
                            "--no-first-run",
                            "--no-zygote",
                            "--disable-gpu",
                            "--disable-blink-features=AutomationControlled",
                        ],
                    )
                    self._is_started = True
                except Exception as e:
                    self._is_started = False
                    raise RuntimeError(f"Failed to start Playwright browser: {str(e)}")

    async def close(self):
        async with self._lock:
            if self._browser:
                try:
                    await self._browser.close()
                except Exception:
                    pass
                self._browser = None

            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None

            self._is_started = False

    async def _ensure_browser(self) -> Browser:
        if not self._is_started or not self._browser or not self._browser.is_connected():
            if self._is_started:
                # Browser was running but disconnected or crashed
                metrics_collector.record_browser_crash()
            await self.start()
        return self._browser

    async def fetch(
        self,
        url: str,
        timeout_ms: int = 30000,
        proxy_url: Optional[str] = None,
        screenshot: bool = False,
        full_page_screenshot: bool = False,
        wait_selector: Optional[str] = None,
        wait_ms: Optional[int] = None,
        **kwargs,
    ) -> RawFetchResult:
        start_time = time.time()
        timeout = float(timeout_ms)

        await self._semaphore.acquire()
        context = None
        page = None
        try:
            browser = await self._ensure_browser()

            user_agent = settings.default_user_agent
            if kwargs.get("stealth", True) and "OutsideBubble" in user_agent:
                user_agent = user_agent.split("OutsideBubble")[0].strip()

            context_kwargs = {
                "user_agent": user_agent,
                "viewport": {
                    "width": settings.browser_viewport_width,
                    "height": settings.browser_viewport_height,
                },
                "java_script_enabled": True,
                "ignore_https_errors": True,
            }
            if proxy_url:
                from urllib.parse import urlsplit, unquote
                parsed = urlsplit(proxy_url)
                server = f"{parsed.scheme}://{parsed.hostname}"
                if parsed.port:
                    server += f":{parsed.port}"
                proxy_dict = {"server": server}
                if parsed.username:
                    proxy_dict["username"] = unquote(parsed.username)
                if parsed.password:
                    proxy_dict["password"] = unquote(parsed.password)
                context_kwargs["proxy"] = proxy_dict

            context = await browser.new_context(**context_kwargs)
            if kwargs.get("stealth", True) and settings.browser_stealth_enabled:
                await context.add_init_script(STEALTH_INIT_SCRIPT)

            page = await context.new_page()

            # Set navigation timeout
            page.set_default_navigation_timeout(timeout)
            page.set_default_timeout(timeout)

            # Navigate
            response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            try:
                await page.wait_for_load_state("networkidle", timeout=min(timeout, 5000.0))
            except Exception:
                pass

            # Optional selector wait
            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=min(timeout, 5000.0))
                except Exception:
                    pass

            # Optional delay for dynamic JS execution
            if wait_ms and wait_ms > 0:
                await asyncio.sleep(wait_ms / 1000.0)

            # Get content and final URL
            final_url = page.url
            try:
                html_content = await page.content()
            except Exception as nav_err:
                if "navigating" in str(nav_err).lower():
                    try:
                        await page.wait_for_load_state("domcontentloaded", timeout=min(timeout, 10000.0))
                    except Exception:
                        await asyncio.sleep(1.0)
                    html_content = await page.content()
                else:
                    raise
            status_code = response.status if response else 200

            # Screenshot capture if requested
            screenshot_bytes = None
            if screenshot or full_page_screenshot:
                screenshot_bytes = await page.screenshot(
                    full_page=full_page_screenshot,
                    type="jpeg",
                    quality=85,
                )

            duration_ms = int((time.time() - start_time) * 1000)

            return RawFetchResult(
                final_url=final_url,
                status_code=status_code,
                html=html_content,
                method="browser",
                duration_ms=duration_ms,
                screenshot_bytes=screenshot_bytes,
                headers=dict(response.headers) if response else {},
            )

        except PlaywrightTimeoutError:
            duration_ms = int((time.time() - start_time) * 1000)
            return RawFetchResult(
                final_url=url,
                status_code=0,
                html="",
                method="browser",
                duration_ms=duration_ms,
                error=ScraperErrorDetail(
                    code=ErrorCode.READ_TIMEOUT,
                    message="Browser page load timed out",
                    stage="browser",
                    retryable=True,
                ),
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            err_str = str(e).lower()

            if "err_name_not_resolved" in err_str or "getaddrinfo" in err_str:
                err_code = ErrorCode.DNS_ERROR
                retryable = True
            elif "err_connection_timed_out" in err_str or "timed out" in err_str:
                err_code = ErrorCode.CONNECTION_TIMEOUT
                retryable = True
            elif any(k in err_str for k in ("err_connection_refused", "err_connection_reset", "err_connection_closed")):
                err_code = ErrorCode.CONNECTION_TIMEOUT
                retryable = True
            elif any(k in err_str for k in ("err_cert_", "err_ssl_", "ssl")):
                err_code = ErrorCode.TLS_ERROR
                retryable = False
            elif any(k in err_str for k in ("target closed", "browser closed", "browser crashed", "crash")):
                metrics_collector.record_browser_crash()
                err_code = ErrorCode.BROWSER_CRASH
                retryable = True
            else:
                err_code = ErrorCode.UNKNOWN
                retryable = True

            return RawFetchResult(
                final_url=url,
                status_code=0,
                html="",
                method="browser",
                duration_ms=duration_ms,
                error=ScraperErrorDetail(
                    code=err_code,
                    message=f"Browser acquisition failure: {str(e)}",
                    stage="browser",
                    retryable=retryable,
                ),
            )
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
            if context:
                try:
                    await context.close()
                except Exception:
                    pass
            self._semaphore.release()


browser_fetcher = BrowserFetcher()
