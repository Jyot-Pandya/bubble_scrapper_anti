"""
Integration tests for BrowserFetcher using Playwright.
"""

import pytest
from apps.scraper_service.providers.fetcher.browser import BrowserFetcher


@pytest.mark.asyncio
async def test_playwright_browser_fetch_and_screenshot():
    fetcher = BrowserFetcher(pool_size=1, headless=True)
    try:
        await fetcher.start()
        data_url = "data:text/html,<html><head><title>Test Page</title></head><body><h1>Playwright Rendered</h1><p>Dynamic content</p></body></html>"

        result = await fetcher.fetch(
            url=data_url,
            timeout_ms=10000,
            screenshot=True,
        )

        assert result.status_code == 200
        assert "Playwright Rendered" in result.html
        assert result.method == "browser"
        assert result.screenshot_bytes is not None
        assert len(result.screenshot_bytes) > 100  # valid image bytes
    finally:
        await fetcher.close()


@pytest.mark.asyncio
async def test_playwright_stealth_evasions():
    """
    Test that Playwright applies stealth evasions (matching ScrapingBee's stealth mode):
    - Masks navigator.webdriver (returns undefined)
    - Injects window.chrome runtime object
    - Populates navigator.languages and plugins
    """
    fetcher = BrowserFetcher(pool_size=1, headless=True)
    try:
        await fetcher.start()
        test_html = """
        <!DOCTYPE html>
        <html>
        <head><title>Stealth Test</title></head>
        <body>
            <div id="res"></div>
            <script>
                const data = {
                    webdriver: navigator.webdriver,
                    hasChrome: !!window.chrome,
                    hasPlugins: navigator.plugins.length > 0
                };
                document.getElementById('res').innerText = JSON.stringify(data);
            </script>
        </body>
        </html>
        """
        import urllib.parse
        data_url = f"data:text/html,{urllib.parse.quote(test_html)}"

        result = await fetcher.fetch(url=data_url, timeout_ms=10000, stealth=True)
        assert result.status_code == 200
        # In JSON.stringify, undefined values are omitted entirely:
        assert '{"hasChrome":true,"hasPlugins":true}' in result.html
    finally:
        await fetcher.close()
