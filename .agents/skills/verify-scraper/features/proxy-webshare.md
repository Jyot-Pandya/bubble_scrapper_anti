# Proxy Rotation & Geo-Targeting (Webshare)

Webshare Proxy Provider provides automatic IP rotation on every request, residential or datacenter proxy backbones, and ISO 3166-1 two-letter country geo-targeting for bypassing rate limits and accessing localized content.

## Sub-features

- `proxy-ip-rotation`: automatically appends `-rotate` to rotate exit IP address per connection.
- `proxy-geo-targeting`: appends `-country-<cc>` to route requests through proxies in a specific ISO 3166-1 country.
- `proxy-residential-gateway`: switches routing between datacenter (`p.webshare.io`) and residential (`rp.webshare.io`) backbones via configuration.
- `proxy-failover-isolation`: rejects invalid 2-letter country codes with structured error without dispatching requests.

## How to get to it (user POV)

- Send `POST /fetch` with body `{"url": "<url>", "country": "us"}`.
- Send `POST /fetch` with body `{"url": "<url>", "proxy_url": "http://user:pass@p.webshare.io:80"}`.
- Call `ScraperClient.fetch(url="<url>", country="us")` in Python.

## Driving it with control-scraper

Preconditions:

- Scraper service is running at `http://127.0.0.1:8000`.
- Webshare credentials (`SCRAPER_WEBSHARE_USERNAME`, `SCRAPER_WEBSHARE_PASSWORD`) are configured in `.env` or passed via proxy URL.

- **Test IP rotation.** Execute `python scripts/control_scraper.py fetch "https://httpbin.org/ip" --mode http --output artifacts/verification/proxy-webshare/ip_rotation.json`. Exits with code `0`. Verify `fetch.status_code: 200`.
- **Test geo-targeting.** Run `python scripts/control_scraper.py fetch "https://httpbin.org/ip" --country us --output artifacts/verification/proxy-webshare/geo_us.json`. Exits with code `0`.
- **Verify country code validation.** Run `python scripts/control_scraper.py fetch "https://httpbin.org/ip" --country invalid_code --output artifacts/verification/proxy-webshare/invalid_country.json`. Inspect `errors`. Returns structured error for invalid country code without crashing.

## Gotchas

- If Webshare credentials are not configured in environment, supplying a `country` parameter returns an error response indicating credentials are required.
- Country code must be a 2-letter alphabetic string (e.g. `us`, `de`, `gb`). Any other format is rejected prior to dispatch.
- Proxy rotation applies to both HTTP requests and Playwright browser contexts.
