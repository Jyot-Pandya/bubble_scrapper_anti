---
name: verify-scraper
description: "Drive and verify the Outside Bubble Scraper Service API, browser automation, and client SDK end-to-end. Use whenever proving HTTP acquisition, Playwright browser rendering, screenshot capture, SSRF defenses, or client SDK behavior."
---

# Verify Scraper Service

The Outside Bubble Scraper Service is an infrastructure service providing reliable web acquisition, Playwright browser rendering, rich media extraction, screenshot capture, and SSRF security isolation. This skill defines how an agent programmatically launches the service, validates its runtime health, drives its public endpoints and Python SDK, captures proof evidence, and cleanly tears down instances.

## Launch

Start the scraper service on an isolated local port using the project verification harness:

```bash
python scripts/control_scraper.py launch --port 8000 --storage-dir storage
```

- **Readiness signal:** The harness polls `http://127.0.0.1:8000/health` with exponential backoff until it returns HTTP `200` with `status: "ok"`. The console prints:
  `[+] Service is READY and answering at http://127.0.0.1:8000!`
- **PID tracking:** The process ID is recorded in `.scraper-verify.pid`.
- **Log location:** Server stdout and stderr stream directly to `artifacts/verification/scraper_service.log`.
- **Teardown command:** Run `python scripts/control_scraper.py teardown`.

## Doctor

Before driving features or when troubleshooting, run the read-only doctor check:

```bash
python scripts/control_scraper.py doctor --url http://127.0.0.1:8000 --output artifacts/verification/doctor.json
```

A healthy instance passes with exit code `0` and outputs:
- `doctor_status: "PASS"`
- `status_code: 200`
- `browser_enabled: true`
- `service_status: "ok"`

If the doctor check fails (exit code `1`), verify whether the port is free or if Chromium dependencies are missing (`playwright install chromium`).

## Drive

Drive the service exclusively through its public HTTP API endpoints or the official Python SDK. Never call internal pipeline classes directly.

### 1. Single URL Acquisition (`POST /fetch`)
```bash
# Auto mode (HTTP with browser escalation if needed)
python scripts/control_scraper.py fetch "https://en.wikipedia.org/wiki/Artificial_intelligence" --output artifacts/verification/fetch_wiki.json

# Explicit browser rendering with viewport screenshot
python scripts/control_scraper.py fetch "https://example.com" --mode browser --screenshot --output artifacts/verification/fetch_browser.json

# Full-page screenshot capture
python scripts/control_scraper.py fetch "https://example.com" --mode browser --full-page --output artifacts/verification/fetch_fullpage.json
```

### 2. Batch URL Acquisition (`POST /fetch/batch`)
```bash
python scripts/control_scraper.py batch "https://example.com" "https://en.wikipedia.org" --concurrency 2 --output artifacts/verification/fetch_batch.json
```

### 3. Client SDK Drive (`ScraperClient`)
```bash
python scripts/control_scraper.py client-fetch "https://example.com" --screenshot --output artifacts/verification/client_fetch.json
```

### 4. Operational Telemetry & Cache (`GET /metrics`, `GET /domains`, `POST /cache/clear`)
```bash
python scripts/control_scraper.py metrics --output artifacts/verification/metrics.json
python scripts/control_scraper.py domains --output artifacts/verification/domains.json
python scripts/control_scraper.py cache-clear --output artifacts/verification/cache_clear.json
```

### 5. Proxy Rotation & Geo-Targeting
```bash
python scripts/control_scraper.py fetch "https://httpbin.org/ip" --country us --output artifacts/verification/fetch_proxy.json
```

## Evidence

Every verification run must store concrete, durable proof in `artifacts/verification/`:

- **Response JSON:** Formatted output matching the `NormalizedResponse` schema, containing:
  - `page.title`, `page.text`, `page.markdown`
  - `quality.content_detected`, `quality.extraction_confidence`
  - `fetch.method` (`"http"` or `"browser"`), `fetch.status_code`, `fetch.duration_ms`
  - `assets.images` array with resolved URLs and hero detection
- **Screenshots:** PNG/JPEG visual captures stored in `storage/` and referenced in `captures.screenshot_url`.
- **Doctor Report:** `artifacts/verification/doctor.json`.
- **Execution Log:** `artifacts/verification/scraper_service.log`.

**Proof Standards:**
1. Test through the real network surface (`http://127.0.0.1:8000/fetch` or `ScraperClient`), not internal mock handlers.
2. Verify both the HTTP response and side effects (e.g. screenshot file created on disk in `storage/`, domain intelligence updated in `/domains`).
3. For security checks, verify structured error response (`ErrorCode.SSRF_BLOCKED`) rather than generic socket timeouts.
4. Proof artifacts in `artifacts/verification/` and `storage/` must remain intact after teardown.

## Cleanup

Terminate the service cleanly:

```bash
python scripts/control_scraper.py teardown
```

- **Targeted Kill:** Terminates only the PID recorded in `.scraper-verify.pid`. Never issues blind `taskkill /IM uvicorn` or `killall python`.
- **Port Release:** Removes `.scraper-verify.pid` and releases port `8000`.
- **Artifact Preservation:** Leaves all files in `artifacts/verification/` and `storage/` untouched for post-run audit.

## Helpers

- `scripts/control_scraper.py`: Primary CLI verification harness providing `doctor`, `launch`, `teardown`, `fetch`, `batch`, `metrics`, `domains`, `cache-clear`, and `client-fetch`. Run with `--help` for all arguments.
