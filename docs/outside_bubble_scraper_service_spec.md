# Outside Bubble Scraper Service
## Builder Specification — v1.0

> Purpose: build a reusable, self-hosted web acquisition service that reliably turns a public URL into structured content, media, screenshots, and provenance for Outside Bubble and future projects.

This service is **not** the Outside Bubble intelligence engine. It is a separate infrastructure service.

Its job is simple:

```text
URL
↓
reliable acquisition
↓
render if needed
↓
extract useful content
↓
collect images/media
↓
capture screenshot if requested
↓
return normalized result + provenance
```

The service must remain generic. It must know nothing about Outside Bubble concepts such as Stories, Worlds, rankings, clusters, or editorial scoring.

---

# 1. Core Principles

1. **Own the acquisition layer, not the whole web stack.** Use mature libraries for extraction and browser automation.
2. **Escalate only when necessary.** Most pages should be fetched cheaply without launching a browser.
3. **Do not depend on paid scraping APIs.** The service must operate in zero-cost mode except for VPS/network/proxy costs the operator intentionally enables.
4. **Paid providers are optional adapters.** The system may later add ScrapingBee, Apify, TinyFish, Browserless, etc., but none are required.
5. **Do not bypass authentication, CAPTCHAs, paywalls, or private areas.** If a page is inaccessible, return a structured failure.
6. **Preserve provenance.** Every result must include when, where, and how it was fetched.
7. **Images and visual evidence are first-class outputs.** The service must support screenshots and discovered page images from the beginning.
8. **The scraper must be reusable outside Outside Bubble.** Design a generic HTTP API and client package.

---

# 2. Recommended Technology

## Service language

**Python**

Reason:
- Crawl4AI
- Trafilatura
- Playwright
- BeautifulSoup/lxml
- image-processing ecosystem
- easy async HTTP support

## API framework

**FastAPI**

## HTTP client

**httpx**

## Primary extraction

**Trafilatura**

Use for:
- standard articles
- blogs
- news pages
- text-heavy webpages

## Rich/difficult extraction

**Crawl4AI**

Use when:
- page structure is unusual
- Markdown extraction is valuable
- JS rendering is needed
- normal extraction quality is poor

## Browser fallback

**Playwright + installed Google Chrome/Chromium**

Use only when:
- page requires JavaScript
- static HTTP output is incomplete
- content appears only after browser execution
- screenshot is requested

## HTML parsing

- lxml
- BeautifulSoup only when needed

## Image metadata

- Pillow
- optional perceptual hashing library

## Optional future queue

Do not require a separate queue for the first version.

Add one only if concurrency/load requires it.

Possible options later:
- Supabase Queues
- Redis + RQ
- Celery
- Dramatiq

---

# 3. Deployment Model

The preferred architecture is:

```text
Outside Bubble / other clients
            ↓
        HTTP API
            ↓
     Scraper Service
            ↓
 ┌──────────┼─────────────┐
 │          │             │
HTTP     Extractor      Browser
 │          │             │
httpx   Trafilatura    Playwright
            │             │
            └──────┬──────┘
                   ↓
           normalized result
```

Run the scraper on a VPS/container environment where a real browser can run.

Recommended initial deployment:

```text
Docker
+
Python/FastAPI
+
Google Chrome
+
Playwright
+
Trafilatura
+
Crawl4AI
```

Frontend hosting such as Vercel is unrelated to this service.

---

# 4. Repository Boundary

Preferred structure:

```text
/apps
  /outside-bubble
  /scraper-service

/packages
  /scraper-client
  /shared-types
```

If kept in separate repositories, preserve the same service boundary.

The important rule:

> Outside Bubble must call the scraper through a defined API/client rather than importing internal scraper implementation code.

---

# 5. Public API

## `POST /fetch`

Primary synchronous endpoint.

Example request:

```json
{
  "url": "https://example.com/article",
  "mode": "auto",
  "include_markdown": true,
  "include_html": false,
  "include_images": true,
  "download_images": false,
  "screenshot": false,
  "full_page_screenshot": false,
  "country": null,
  "timeout_ms": 30000
}
```

### Supported modes

```text
auto
http
browser
```

`auto` is the normal mode.

The caller should almost never need to know which internal strategy is used.

## `POST /fetch/batch`

Accept multiple URLs.

Use bounded concurrency.

Do not launch one browser process per URL.

## Optional future endpoints

```text
POST /jobs
GET  /jobs/{id}
GET  /health
GET  /metrics
```

Only add async job APIs when bulk volume requires them.

---

# 6. Normalized Response

The response should look conceptually like:

```json
{
  "request": {
    "url": "https://example.com/article"
  },
  "page": {
    "final_url": "https://example.com/article",
    "canonical_url": "https://example.com/article",
    "title": "...",
    "author": "...",
    "published_at": "...",
    "language": "en",
    "description": "...",
    "text": "...",
    "markdown": "..."
  },
  "metadata": {
    "site_name": "...",
    "og_title": "...",
    "og_description": "...",
    "og_image": "...",
    "json_ld": {}
  },
  "assets": {
    "images": [],
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
    "duration_ms": 820,
    "retrieved_at": "...",
    "proxy_used": false,
    "country": null
  },
  "quality": {
    "content_detected": true,
    "text_length": 4820,
    "extraction_confidence": 0.94
  },
  "errors": []
}
```

Do not expose internal secrets, cookies, proxy credentials, or browser profile data.

---

# 7. Acquisition Escalation

This is the heart of the service.

Use the cheapest reliable path first.

```text
URL
 ↓
Stage 1 — direct HTTP fetch
 ↓
good page?
 ├─ yes → extract → return
 └─ no
      ↓
Stage 2 — Crawl4AI/static enhanced extraction
      ↓
good page?
 ├─ yes → return
 └─ no
      ↓
Stage 3 — browser rendering
      ↓
good page?
 ├─ yes → return
 └─ no
      ↓
Stage 4 — optional proxy/browser strategy
      ↓
success or structured failure
```

The exact escalation decision should use heuristics, not only HTTP status codes.

Possible failure signals:

```text
403 / 429 / 503
very short body
known block-page markers
JS-only shell
empty article body
login wall
CAPTCHA
bot-detection interstitial
unexpected redirect
```

If the response is a CAPTCHA, paywall, login wall, or explicitly restricted content, stop and report the condition rather than trying to defeat it.

---

# 8. HTTP Fetcher

The HTTP fetcher should:

- use persistent connections
- support redirects
- support gzip/brotli
- set realistic but transparent HTTP headers
- enforce per-domain pacing
- cache recent successful fetches
- limit response size
- handle charset detection
- reject unsupported/binary payloads unless explicitly requested

The HTTP fetcher should be the default path because it is:

- fastest
- cheapest
- easiest to scale
- least resource-intensive

---

# 9. Browser Worker

Do not create a new browser process for every request.

Use:

```text
Browser Process
    ↓
Browser Context Pool
    ↓
Pages/Tabs
```

Requirements:

- bounded concurrency
- context reuse where appropriate
- periodic context recycling
- request timeout
- page timeout
- memory safeguards
- browser crash recovery
- domain-aware pacing
- optional persistent profiles

Persistent profiles are useful for sites that behave better across repeated sessions.

However:

> Persistent profiles must never contain personal user sessions or credentials unless explicitly configured by the operator for a legitimate use.

---

# 10. Proxy Layer

Proxies are **optional**, not required.

The system must work without proxy configuration.

Create a generic proxy adapter:

```text
ProxyProvider
  get_proxy(country?)
  report_success()
  report_failure()
```

Possible future providers:

- operator-owned residential/static proxies
- datacenter proxies
- commercial proxy APIs
- region-specific proxies

Do not hard-code one vendor.

The service should track proxy health:

```text
success rate
latency
recent failures
region
bandwidth usage
blocked domains
```

Country targeting should be optional.

Example:

```json
{
  "url": "...",
  "country": "br"
}
```

If no matching proxy exists, return a clear capability warning rather than silently pretending geo-targeting occurred.

---

# 11. Image Extraction

Images are first-class outputs.

Discover:

```text
<img src>
<img srcset>
<picture>
OpenGraph image
Twitter card image
JSON-LD image
linked hero images
relevant CSS background images where practical
```

For every image store/return metadata such as:

```text
source URL
resolved absolute URL
alt text
title
width
height
mime type
DOM context
position in article
source page
```

Filter obvious noise where possible:

```text
1x1 pixels
tiny icons
tracking pixels
logos repeated many times
avatars if irrelevant
spacers
ad-tech assets
```

Do not aggressively remove media at extraction time.

Outside Bubble may later decide an image is editorially useful.

---

# 12. Image Downloading

Default:

```text
discover image URLs
do not download all of them
```

Downloading every discovered image wastes bandwidth/storage.

Support:

```text
download_images = true
```

or selective policies such as:

```text
download hero image
download images above minimum dimensions
download top N article images
```

Downloaded media should go to object storage.

Recommended:

**Cloudflare R2**

Store:

```text
original image
content hash
mime type
source URL
retrieved timestamp
```

Never lose provenance.

---

# 13. Screenshots

Support:

```text
viewport screenshot
full-page screenshot
specific-element screenshot (future)
```

Screenshots are especially useful for:

- social posts
- leaderboards
- launch pages
- company statements
- charts
- unusual websites
- pages likely to change
- visual evidence for YouTube research

Only invoke a browser when screenshot functionality is requested.

Screenshots should be uploaded to R2 and returned as object URLs/keys.

---

# 14. Video and Embed Discovery

The service does not need to download video initially.

Discover and return:

```text
video URLs
YouTube embeds
Vimeo embeds
TikTok embeds
iframe sources
poster images
HTML5 video sources
```

Outside Bubble can later decide whether to process them.

---

# 15. Content Extraction Quality

Every extraction should receive a quality score.

Possible signals:

```text
title exists
main text length
paragraph count
text-to-markup ratio
duplicate navigation ratio
article metadata exists
publication date exists
author exists
known block-page markers absent
```

Example:

```text
confidence > 0.8
→ accept

0.4–0.8
→ consider escalation

< 0.4
→ escalate/fail
```

Do not use an LLM for the basic quality decision unless necessary.

Use deterministic heuristics first.

---

# 16. Deduplication and Caching

Before expensive rendering:

```text
URL normalization
canonical URL lookup
recent cache lookup
content hash lookup
```

Useful cache keys:

```text
normalized URL
final URL
content hash
ETag
Last-Modified
```

Support configurable cache TTL.

Example defaults:

```text
news article: hours
static documentation: days
homepages/trend pages: minutes
```

Outside Bubble can bypass cache when fresh evidence is required.

---

# 17. Rate Limiting and Domain Courtesy

Maintain per-domain controls:

```text
requests per minute
minimum delay
max concurrent requests
cooldown after 429
cooldown after repeated failures
```

Global concurrency and domain concurrency must be separate.

Example:

```text
global concurrency: 20
per-domain concurrency: 1–2
```

Configuration should be adjustable without code changes.

---

# 18. Error Taxonomy

Never return only `"failed"`.

Use structured reasons:

```text
dns_error
connection_timeout
read_timeout
tls_error
blocked
rate_limited
captcha
login_required
paywall
robots_restricted
unsupported_content
empty_content
browser_crash
proxy_failure
geo_unavailable
extraction_failed
unknown
```

This is critical because Outside Bubble needs to know whether to retry, use another source, or stop.

---

# 19. Observability

Track at minimum:

```text
requests
success rate
failure rate
success by domain
success by acquisition stage
HTTP-only success %
browser escalation %
proxy escalation %
average latency
p95 latency
bytes downloaded
browser crashes
CAPTCHA/block frequency
image count
screenshot count
```

Add structured logs.

Useful future stack:

- Prometheus/Grafana
- OpenTelemetry
- Sentry

Do not make them mandatory for v1.

---

# 20. Domain Intelligence

Maintain lightweight domain-level history.

Example:

```text
example.com
preferred_method: http
http_success_rate: 99%

another-site.com
preferred_method: browser
http_success_rate: 2%
browser_success_rate: 93%
```

After enough history, skip clearly useless stages.

Example:

```text
if domain repeatedly requires browser:
    start with browser
```

This turns the system into an adaptive fetcher over time.

---

# 21. Provider Architecture

All external integrations must be adapters.

Example:

```text
Fetcher
├── HttpFetcher
├── BrowserFetcher
├── Crawl4AIFetcher
└── ExternalFetcherAdapter (optional)

ProxyProvider
├── NoProxy
├── ResidentialProvider
└── CommercialProvider

StorageProvider
├── LocalFilesystem
└── R2Storage
```

Do not scatter provider-specific logic across the codebase.

---

# 22. Security

Requirements:

- validate URLs
- prevent SSRF
- block private/internal IP ranges by default
- limit maximum response sizes
- limit redirects
- sanitize filenames
- never expose credentials
- isolate browser workers
- enforce request timeouts
- restrict `file://` and unsupported URI schemes
- log security-relevant failures

Important:

```text
http://localhost
http://127.0.0.1
http://169.254.169.254
internal network hosts
```

must not be fetchable by arbitrary callers.

---

# 23. Storage Strategy

Do not use PostgreSQL as blob storage.

### Database / structured metadata

Outside Bubble stores:

```text
result metadata
source relationships
story relationships
hashes
object keys
timestamps
```

### R2

Store:

```text
raw HTML when preserved
screenshots
downloaded images
large extraction artifacts
optional PDFs
```

The scraper itself should be able to run statelessly.

---

# 24. Outside Bubble Integration

Outside Bubble should use a small client package.

Example conceptual interface:

```python
result = scraper.fetch(
    url=url,
    include_images=True,
    screenshot=False,
)
```

Outside Bubble then handles:

```text
Story assignment
entity extraction
LLM enrichment
clustering
signals
ranking
research
editorial decisions
```

The scraper must **never**:

```text
decide if a story is important
assign Worlds
score virality
cluster stories
generate editorial summaries
decide what goes into a YouTube episode
```

Those are Outside Bubble responsibilities.

---

# 25. When Outside Bubble Should Call the Scraper

### Source ingestion

```text
RSS item discovered
↓
fetch article URL
↓
extract content
```

### Search expansion

```text
interesting entity discovered
↓
search API finds 15 URLs
↓
scraper fetches those URLs
```

### Research dossier

```text
story selected
↓
fetch best primary/local sources
↓
extract text + media
```

### Preservation

```text
important/volatile page
↓
capture screenshot
↓
save raw HTML
```

---

# 26. LLM Usage

The scraper does **not need an LLM for normal operation**.

LLMs belong primarily in Outside Bubble.

Possible future optional scraper use:

```text
unusual DOM extraction
schema inference
visual understanding
complex content cleanup
```

But these should not be required for normal fetching.

Pipeline:

```text
Scraper
→ deterministic content extraction
→ Outside Bubble
→ LLM enrichment
```

This keeps scraping cheap and predictable.

---

# 27. What Not to Build

Do not build:

- a custom browser engine
- a custom HTML rendering engine
- a full anti-bot research platform
- CAPTCHA solvers
- login bypassing
- paywall bypassing
- a proprietary proxy network
- a full ScrapingBee feature clone
- a search engine
- a Story/recommendation system inside the scraper

The goal is a **high-quality internal fetch service**, not a general commercial scraping platform.

---

# 28. Implementation Order

## Phase 1 — Core HTTP service

Build:

```text
FastAPI
POST /fetch
httpx
Trafilatura
normalized response
URL validation
timeouts
error taxonomy
```

Exit condition:

> Most normal news/blog URLs return high-quality text and metadata.

## Phase 2 — Browser fallback

Add:

```text
Playwright
Chrome
browser pool
JS rendering
browser escalation
screenshots
```

Exit condition:

> JS-heavy pages can be fetched reliably without one browser process per request.

## Phase 3 — Crawl4AI

Add Crawl4AI where it improves:

```text
Markdown
structured extraction
dynamic pages
complex HTML
```

It should remain one implementation inside the acquisition engine, not define the API.

## Phase 4 — Media

Add:

```text
image discovery
metadata
image filtering
optional downloads
R2 storage
screenshots
video/embed discovery
```

## Phase 5 — Reliability

Add:

```text
domain history
adaptive acquisition
cache
retry policy
rate limiting
metrics
browser recovery
```

## Phase 6 — Optional proxy support

Add generic proxy-provider architecture.

No proxy provider should be required.

## Phase 7 — Batch/async workloads

Only if Outside Bubble needs higher throughput:

```text
batch API
job queue
worker scaling
priority jobs
```

---

# 29. Acceptance Criteria

The first production-ready version should satisfy:

### Standard pages
- fetch and extract common news/blog pages reliably
- produce clean text and Markdown
- extract title/date/author where available

### Dynamic pages
- automatically escalate to browser mode when needed

### Media
- discover page images
- identify hero/OpenGraph images
- optionally download selected images
- capture screenshots

### Reliability
- retries are bounded
- per-domain rate limiting works
- browser workers recover from crashes
- structured failure reasons are returned

### Security
- SSRF protection exists
- internal/private network access is blocked
- request/response limits are enforced

### Integration
- Outside Bubble can consume the service through one stable client/API
- no Outside Bubble business logic exists inside the scraper

### Cost
- service works without any paid scraping API
- proxy use is optional
- normal HTTP fetches remain the default path

---

# 30. Performance Targets

Initial targets, not hard guarantees:

```text
HTTP-only fetch
p50 < 2s

Browser fetch
p50 < 10s

ordinary pages handled without browser
> 70%

successful public-page acquisition across curated sources
> 90% target over time
```

These targets should be measured on the actual Outside Bubble source set, not synthetic benchmarks.

---

# 31. Future Capabilities

Possible future additions:

- regional proxy routing
- domain-specific fetch recipes
- browser profile pools
- PDF extraction
- OCR for image-only documents
- WARC preservation
- ArchiveBox integration
- DOM snapshotting
- content-change diffing
- scheduled monitoring
- external scraping-provider fallback
- multi-VPS worker pool
- internal admin dashboard

None are required for the first production version.

---

# 32. Final Architectural Rule

The scraper is a **reliable acquisition layer**, not an intelligence product.

Keep the boundary:

```text
SCRAPER SERVICE

URL
→ retrieve
→ render
→ extract
→ capture
→ return


OUTSIDE BUBBLE

sources
→ understand
→ cluster
→ detect anomalies
→ rank
→ research
→ editorialize
```

If this boundary remains clean, the scraper can later support:

- Outside Bubble
- other internal projects
- research tools
- monitoring systems
- future SaaS products

without rewriting it.
