# Scraper Service Verification Map

This directory is the maintained source for verifying the user-facing behavior of the Outside Bubble Scraper Service. Read the index before driving the app, then use the matching feature file as the recipe.

## Baseline preconditions

- Launch the Scraper Service at `http://127.0.0.1:8000` using `python scripts/control_scraper.py launch`.
- Ensure Chromium dependencies are present (`playwright install chromium`).
- Set storage directory to `storage/` or a dedicated test directory (`SCRAPER_LOCAL_STORAGE_DIR=storage`).
- Run `python scripts/control_scraper.py doctor` and require `doctor_status: "PASS"` and `browser_ready: true`.
- Never drive an instance that was not started by this verification run or when the port belongs to an untracked process.

## Driving conventions

- Start every recipe from the baseline healthy state unless preconditions specify otherwise.
- Drive the service exclusively through HTTP requests (`POST /fetch`, `POST /fetch/batch`, `GET /health`, `GET /metrics`, `GET /domains`) or via the `ScraperClient` SDK.
- Treat every command as literal. Keep JSON payloads and parameter flags unchanged.
- Execute commands via `python scripts/control_scraper.py <command>`.
- Proof artifacts must be directed to `artifacts/verification/<feature-name>/`.
- Cleanup operations must terminate the service PID cleanly and preserve generated proof artifacts.

## Proof and skip reporting

- Capture both the request configuration and the resulting normalized response body.
- Content extraction proof must record `page.title`, `page.text` (non-empty), `page.markdown`, and `quality.extraction_confidence >= 0.7`.
- Browser capture proof must record both the response JSON (`captures.screenshot_url`) and the verified image file on disk in `storage/`.
- Security proof must verify structured error taxonomy `ErrorCode.SSRF_BLOCKED` (`"ssrf_blocked"`), `retryable=False`, and zero network egress to blocked subnets.
- Batch proof must record all items completing, with individual failures isolated without aborting peer tasks.
- Record the feature ID and entry point used with every artifact.
- Never report a skipped test or synthetic mock as a verified user journey.

## Feature entry contract

Each feature file starts with an H1 title and one paragraph describing the user-visible behavior. It then uses exactly four H2 sections in this order:

1. `Sub-features` lists short IDs with one line for each behavior.
2. `How to get to it (user POV)` lists every user entry point.
3. `Driving it with <harness>` starts with `Preconditions:` and uses labeled bullets that pair each user action with an exact command and observable result.
4. `Gotchas` lists traps that can waste or invalidate a verification run.

Keep internal implementation details out of the map. Name only user paths, stable parameters, required state, commands, and observable proof.

## Features

- [Standard HTTP Content Acquisition](./fetch-standard.md) covers direct HTTP fetching, Markdown extraction, metadata, and media discovery.
- [Browser Automation & Screenshot Capture](./fetch-browser-screenshot.md) covers headless Chromium execution, JS rendering, selector waiting, and full-page visual captures.
- [Batch URL Acquisition](./fetch-batch.md) covers bounded concurrent fetching, per-task exception isolation, and batch throughput.
- [SSRF Security Enforcement](./security-ssrf.md) covers loopback, private subnet, cloud metadata, and encoded IP blocking.
- [Observability & Domain Intelligence](./domain-intelligence-metrics.md) covers `/metrics`, `/domains`, adaptive preferred-method switching, and cache controls.
- [Proxy Rotation & Geo-Targeting (Webshare)](./proxy-webshare.md) covers automatic IP rotation, ISO 3166-1 country geo-targeting, and residential gateway routing via Webshare.
