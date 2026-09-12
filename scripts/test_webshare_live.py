"""
Live Webshare Proxy Verification Script
Tests real egress IP, rotating gateway connectivity, and geo-targeting.
"""

import os
import sys

# Ensure repository root is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import asyncio
from apps.scraper_service.config import Settings
from apps.scraper_service.providers.proxy.webshare import WebshareProxyProvider
from apps.scraper_service.providers.fetcher.pipeline import AcquisitionPipeline
from apps.scraper_service.models.request import FetchMode, FetchRequest


async def main():
    print("=" * 60)
    print("LIVE WEBSHARE PROXY VERIFICATION")
    print("=" * 60)

    # 1. Reload settings from disk
    settings = Settings()
    username = settings.webshare_username
    password = settings.webshare_password
    host = settings.webshare_host
    port = settings.webshare_port
    proxy_url = settings.proxy_url
    provider_name = settings.proxy_provider

    print(f"Proxy Provider setting : {provider_name}")
    print(f"Webshare Host          : {host}:{port}")
    print(f"Username configured    : {'YES (' + username[:3] + '***)' if username else 'NO'}")
    print(f"Password configured    : {'YES (***)' if password else 'NO'}")
    print(f"Direct proxy_url set   : {'YES' if proxy_url else 'NO'}")
    print("-" * 60)

    if not ((username and password) or proxy_url):
        print("[ERROR] No Webshare credentials detected on disk!")
        print(f"Location checked: {os.path.join(BASE_DIR, '.env')}")
        print("Your .env file is currently 0 bytes (empty).")
        print("Please press Ctrl+S in your editor to save the .env file, then rerun.")
        sys.exit(1)

    provider = WebshareProxyProvider(
        username=username,
        password=password,
        host=host,
        port=port,
        proxy_url=proxy_url,
    )
    pipeline = AcquisitionPipeline(proxy_provider=provider)

    # Test 1: Default rotating fetch (HTTP)
    print("\n[TEST 1] Testing Default Webshare Rotating Proxy (HTTP)...")
    try:
        req1 = FetchRequest(
            url="https://api.ipify.org?format=json",
            mode=FetchMode.HTTP,
            bypass_cache=True,
        )
        resp1 = await pipeline.execute(req1)
        if resp1.errors:
            print(f"[-] Test 1 Failed: {resp1.errors[0].message} ({resp1.errors[0].code})")
        else:
            print(f"[+] Test 1 Passed! Status: {resp1.fetch.status_code}")
            print(f"    Proxy Used : {resp1.fetch.proxy_used}")
            print(f"    Response   : {resp1.page.text.strip()}")
            print(f"    Duration   : {resp1.fetch.duration_ms} ms")
    except Exception as e:
        print(f"[-] Test 1 Exception: {e}")

    # Test 2: Geo-targeted fetch (US Node)
    print("\n[TEST 2] Testing Dynamic Geo-Targeting (country='us')...")
    try:
        req2 = FetchRequest(
            url="https://ipinfo.io/json",
            mode=FetchMode.HTTP,
            country="us",
            bypass_cache=True,
        )
        resp2 = await pipeline.execute(req2)
        if resp2.errors:
            print(f"[-] Test 2 Failed: {resp2.errors[0].message} ({resp2.errors[0].code})")
        else:
            print(f"[+] Test 2 Passed! Status: {resp2.fetch.status_code}")
            print(f"    Country Tag: {resp2.fetch.country}")
            print(f"    Proxy Used : {resp2.fetch.proxy_used}")
            print(f"    Response   : {resp2.page.text.strip()[:200]}...")
            print(f"    Duration   : {resp2.fetch.duration_ms} ms")
    except Exception as e:
        print(f"[-] Test 2 Exception: {e}")

    # Test 3: Browser Fetch + Stealth through Proxy
    print("\n[TEST 3] Testing Headless Browser (Playwright) + Stealth Mode...")
    try:
        req3 = FetchRequest(
            url="https://httpbin.org/ip",
            mode=FetchMode.BROWSER,
            stealth=True,
            bypass_cache=True,
        )
        resp3 = await pipeline.execute(req3)
        if resp3.errors:
            print(f"[-] Test 3 Failed: {resp3.errors[0].message} ({resp3.errors[0].code})")
        else:
            print(f"[+] Test 3 Passed! Status: {resp3.fetch.status_code}")
            print(f"    Method     : {resp3.fetch.method}")
            print(f"    Proxy Used : {resp3.fetch.proxy_used}")
            print(f"    Response   : {resp3.page.text.strip()}")
            print(f"    Duration   : {resp3.fetch.duration_ms} ms")
    except Exception as e:
        print(f"[-] Test 3 Exception: {e}")

    print("\n" + "=" * 60)
    print("VERIFICATION RUN COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
