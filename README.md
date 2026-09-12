# Outside Bubble Scraper Service

High-performance, self-hosted web acquisition service that turns public URLs into structured content, media, screenshots, and provenance.

Designed according to `outside_bubble_scraper_service_spec.md`.

---

## 🌟 Key Features

1. **Multi-Stage Acquisition Escalation**:
   - **Stage 1 (Direct HTTP)**: Fast, non-blocking fetch via `httpx` with connection pooling, gzip/brotli, and realistic headers.
   - **Stage 2 (Enhanced Extraction)**: High-precision text and Markdown extraction using `trafilatura` with BeautifulSoup fallbacks.
   - **Stage 3 (Browser Automation)**: Real headless Chromium browser via `playwright` with context pooling, JS rendering, selector waiting, and viewport/full-page screenshot capture.
   - **Stage 4 (Proxy & Courtesy)**: Domain-level rate pacing, cooldown on HTTP 429, and optional geo-proxy routing.

2. **Security & SSRF Hardening**:
   - Comprehensive SSRF validation: strictly blocks loopback, private RFC 1918 subnets, cloud metadata endpoints (`169.254.169.254`, `metadata.google.internal`), and multicast ranges.
   - Hostname DNS pre-resolution checks.
   - Maximum response byte limits (15 MB default safeguard).
   - Only `http` and `https` allowed.

3. **Rich Media Discovery**:
   - Discovers `<img>`, `<picture>`, `srcset`, OpenGraph images, Twitter cards, JSON-LD images, and CSS background images.
   - Hero image identification based on OpenGraph priority and dimensions.
   - Filters 1x1 tracking pixels, spacers, and ad assets.
   - Optional image downloading with Pillow dimension verification and SHA-256 hashing.
   - Video and embed extraction for YouTube, Vimeo, TikTok, HTML5 `<video>`, and iframes.

4. **Deduplication, Caching & Domain Intelligence**:
   - Canonical URL and normalized URL caching (stripping `utm_*`, `fbclid`, and sorting query parameters).
   - Adaptive domain memory: learns which domains require browser rendering to skip redundant HTTP failures.
   - Thread-safe in-memory LRU TTL cache.

5. **Clean Service Boundary & Client SDK**:
   - Zero Outside Bubble intelligence logic in scraper service (generic acquisition layer only).
   - Official typed Python SDK (`ScraperClient` and `AsyncScraperClient`) in `packages/scraper_client`.

---

## 🚀 Quickstart

### 1. Running Locally with Python (Recommended for Development)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Install Playwright Chromium
playwright install chromium

# 3. Start the service (choose one):
python scripts/control_scraper.py serve --port 8000
# OR via uvicorn directly:
python -m uvicorn apps.scraper_service.main:app --host 127.0.0.1 --port 8000 --reload
```

Once started, open your browser to **[http://127.0.0.1:8000](http://127.0.0.1:8000)** (automatically redirects to the interactive Swagger UI).

### 2. Running with Docker (Requires Docker Desktop)

```bash
docker compose up -d --build
```

---

### ⚠️ Common Troubleshooting

- **"Address already in use" / Port 8000 occupied:**  
  If the scraper is already running in another terminal or background process, stop it with:
  ```bash
  python scripts/control_scraper.py teardown
  ```
- **"Docker daemon not running / pipe not found":**  
  Ensure Docker Desktop is open and started before running `docker compose`, or simply use the Python command above (`python scripts/control_scraper.py serve`).
- **Interactive Documentation:**  
  Interactive Swagger UI is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

---

## 📡 API Reference

### `POST /fetch`
Primary acquisition endpoint.

**Request Body:**
```json
{
  "url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
  "mode": "auto",
  "include_markdown": true,
  "include_html": false,
  "include_images": true,
  "download_images": false,
  "screenshot": false,
  "full_page_screenshot": false,
  "timeout_ms": 30000,
  "bypass_cache": false
}
```

**Response Format:**
```json
{
  "request": {
    "url": "https://en.wikipedia.org/wiki/Artificial_intelligence"
  },
  "page": {
    "final_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
    "canonical_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
    "title": "Artificial intelligence - Wikipedia",
    "author": null,
    "published_at": null,
    "language": "en",
    "description": "...",
    "text": "...",
    "markdown": "..."
  },
  "metadata": {
    "site_name": "Wikipedia",
    "og_title": "...",
    "og_image": "...",
    "json_ld": []
  },
  "assets": {
    "images": [
      {
        "source_url": "...",
        "resolved_url": "https://...",
        "alt": "...",
        "width": 1200,
        "height": 800,
        "is_hero": true
      }
    ],
    "videos": [],
    "embeds": []
  },
  "captures": {
    "screenshot_url": null,
    "full_page_screenshot_url": null
  },
  "fetch": {
    "method": "http",
    "status_code": 200,
    "attempts": 1,
    "duration_ms": 450,
    "retrieved_at": "2026-09-09T18:00:00Z",
    "proxy_used": false,
    "country": null
  },
  "quality": {
    "content_detected": true,
    "text_length": 15400,
    "extraction_confidence": 0.95
  },
  "errors": []
}
```

### `POST /fetch/batch`
Batch acquisition of multiple URLs with bounded concurrency (default 5, max 20).

### `GET /health`
Service health status, browser status, and cache size.

### `GET /metrics`
Detailed latency percentiles (avg, p50, p95), requests by stage (`http`, `browser`, `cache`), success rates, and errors.

### `GET /domains`
Summary of adaptive domain statistics and learned preferred methods.

---

## 🐍 Client SDK Example

```python
from packages.scraper_client import ScraperClient, AsyncScraperClient

# Synchronous
client = ScraperClient(base_url="http://localhost:8000")
result = client.fetch("https://example.com", screenshot=True)
print("Title:", result.page.title)
print("Confidence:", result.quality.extraction_confidence)
if result.captures.screenshot_url:
    print("Screenshot:", result.captures.screenshot_url)

# Asynchronous
async def run():
    async_client = AsyncScraperClient(base_url="http://localhost:8000")
    results = await async_client.fetch_batch([
        "https://example.com/1",
        "https://example.com/2"
    ], concurrency=2)
    for res in results:
        print(res.page.title)
```

---

## 🧪 Testing

Run the full automated test suite:
```bash
pytest -v
```
