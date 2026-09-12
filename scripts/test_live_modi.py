"""
Live end-to-end test script:
Fetches Narendra Modi Wikipedia page with screenshot capture and image downloading.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Ensure repo root is in path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from apps.scraper_service.models.request import FetchMode, FetchRequest
from apps.scraper_service.providers.fetcher.pipeline import AcquisitionPipeline
from apps.scraper_service.providers.storage.local import LocalStorageProvider


async def run_test():
    storage_dir = ROOT_DIR / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage = LocalStorageProvider(base_dir=str(storage_dir))
    pipeline = AcquisitionPipeline(storage_provider=storage)

    url = "https://en.wikipedia.org/wiki/Narendra_Modi"
    print(f"[*] Starting live test against: {url}")
    print("[*] Options: mode=auto, screenshot=True, download_images=True, include_markdown=True")

    req = FetchRequest(
        url=url,
        mode=FetchMode.AUTO,
        include_markdown=True,
        include_images=True,
        download_images=True,
        screenshot=True,
    )

    start_time = time.time()
    resp = await pipeline.execute(req)
    elapsed = time.time() - start_time

    print(f"\n[+] Acquisition Complete in {elapsed:.2f}s!")
    print(f"    - Final URL: {resp.page.final_url}")
    print(f"    - Title: {resp.page.title}")
    print(f"    - Method: {resp.fetch.method}")
    print(f"    - Status: {resp.fetch.status_code}")
    print(f"    - Duration recorded: {resp.fetch.duration_ms}ms")
    print(f"    - Text Length: {resp.quality.text_length} chars")
    print(f"    - Extraction Confidence: {resp.quality.extraction_confidence}")
    print(f"    - Errors: {resp.errors}")

    # Screenshot
    print("\n--- Screenshot Verification ---")
    if resp.captures.screenshot_url:
        ss_path = ROOT_DIR / resp.captures.screenshot_url.lstrip("/")
        print(f"[+] Screenshot URL: {resp.captures.screenshot_url}")
        if ss_path.exists():
            print(f"[+] File exists on disk: {ss_path} ({ss_path.stat().st_size:,} bytes)")
        else:
            print(f"[-] Screenshot file not found at {ss_path}")
    else:
        print("[-] No screenshot captured.")

    # Discovered & Downloaded Images
    print(f"\n--- Discovered Images ({len(resp.assets.images)} total) ---")
    downloaded = [img for img in resp.assets.images if img.storage_url]
    print(f"[+] Successfully Downloaded Images: {len(downloaded)}")

    for i, img in enumerate(downloaded, 1):
        img_path = ROOT_DIR / img.storage_url.lstrip("/")
        exists = img_path.exists()
        size_str = f"{img_path.stat().st_size:,} bytes" if exists else "missing"
        hero_tag = " [HERO IMAGE]" if img.is_hero else ""
        print(f"\n    {i}. {img.alt or 'No Alt'}{hero_tag}")
        print(f"       Source: {img.source_url[:80]}...")
        print(f"       Storage Path: {img.storage_url} ({size_str})")
        print(f"       Dimensions: {img.width}x{img.height}")
        print(f"       MIME Type: {img.mime_type}")
        print(f"       SHA-256 Hash: {img.content_hash}")

    # Save evidence artifact
    out_file = ROOT_DIR / "artifacts" / "verification" / "live_test_modi.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(resp.model_dump(), indent=2), encoding="utf-8")
    print(f"\n[+] Full Response Evidence Saved to: {out_file}")

    # Clean up browser
    from apps.scraper_service.providers.fetcher.browser import browser_fetcher
    await browser_fetcher.close()


if __name__ == "__main__":
    asyncio.run(run_test())
