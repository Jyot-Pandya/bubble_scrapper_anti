# Batch URL Acquisition

Batch URL Acquisition allows concurrent retrieval of multiple public web pages with bounded parallelism, per-domain rate limiting, and strict fault isolation so individual request failures never abort the wider batch.

## Sub-features

- `batch-concurrency-control`: processes requests concurrently up to configured limit (default 5, max 20).
- `batch-fault-isolation`: ensures an unhandled error on one item returns a structured error item while other URLs finish cleanly.
- `batch-rate-pacing`: respects per-domain rate limits even when multiple URLs in the batch target the same domain.

## How to get to it (user POV)

- Send `POST /fetch/batch` with body `{"requests": [{"url": "url1"}, {"url": "url2"}], "concurrency": 5}`.
- Call `AsyncScraperClient.fetch_batch(urls=[...], concurrency=5)` in Python.

## Driving it with control-scraper

Preconditions:

- Scraper service is healthy at `http://127.0.0.1:8000`.
- List of diverse target URLs (mix of fast HTTP pages and invalid/blocked targets).

- **Execute batch request.** Run `python scripts/control_scraper.py batch "https://example.com" "https://en.wikipedia.org/wiki/Web_scraping" --concurrency 2 --output artifacts/verification/fetch-batch/batch_success.json`. Exits with code `0`.
- **Verify results structure.** Inspect the top-level results array in the JSON. Total count matches input URL count (`2`), and each entry has its own `page`, `fetch`, and `quality` objects.
- **Drive fault-isolated batch.** Submit a batch containing one valid URL and one failing URL (e.g. `http://127.0.0.1:8000` which triggers SSRF block). Run `python scripts/control_scraper.py batch "https://example.com" "http://127.0.0.1" --output artifacts/verification/fetch-batch/batch_resilience.json`.
- **Verify per-item isolation.** Ensure the overall HTTP status code is `200`. The first result succeeds with `fetch.status_code: 200`, and the second result returns `errors: [{"code": "ssrf_blocked"}]` without throwing a 500 error.

## Gotchas

- Request concurrency is capped at 20 (`concurrency <= 20`); requesting higher concurrency triggers an HTTP 422 validation error.
- If all URLs belong to the same domain, per-domain rate pacing bounds concurrency to 2 simultaneous requests regardless of higher batch concurrency settings.
