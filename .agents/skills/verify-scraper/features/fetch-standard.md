# Standard HTTP Content Acquisition

Standard HTTP Content Acquisition fetches public web pages cheaply without launching a browser, extracting structured plain text, formatted Markdown, author and publication metadata, OpenGraph tags, and media asset links with deterministic quality scoring.

## Sub-features

- `fetch-http-direct`: retrieves public HTML documents via asynchronous `httpx` client with realistic browser headers.
- `extract-markdown`: converts body content into clean, reading-optimized Markdown.
- `extract-metadata`: parses title, description, language, OpenGraph, and JSON-LD schema.
- `discover-media`: discovers `<img>`, `<picture>`, `srcset`, and hero images, extracting tag-attribute dimensions without downloading raw bytes.

## How to get to it (user POV)

- Send `POST /fetch` with JSON body `{"url": "<target-url>", "mode": "auto"}`.
- Send `POST /fetch` with JSON body `{"url": "<target-url>", "mode": "http", "include_markdown": true}`.
- Call `ScraperClient.fetch(url="<target-url>")` in Python.

## Driving it with control-scraper

Preconditions:

- Scraper service is healthy at `http://127.0.0.1:8000`.
- Target URL is accessible on the public Internet (e.g. `https://en.wikipedia.org/wiki/Artificial_intelligence`).
- `python scripts/control_scraper.py doctor` reports `doctor_status: "PASS"`.

- **Execute standard fetch.** Acquire a structured article via HTTP. Run `python scripts/control_scraper.py fetch "https://en.wikipedia.org/wiki/Artificial_intelligence" --mode http --output artifacts/verification/fetch-standard/wiki_article.json`. The command exits with code `0`.
- **Verify HTTP method.** Inspect `fetch.method` in the evidence JSON. It equals `"http"` and `fetch.status_code` equals `200`.
- **Verify text and markdown.** Inspect `page.text` and `page.markdown`. The text length exceeds 1000 characters and starts with article headings rather than navigation boilerplate.
- **Verify metadata.** Inspect `metadata.site_name` and `page.title`. They accurately reflect the page publisher and topic.
- **Verify asset discovery.** Inspect `assets.images`. Contains at least one image with `resolved_url` beginning with `https://`. Dimensions (`width`, `height`) are populated when present in HTML tag attributes.
- **Verify quality confidence.** Inspect `quality.extraction_confidence`. Score is greater than `0.8` with `quality.content_detected: true`.

## Gotchas

- Calling `mode: "http"` against client-rendered SPA sites (e.g. React/Vue without SSR) returns an empty shell or low confidence score. Use `mode: "auto"` or `mode: "browser"`.
- Some sites return 403 to default python-httpx User-Agents; the scraper automatically injects realistic browser headers to prevent false rejections.
- Ensure the evidence output directory exists; `control_scraper.py` creates parent directories automatically.
