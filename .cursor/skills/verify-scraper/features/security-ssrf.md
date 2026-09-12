# SSRF Security Enforcement

SSRF Security Enforcement blocks all attempts to exploit the acquisition service to probe loopback interfaces, RFC 1918 private subnets, cloud metadata endpoints, or internal infrastructure, returning structured security errors.

## Sub-features

- `ssrf-block-loopback`: rejects `localhost`, `127.0.0.1`, `[::1]`.
- `ssrf-block-metadata`: rejects AWS/GCP/Azure metadata services (`169.254.169.254`, `metadata.google.internal`).
- `ssrf-block-private-ranges`: rejects `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`.
- `ssrf-block-encoded-ips`: rejects integer (`http://2130706433/`) and hex (`http://0x7f000001/`) IP representations.
- `ssrf-block-non-http`: rejects `file://`, `ftp://`, `gopher://`, and other unsupported URI schemes.

## How to get to it (user POV)

- Send `POST /fetch` with body `{"url": "http://127.0.0.1:8000/health"}`.
- Send `POST /fetch` with body `{"url": "http://169.254.169.254/latest/meta-data/"}`.
- Send `POST /fetch` with body `{"url": "http://2130706433/"}`.

## Driving it with control-scraper

Preconditions:

- Scraper service is running with SSRF protection enabled (`SCRAPER_SSRF_PROTECTION_ENABLED=true`).

- **Test loopback block.** Run `python scripts/control_scraper.py fetch "http://127.0.0.1:8000/health" --output artifacts/verification/security-ssrf/loopback_blocked.json`. Exits with code `0` (HTTP response returned).
- **Verify structured error.** Inspect the output JSON. `errors` contains an error object with `code: "ssrf_blocked"` and `retryable: false`. No data is fetched from localhost.
- **Test cloud metadata block.** Run `python scripts/control_scraper.py fetch "http://169.254.169.254/latest/meta-data/" --output artifacts/verification/security-ssrf/metadata_blocked.json`. Verify `errors[0].code == "ssrf_blocked"`.
- **Test integer IP block.** Run `python scripts/control_scraper.py fetch "http://2130706433/" --output artifacts/verification/security-ssrf/integer_ip_blocked.json`. Verify `errors[0].code == "ssrf_blocked"`.
- **Verify DNS error differentiation.** Fetch a nonexistent public domain: `python scripts/control_scraper.py fetch "https://nonexistent-domain-xyz-99999.org" --output artifacts/verification/security-ssrf/dns_error.json`. Inspect `errors[0].code`. It must be `"dns_error"` with `retryable: true`, NOT `"ssrf_blocked"`.

## Gotchas

- SSRF checks must occur both pre-DNS (string parsing and IP checks) and post-DNS resolution (evaluating the resolved IP).
- DNS resolution failures must never be reported as SSRF blocks; they represent transient network or DNS issues and must have `retryable=True`.
