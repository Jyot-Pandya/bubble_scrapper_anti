# Outside Bubble: Scraper Service Integration Specification for AI Agents & Developers

**Document Purpose:** Context, API contract, and implementation guide for AI coding agents and software engineers building the **Outside Bubble** core application (Next.js, Supabase, background workers).

**Upstream Service Repository:** [https://github.com/Jyot-Pandya/bubble_scrapper_anti.git](https://github.com/Jyot-Pandya/bubble_scrapper_anti.git)

---

## 1. System Responsibility & Boundary Contract

Per **Outside Bubble Architecture Spec v1.6 (Sections 8.18, 11.3, 11.7, 12, 23)**:

### What Outside Bubble DOES NOT Do:
- ❌ Do **not** embed Playwright, Chromium, Trafilatura, Crawl4AI, or browser automation into Outside Bubble application workers or Next.js serverless functions.
- ❌ Do **not** implement custom web scrapers, proxy rotation pools, or CAPTCHA evasions in the main codebase.

### What the Scraper Service Does:
- ✅ Provides an isolated HTTP microservice and Python SDK (`packages.scraper_client`).
- ✅ Handles intelligent fetch escalation: fast HTTP + Trafilatura first, automatic escalation to Playwright Chromium with anti-bot stealth scripts when JavaScript/DOM hydration is required.
- ✅ Handles proxy rotation (Webshare datacenter/residential backbones) and dynamic ISO 3166-1 country geo-targeting.
- ✅ Enforces SSRF security boundaries (blocking loopback, private subnets, cloud metadata).
- ✅ Captures viewport and full-page visual screenshots for the **Source Reader** and **Research Dossier**.
- ✅ Emits standardized `NormalizedResponse` payloads containing clean body text, reading-optimized Markdown, discovered media, hero image detection, and fetch provenance.

---

## 2. Service Endpoints & API Contract

Base URL configuration:
- **Local Development:** `SCRAPER_SERVICE_URL="http://127.0.0.1:8000"`
- **Production (Oracle Cloud VPS):** `SCRAPER_SERVICE_URL="https://scraper.yourdomain.com"`

### Core Endpoints

| Method | Path | Description | Typical Consumer in Outside Bubble |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Read-only health check (`{"status": "ok"}`) | Worker startup probes, Docker healthchecks |
| `POST` | `/fetch` | Single URL acquisition and extraction | Manual URL imports, Research Orchestrator, ad-hoc jobs |
| `POST` | `/fetch/batch` | Bounded concurrent batch URL acquisition | Feed / RSS / GDELT / Newsletter ingestion workers |
| `GET` | `/metrics` | Telemetry (latencies, stage escalations, errors) | Observability dashboards, worker monitoring |
| `GET` | `/domains` | Domain memory (success history, preferred method) | Ingestion scheduling & routing optimizer |
| `POST`| `/cache/clear`| Clears internal TTL cache | Operational maintenance jobs |
| `GET` | `/storage/...`| Static file server for captured screenshots | Next.js Source Reader UI image embeds |

---

## 3. Client Installation & Setup

### A. Python Workers (Background Queues, Research Orchestrator)

Add the standalone client SDK to your worker dependencies:

#### `requirements.txt` or `pyproject.toml`:
```text
git+https://github.com/Jyot-Pandya/bubble_scrapper_anti.git#subdirectory=packages/scraper_client
```

#### Client Initialization:
```python
import os
from packages.scraper_client import ScraperClient, AsyncScraperClient

SCRAPER_SERVICE_URL = os.getenv("SCRAPER_SERVICE_URL", "http://127.0.0.1:8000")

# Synchronous client (single-threaded jobs / CLI scripts)
scraper_client = ScraperClient(base_url=SCRAPER_SERVICE_URL, timeout_seconds=60.0)

# Asynchronous client (asyncio workers / pgmq consumer loops)
async_scraper_client = AsyncScraperClient(base_url=SCRAPER_SERVICE_URL, timeout_seconds=60.0)
```

---

### B. TypeScript / Next.js (App Router, Server Actions, API Routes)

```typescript
// lib/scraper/client.ts
export interface ScraperRequest {
  url: string;
  mode?: "auto" | "http" | "browser";
  screenshot?: boolean;
  full_page_screenshot?: boolean;
  stealth?: boolean;
  use_proxy?: boolean;
  country?: string;
  bypass_cache?: boolean;
  timeout_ms?: number;
}

export interface ScraperResponse {
  request: { url: string };
  page: {
    final_url: string;
    canonical_url?: string;
    title?: string;
    author?: string;
    published_at?: string;
    language?: string;
    description?: string;
    text?: string;
    markdown?: string;
    html?: string;
  };
  metadata: {
    site_name?: string;
    og_title?: string;
    og_image?: string;
    json_ld: any[];
  };
  assets: {
    images: Array<{
      source_url: string;
      resolved_url: string;
      is_hero: boolean;
      width?: number;
      height?: number;
    }>;
  };
  captures: {
    screenshot_url?: string;
    full_page_screenshot_url?: string;
  };
  fetch: {
    method: "http" | "browser" | "cache";
    status_code: number;
    duration_ms: number;
    proxy_used: boolean;
    retrieved_at: string;
  };
  errors: Array<{
    code: string;
    message: string;
    stage: string;
    retryable: boolean;
  }>;
}

export async function fetchFromScraper(req: ScraperRequest): Promise<ScraperResponse> {
  const baseUrl = process.env.SCRAPER_SERVICE_URL || "http://127.0.0.1:8000";
  const res = await fetch(`${baseUrl}/fetch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mode: "auto",
      stealth: true,
      use_proxy: true,
      ...req,
    }),
  });

  if (!res.ok) {
    throw new Error(`Scraper service failed with status ${res.status}: ${await res.text()}`);
  }

  return res.json();
}
```

---

## 4. Integration Recipes for Outside Bubble Pipelines

### Recipe 1: Ingestion & Normalization Worker (Stage 1 -> Stage 2)
*Consuming newly discovered URLs from RSS, GDELT, Newsletters, or Hacker News.*

```python
# workers/ingest_worker.py
from packages.scraper_client import AsyncScraperClient

client = AsyncScraperClient(base_url=os.getenv("SCRAPER_SERVICE_URL", "http://127.0.0.1:8000"))

async def handle_fetch_content_job(job_payload: dict):
    target_url = job_payload["url"]
    
    # 1. Fetch via Scraper Service (uses fast HTTP first, auto-escalates to browser)
    response = await client.fetch(
        url=target_url,
        mode="auto",
        include_markdown=True,
        screenshot=False, # Conserve disk during bulk background ingestion
    )

    if response.errors:
        # Handle dead links, 404s, or blocked pages gracefully without crashing worker
        return {"status": "failed", "error": response.errors[0].message}

    # 2. Store Document in Supabase
    document_record = {
        "url": response.request.url,
        "canonical_url": response.page.canonical_url or response.page.final_url,
        "title": response.page.title,
        "author": response.page.author,
        "published_at": response.page.published_at,
        "body_text": response.page.text,
        "markdown": response.page.markdown,
        "site_name": response.metadata.site_name,
        "hero_image": next((img.resolved_url for img in response.assets.images if img.is_hero), None),
        "provenance": {
            "fetch_method": response.fetch.method,
            "duration_ms": response.fetch.duration_ms,
            "proxy_used": response.fetch.proxy_used,
            "retrieved_at": response.fetch.retrieved_at,
        }
    }
    
    # 3. Next pipeline steps: Embeddings (pgvector) -> Story Resolution
    await queue_embedding_and_resolution(document_record)
```

---

### Recipe 2: Research Dossier & Visual Evidence (Stage 10 & Source Reader)
*When the editor investigates a Story candidate, we must capture a visual snapshot and rich content.*

```python
# workers/research_worker.py
from packages.scraper_client import ScraperClient

client = ScraperClient(base_url=os.getenv("SCRAPER_SERVICE_URL", "http://127.0.0.1:8000"))

def acquire_research_evidence(primary_url: str) -> dict:
    # Force browser execution + stealth + viewport screenshot
    response = client.fetch(
        url=primary_url,
        mode="browser",
        screenshot=True,
        full_page_screenshot=False,
        stealth=True,
        bypass_cache=True, # Fresh evidence snapshot
    )

    # Convert relative storage path to full URL for the frontend Source Reader
    scraper_base = os.getenv("SCRAPER_SERVICE_URL", "http://127.0.0.1:8000")
    screenshot_full_url = None
    if response.captures.screenshot_url:
        screenshot_full_url = f"{scraper_base}{response.captures.screenshot_url}"

    return {
        "title": response.page.title,
        "markdown": response.page.markdown,
        "screenshot_url": screenshot_full_url,
        "retrieved_at": response.fetch.retrieved_at,
        "images": [img.resolved_url for img in response.assets.images],
    }
```

---

### Recipe 3: Strict Anti-Bot & Subculture Targets (Reddit, etc.)
*Reddit and certain forum CDNs blacklist commercial datacenter proxy subnets.*

```python
# Rule for Reddit or strict anti-bot targets:
response = client.fetch(
    url="https://www.reddit.com/r/technology/",
    mode="browser",
    stealth=True,
    use_proxy=False,  # Direct routing avoids datacenter proxy IP blocks
    screenshot=True,
)
```

---

### Recipe 4: Dynamic Geo-Targeting
*When investigating regional/local events in a specific country (e.g. Brazil, Germany, Japan).*

```python
# Route request through exit nodes in specific ISO 3166-1 country
response = client.fetch(
    url="https://local-news-outlet.br/article-123",
    country="br",
    mode="auto",
)
```

---

## 5. Output Data Mapping Table (Scraper -> Outside Bubble Database)

| Scraper Service Field (`NormalizedResponse`) | Outside Bubble Concept | Schema Table / Destination | Purpose |
| :--- | :--- | :--- | :--- |
| `page.canonical_url` / `page.final_url` | Canonical URL | `documents.canonical_url` | Global deduplication across sentinels |
| `page.title` | Title | `documents.title` | Story heading & search index |
| `page.text` | Clean Text | `documents.raw_text` | Input to Sentence Transformers / Nemotron Embeddings |
| `page.markdown` | Structured Markdown | `documents.markdown_content` | Source Reader center pane display |
| `metadata.site_name` | Source Publisher | `sources.name` | Source Graph attribution & early-signal learning |
| `metadata.published_at` | Published Timestamp | `documents.published_at` | Event timeline ordering & velocity calculation |
| `assets.images[is_hero=True]` | Hero Media Link | `stories.hero_image_url` | Radar & Episode Board visual thumbnail |
| `captures.screenshot_url` | Visual Snapshot | `evidence.screenshot_url` | Source Reader right-pane evidence preview |
| `fetch.method` & `duration_ms` | Performance Provenance | `documents.fetch_meta` JSONB | Sensor diagnostics & domain intelligence auditing |

---

## 6. Running Locally in Development

1. **Terminal 1: Start the Scraper Service**
   ```bash
   cd scrapper
   python scripts/control_scraper.py serve --port 8000
   ```
   *(Verify readiness at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs))*

2. **Terminal 2: Start Outside Bubble Application**
   ```bash
   cd outside_bubble
   # Add to .env.local:
   # SCRAPER_SERVICE_URL="http://127.0.0.1:8000"
   npm run dev # or python -m workers.main
   ```

---

## 7. Production Deployment: Oracle Cloud VPS (Always Free Tier)

When deploying to an Oracle Cloud Infrastructure (OCI) Compute Instance (ARM Ampere A1 or AMD x86_64):

### Step 1: Provision & Install Prerequisites on VPS
```bash
# Ubuntu 22.04/24.04 LTS on Oracle Cloud
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git
sudo usermod -aG docker $USER
```

### Step 2: Clone and Configure Environment
```bash
sudo git clone https://github.com/Jyot-Pandya/bubble_scrapper_anti.git /opt/scraper_service
cd /opt/scraper_service
sudo cp .env.example .env

# Edit .env with Webshare proxy credentials and configuration
sudo nano .env
```

### Step 3: Run with Docker Compose
```bash
sudo docker compose up -d --build
```
This builds and launches the container running Uvicorn + Playwright Chromium, exposing port `8000` locally and mounting `/opt/scraper_service/storage` for screenshot persistence.

### Step 4: Reverse Proxy & HTTPS via Caddy
Install Caddy for automatic Let's Encrypt SSL:
```bash
sudo apt-get install -y caddy
```

Edit `/etc/caddy/Caddyfile`:
```caddy
scraper.yourdomain.com {
    reverse_proxy 127.0.0.1:8000
}
```
Reload Caddy:
```bash
sudo systemctl reload caddy
```

### Step 5: Configure Oracle Cloud VCN Security Rules
In the Oracle Cloud Console:
- Navigate to **Networking > Virtual Cloud Networks > VCN Details > Security Lists**.
- Add an **Ingress Rule** for Port `443` (HTTPS) and Port `80` (HTTP) with Source CIDR `0.0.0.0/0`.
- Open iptables on Ubuntu if needed:
  ```bash
  sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
  sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
  sudo netfilter-persistent save
  ```

### Step 6: Connect Outside Bubble Production
In your Outside Bubble production environment (e.g. Vercel dashboard or production worker containers):
```env
SCRAPER_SERVICE_URL="https://scraper.yourdomain.com"
```

No code changes are required: switching from local development to production only requires updating the `SCRAPER_SERVICE_URL` environment variable.
