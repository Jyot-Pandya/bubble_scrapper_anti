# Observability & Domain Intelligence

Observability & Domain Intelligence provides operational insight into acquisition latencies, stage escalation distribution, per-domain success histories, and cache management.

## Sub-features

- `metrics-telemetry`: reports requests by stage (`stages.http_requests`, `stages.browser_requests`), latency percentiles (`latencies.avg_ms`, `latencies.p50_ms`, `latencies.p95_ms`), browser crashes, and error taxonomy counts.
- `domain-learning`: dynamically records success and failure history per domain to adaptively prefer browser or HTTP fetching.
- `cache-management`: supports TTL-based deduplication with geo-aware cache keys and operational clearing via `POST /cache/clear`.

## How to get to it (user POV)

- Send `GET /metrics`.
- Send `GET /domains`.
- Send `POST /cache/clear`.

## Driving it with control-scraper

Preconditions:

- Scraper service is running at `http://127.0.0.1:8000`.
- At least one fetch request has completed during this run.

- **Query service metrics.** Run `python scripts/control_scraper.py metrics --output artifacts/verification/domain-intelligence/metrics.json`. Exits with code `0`.
- **Verify metrics fields.** Inspect the JSON output. Confirms `total_requests >= 1`, `stages.http_requests >= 1`, `latencies.p50_ms` is a float or int, and `errors.browser_crashes: 0`.
- **Query domain intelligence.** Run `python scripts/control_scraper.py domains --output artifacts/verification/domain-intelligence/domains.json`. Exits with code `0`.
- **Verify domain memory.** Inspect the domains dictionary. Contains entries keyed by fetched domains (e.g. `"en.wikipedia.org"`, `"example.com"`) with `preferred_method`, `http_attempts`, and `http_success_rate`.
- **Test cache clear.** Clear cache via harness CLI: `python scripts/control_scraper.py cache-clear --output artifacts/verification/domain-intelligence/cache_clear.json`. Response returns `{"status": "cleared", "cache_entries": 0}`.

## Gotchas

- Metrics counters reset when the service restarts.
- Percentiles require at least one recorded request to compute accurately; on a fresh start before requests occur, p50 and p95 return `0.0`.
