# Browser Automation & Screenshot Capture

Browser Automation executes JavaScript on dynamic web applications using a pooled headless Playwright Chromium instance, rendering client-side DOMs, waiting for target selectors, and capturing visual screenshots stored in object/local storage.

## Sub-features

- `browser-render`: renders client-side JavaScript applications and Single Page Apps (SPAs).
- `browser-stealth`: injects stealth evasion scripts and browser flags to bypass anti-bot detections (enabled by default).
- `screenshot-viewport`: captures standard 1280x800 viewport screenshot as JPEG.
- `screenshot-fullpage`: scrolls and captures full-length document canvas as JPEG.
- `selector-wait`: waits for dynamic content elements to mount before extracting DOM.

## How to get to it (user POV)

- Send `POST /fetch` with `{"url": "<url>", "mode": "browser", "screenshot": true}`.
- Send `POST /fetch` with `{"url": "<url>", "mode": "browser", "full_page_screenshot": true}`.
- Send `POST /fetch` with `{"url": "<url>", "mode": "browser", "stealth": false}` (disables stealth overrides).
- Call `ScraperClient.fetch(url="<url>", mode="browser", screenshot=True, stealth=True)`.

## Driving it with control-scraper

Preconditions:

- Scraper service is healthy with `browser_ready: true`.
- Chromium browser binaries are installed.
- Storage directory `storage/` exists and is writable.

- **Execute browser render & screenshot.** Drive a browser acquisition. Run `python scripts/control_scraper.py fetch "https://example.com" --mode browser --screenshot --output artifacts/verification/fetch-browser/browser_screenshot.json`. Exits with code `0`.
- **Verify browser provenance.** Inspect `fetch.method` in the JSON. It equals `"browser"`, and `fetch.duration_ms` reflects real browser startup and navigation.
- **Verify screenshot metadata.** Inspect `captures.screenshot_url`. It contains a non-null path ending in `.jpg` (e.g. `storage/screenshots/...jpg`).
- **Verify file existence on disk.** Check that the screenshot file referenced in `captures.screenshot_url` exists on disk and is a valid JPEG image file exceeding 10 KB.
- **Drive full-page screenshot.** Run `python scripts/control_scraper.py fetch "https://example.com" --mode browser --full-page --output artifacts/verification/fetch-browser/fullpage_screenshot.json`. Verify `captures.full_page_screenshot_url` exists.
- **Verify Python SDK parity.** Run `python scripts/control_scraper.py client-fetch "https://example.com" --screenshot --output artifacts/verification/fetch-browser/client_sdk_screenshot.json`. Verifies the client SDK receives the screenshot URL accurately.

## Gotchas

- Full-page screenshots on infinitely scrolling pages can generate excessively large images; set explicit timeouts or use viewport screenshots.
- Concurrent browser requests are bounded by `SCRAPER_BROWSER_POOL_SIZE` (default 4); queuing occurs when concurrency exceeds pool limits.
- If Playwright crashes or fails to launch, the service automatically attempts recovery; check `metrics_collector.browser_crashes` in `/metrics`.
