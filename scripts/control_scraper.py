#!/usr/bin/env python3
"""
control_scraper.py - Programmatic verification harness for Outside Bubble Scraper Service.

Drives the scraper service as an external client: launches the service, validates health (doctor),
executes single and batch acquisitions, captures visual and JSON evidence, and handles clean teardown.
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import httpx
except ImportError:
    httpx = None


DEFAULT_PORT = 8000
DEFAULT_URL = f"http://127.0.0.1:{DEFAULT_PORT}"
PID_FILE_NAME = ".scraper-verify.pid"


def get_pid_file(custom_path: Optional[str] = None) -> Path:
    if custom_path:
        return Path(custom_path)
    return Path.cwd() / PID_FILE_NAME


def run_doctor(url: str = DEFAULT_URL, output_file: Optional[str] = None) -> int:
    """Read-only health and readiness check."""
    print(f"[*] Running doctor against {url}...")
    target = f"{url.rstrip('/')}/health"
    start_time = time.time()
    try:
        if httpx:
            resp = httpx.get(target, timeout=5.0)
            status_code = resp.status_code
            data = resp.json()
        else:
            import urllib.request
            req = urllib.request.Request(target)
            with urllib.request.urlopen(req, timeout=5.0) as response:
                status_code = response.status
                data = json.loads(response.read().decode())

        latency_ms = int((time.time() - start_time) * 1000)
        is_healthy = status_code == 200 and data.get("status") == "ok"
        report = {
            "doctor_status": "PASS" if is_healthy else "FAIL",
            "url": target,
            "status_code": status_code,
            "latency_ms": latency_ms,
            "service_status": data.get("status"),
            "service_name": data.get("service"),
            "version": data.get("version"),
            "browser_enabled": data.get("browser_enabled"),
            "cache_entries": data.get("cache_entries"),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        print(f"[+] Doctor result: {report['doctor_status']} (HTTP {status_code}, {latency_ms}ms)")
        print(f"    - Service: {report['service_status']} ({report['service_name']} v{report['version']})")
        print(f"    - Browser enabled: {report['browser_enabled']}")
        print(f"    - Cache entries: {report['cache_entries']}")

        if output_file:
            out_p = Path(output_file)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(f"[+] Evidence written to: {out_p}")

        return 0 if is_healthy else 1

    except Exception as exc:
        print(f"[-] Doctor check failed: {exc}", file=sys.stderr)
        report = {
            "doctor_status": "FAIL",
            "url": target,
            "error": str(exc),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        if output_file:
            out_p = Path(output_file)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return 1


def run_launch(
    port: int = DEFAULT_PORT,
    storage_dir: Optional[str] = None,
    pid_file: Optional[str] = None,
    timeout: int = 20,
) -> int:
    """Launch scraper service in background and poll until ready."""
    p_file = get_pid_file(pid_file)
    if p_file.exists():
        try:
            old_pid = int(p_file.read_text().strip())
            print(f"[!] Found existing PID file ({old_pid}). Running doctor first...")
            if run_doctor(f"http://127.0.0.1:{port}") == 0:
                print(f"[+] Service is already running with PID {old_pid}.")
                return 0
            else:
                print(f"[*] Removing stale PID file {p_file}...")
                p_file.unlink(missing_ok=True)
        except Exception:
            p_file.unlink(missing_ok=True)

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    if storage_dir:
        env["SCRAPER_LOCAL_STORAGE_DIR"] = storage_dir

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "apps.scraper_service.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]

    print(f"[*] Launching: {' '.join(cmd)}")
    log_file = Path.cwd() / "artifacts" / "verification" / "scraper_service.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    f_log = open(log_file, "w", encoding="utf-8")

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    proc = subprocess.Popen(
        cmd,
        stdout=f_log,
        stderr=subprocess.STDOUT,
        env=env,
        creationflags=creationflags,
    )
    p_file.write_text(str(proc.pid))
    print(f"[+] Started process PID {proc.pid}, polling http://127.0.0.1:{port}/health...")

    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            print(f"[-] Process exited prematurely with code {proc.returncode}. Check {log_file}", file=sys.stderr)
            p_file.unlink(missing_ok=True)
            return 1
        try:
            if run_doctor(f"http://127.0.0.1:{port}") == 0:
                print(f"[+] Service is READY and answering at http://127.0.0.1:{port}!")
                return 0
        except Exception:
            pass
        time.sleep(1)

    print(f"[-] Timed out waiting for service to become healthy.", file=sys.stderr)
    run_teardown(pid_file)
    return 1

def run_serve(port: int = DEFAULT_PORT, storage_dir: Optional[str] = None, pid_file: Optional[str] = None) -> int:
    """Run the scraper service in the foreground (useful for daemon or container harnesses)."""
    p_file = get_pid_file(pid_file)
    p_file.write_text(str(os.getpid()))
    print(f"[+] Started scraper service in foreground (PID {os.getpid()}) on port {port}")
    if storage_dir:
        os.environ["SCRAPER_LOCAL_STORAGE_DIR"] = storage_dir
    os.environ["PYTHONUNBUFFERED"] = "1"

    import uvicorn
    from apps.scraper_service.main import app
    try:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
        return 0
    finally:
        p_file.unlink(missing_ok=True)


def run_teardown(pid_file: Optional[str] = None) -> int:
    """Tear down the running service instance using the PID file."""
    p_file = get_pid_file(pid_file)
    if not p_file.exists():
        print(f"[*] No PID file at {p_file}. Nothing to tear down.")
        return 0

    try:
        pid = int(p_file.read_text().strip())
    except Exception as exc:
        print(f"[-] Invalid PID file content: {exc}", file=sys.stderr)
        p_file.unlink(missing_ok=True)
        return 1

    print(f"[*] Terminating scraper service PID {pid}...")
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
            time.sleep(1)
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        print(f"[+] Successfully terminated PID {pid}.")
    except Exception as exc:
        print(f"[!] Process termination signal sent (may have already stopped: {exc})")
    finally:
        p_file.unlink(missing_ok=True)

    return 0


def run_fetch(
    url: str,
    base_url: str = DEFAULT_URL,
    mode: str = "auto",
    screenshot: bool = False,
    full_page_screenshot: bool = False,
    include_markdown: bool = True,
    include_html: bool = False,
    include_images: bool = True,
    download_images: bool = False,
    bypass_cache: bool = False,
    country: Optional[str] = None,
    stealth: bool = True,
    use_proxy: bool = True,
    output_file: Optional[str] = None,
) -> int:
    """Execute a single URL acquisition via POST /fetch."""
    endpoint = f"{base_url.rstrip('/')}/fetch"
    payload = {
        "url": url,
        "mode": mode,
        "include_markdown": include_markdown,
        "include_html": include_html,
        "include_images": include_images,
        "download_images": download_images,
        "screenshot": screenshot,
        "full_page_screenshot": full_page_screenshot,
        "bypass_cache": bypass_cache,
        "stealth": stealth,
        "use_proxy": use_proxy,
    }
    if country:
        payload["country"] = country

    print(f"[*] Executing POST {endpoint}")
    print(f"    Target URL: {url} (mode: {mode}, screenshot: {screenshot}, country: {country}, stealth: {stealth}, proxy: {use_proxy})")

    start_time = time.time()
    try:
        with httpx.Client(timeout=45.0) as client:
            resp = client.post(endpoint, json=payload)
        elapsed_ms = int((time.time() - start_time) * 1000)

        data = resp.json()
        page = data.get("page", {})
        fetch_meta = data.get("fetch", {})
        quality = data.get("quality", {})
        captures = data.get("captures", {})
        errors = data.get("errors", [])

        print(f"[+] Result (HTTP {resp.status_code}, {elapsed_ms}ms):")
        print(f"    - Title: {page.get('title')}")
        print(f"    - Method: {fetch_meta.get('method')}")
        print(f"    - Status: {fetch_meta.get('status_code')}")
        print(f"    - Text Length: {quality.get('text_length')} chars")
        print(f"    - Confidence: {quality.get('extraction_confidence')}")
        if fetch_meta.get("country"):
            print(f"    - Country: {fetch_meta.get('country')}")
        if fetch_meta.get("proxy_used"):
            print(f"    - Proxy Used: {fetch_meta.get('proxy_used')}")
        if captures.get("screenshot_url"):
            print(f"    - Screenshot: {captures.get('screenshot_url')}")
        if captures.get("full_page_screenshot_url"):
            print(f"    - Full Page Screenshot: {captures.get('full_page_screenshot_url')}")
        if errors:
            print(f"    - Errors: {errors}")

        if output_file:
            out_p = Path(output_file)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(json.dumps(data, indent=2), encoding="utf-8")
            print(f"[+] Saved response evidence: {out_p}")

        return 0 if resp.status_code == 200 else 1

    except Exception as exc:
        print(f"[-] Fetch failed: {exc}", file=sys.stderr)
        return 1


def run_batch(
    urls: List[str],
    base_url: str = DEFAULT_URL,
    concurrency: int = 5,
    output_file: Optional[str] = None,
) -> int:
    """Execute batch acquisition via POST /fetch/batch."""
    endpoint = f"{base_url.rstrip('/')}/fetch/batch"
    payload = {
        "requests": [{"url": u} for u in urls],
        "concurrency": concurrency,
    }

    print(f"[*] Executing POST {endpoint} with {len(urls)} URLs (concurrency={concurrency})...")
    start_time = time.time()
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(endpoint, json=payload)
        elapsed_ms = int((time.time() - start_time) * 1000)

        data = resp.json()
        results = data if isinstance(data, list) else data.get("results", [])
        print(f"[+] Batch completed (HTTP {resp.status_code}, {elapsed_ms}ms, {len(results)} items):")
        for i, item in enumerate(results, 1):
            p = item.get("page", {})
            f = item.get("fetch", {})
            errs = item.get("errors", [])
            err_msg = f" [Errors: {errs}]" if errs else ""
            print(f"    {i}. {item.get('request', {}).get('url')} -> HTTP {f.get('status_code')} via {f.get('method')} ('{p.get('title')}'){err_msg}")

        if output_file:
            out_p = Path(output_file)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(json.dumps(data, indent=2), encoding="utf-8")
            print(f"[+] Saved batch evidence: {out_p}")

        return 0 if resp.status_code == 200 else 1

    except Exception as exc:
        print(f"[-] Batch failed: {exc}", file=sys.stderr)
        return 1


def run_metrics(base_url: str = DEFAULT_URL, output_file: Optional[str] = None) -> int:
    """Query GET /metrics."""
    endpoint = f"{base_url.rstrip('/')}/metrics"
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(endpoint)
        data = resp.json()
        print(f"[+] Service Metrics (HTTP {resp.status_code}):")
        print(json.dumps(data, indent=2))
        if output_file:
            out_p = Path(output_file)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(json.dumps(data, indent=2), encoding="utf-8")
            print(f"[+] Saved metrics evidence: {out_p}")
        return 0
    except Exception as exc:
        print(f"[-] Metrics query failed: {exc}", file=sys.stderr)
        return 1


def run_domains(base_url: str = DEFAULT_URL, output_file: Optional[str] = None) -> int:
    """Query GET /domains."""
    endpoint = f"{base_url.rstrip('/')}/domains"
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(endpoint)
        data = resp.json()
        print(f"[+] Domain Intelligence (HTTP {resp.status_code}):")
        print(json.dumps(data, indent=2))
        if output_file:
            out_p = Path(output_file)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(json.dumps(data, indent=2), encoding="utf-8")
            print(f"[+] Saved domain evidence: {out_p}")
        return 0
    except Exception as exc:
        print(f"[-] Domains query failed: {exc}", file=sys.stderr)
        return 1


def run_client_sdk_fetch(
    url: str,
    base_url: str = DEFAULT_URL,
    screenshot: bool = False,
    full_page: bool = False,
    country: Optional[str] = None,
    stealth: bool = True,
    use_proxy: bool = True,
    output_file: Optional[str] = None,
) -> int:
    """Exercise packages.scraper_client ScraperClient directly."""
    print(f"[*] Testing ScraperClient SDK against {base_url}...")
    try:
        from packages.scraper_client import ScraperClient
        client = ScraperClient(base_url=base_url)
        res = client.fetch(
            url,
            screenshot=screenshot,
            full_page_screenshot=full_page,
            country=country,
            stealth=stealth,
            use_proxy=use_proxy,
        )
        print(f"[+] Client SDK Fetch Successful:")
        print(f"    - Title: {res.page.title}")
        print(f"    - Method: {res.fetch.method}")
        print(f"    - Confidence: {res.quality.extraction_confidence}")
        if res.fetch.country:
            print(f"    - Country: {res.fetch.country}")
        if res.fetch.proxy_used:
            print(f"    - Proxy Used: {res.fetch.proxy_used}")
        if res.captures.screenshot_url:
            print(f"    - Screenshot: {res.captures.screenshot_url}")
        if res.captures.full_page_screenshot_url:
            print(f"    - Full Page Screenshot: {res.captures.full_page_screenshot_url}")

        if output_file:
            out_p = Path(output_file)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(json.dumps(res.model_dump(), indent=2), encoding="utf-8")
            print(f"[+] Saved client SDK evidence: {out_p}")
        return 0
    except Exception as exc:
        print(f"[-] Client SDK test failed: {exc}", file=sys.stderr)
        return 1


def run_cache_clear(base_url: str = DEFAULT_URL, output_file: Optional[str] = None) -> int:
    """Clear acquisition cache via POST /cache/clear."""
    endpoint = f"{base_url.rstrip('/')}/cache/clear"
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(endpoint)
        data = resp.json()
        print(f"[+] Cache Cleared (HTTP {resp.status_code}): {data}")
        if output_file:
            out_p = Path(output_file)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(json.dumps(data, indent=2), encoding="utf-8")
            print(f"[+] Saved cache clear evidence: {out_p}")
        return 0 if resp.status_code == 200 else 1
    except Exception as exc:
        print(f"[-] Cache clear failed: {exc}", file=sys.stderr)
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Outside Bubble Scraper Verification Harness")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # doctor
    p_doc = subparsers.add_parser("doctor", help="Check service readiness")
    p_doc.add_argument("--url", default=DEFAULT_URL, help="Base service URL")
    p_doc.add_argument("--output", help="Path to write doctor result evidence JSON")

    # launch
    p_launch = subparsers.add_parser("launch", help="Start service in background")
    p_launch.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind")
    p_launch.add_argument("--storage-dir", help="Custom storage directory")
    p_launch.add_argument("--pid-file", help="Custom PID file path")
    p_launch.add_argument("--timeout", type=int, default=20, help="Readiness timeout in seconds")
    p_launch.add_argument("--foreground", action="store_true", help="Run in foreground instead of detached")

    # serve
    p_serve = subparsers.add_parser("serve", help="Run service in foreground")
    p_serve.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind")
    p_serve.add_argument("--storage-dir", help="Custom storage directory")
    p_serve.add_argument("--pid-file", help="Custom PID file path")

    # teardown
    p_down = subparsers.add_parser("teardown", help="Stop background service")
    p_down.add_argument("--pid-file", help="PID file path")

    # fetch
    p_fetch = subparsers.add_parser("fetch", help="Fetch a single URL")
    p_fetch.add_argument("url", help="Target URL")
    p_fetch.add_argument("--base-url", default=DEFAULT_URL, help="Service base URL")
    p_fetch.add_argument("--mode", default="auto", choices=["auto", "http", "browser"])
    p_fetch.add_argument("--screenshot", action="store_true", help="Capture viewport screenshot")
    p_fetch.add_argument("--full-page", action="store_true", help="Capture full page screenshot")
    p_fetch.add_argument("--no-markdown", action="store_true", help="Disable markdown extraction")
    p_fetch.add_argument("--html", action="store_true", help="Include raw HTML")
    p_fetch.add_argument("--download-images", action="store_true", help="Download discovered images")
    p_fetch.add_argument("--bypass-cache", action="store_true", help="Bypass cached response")
    p_fetch.add_argument("--country", help="ISO 3166-1 alpha-2 country code for proxy routing")
    p_fetch.add_argument("--no-stealth", action="store_false", dest="stealth", default=True, help="Disable stealth evasions")
    p_fetch.add_argument("--no-proxy", action="store_false", dest="use_proxy", default=True, help="Disable proxy routing (use direct connection)")
    p_fetch.add_argument("--output", help="Path to write response evidence JSON")

    # batch
    p_batch = subparsers.add_parser("batch", help="Batch fetch URLs")
    p_batch.add_argument("urls", nargs="+", help="Target URLs")
    p_batch.add_argument("--base-url", default=DEFAULT_URL, help="Service base URL")
    p_batch.add_argument("--concurrency", type=int, default=5, help="Batch concurrency limit")
    p_batch.add_argument("--output", help="Path to write batch evidence JSON")

    # metrics
    p_metrics = subparsers.add_parser("metrics", help="Query service metrics")
    p_metrics.add_argument("--base-url", default=DEFAULT_URL, help="Service base URL")
    p_metrics.add_argument("--output", help="Path to write metrics JSON")

    # domains
    p_domains = subparsers.add_parser("domains", help="Query domain intelligence")
    p_domains.add_argument("--base-url", default=DEFAULT_URL, help="Service base URL")
    p_domains.add_argument("--output", help="Path to write domain stats JSON")

    # cache-clear
    p_cache = subparsers.add_parser("cache-clear", help="Clear acquisition cache")
    p_cache.add_argument("--base-url", default=DEFAULT_URL, help="Service base URL")
    p_cache.add_argument("--output", help="Path to write cache clear JSON")

    # client-fetch
    p_client = subparsers.add_parser("client-fetch", help="Fetch via Python SDK client")
    p_client.add_argument("url", help="Target URL")
    p_client.add_argument("--base-url", default=DEFAULT_URL, help="Service base URL")
    p_client.add_argument("--screenshot", action="store_true", help="Capture screenshot")
    p_client.add_argument("--full-page", action="store_true", help="Capture full page screenshot")
    p_client.add_argument("--country", help="ISO 3166-1 country code")
    p_client.add_argument("--no-stealth", action="store_false", dest="stealth", default=True, help="Disable stealth")
    p_client.add_argument("--no-proxy", action="store_false", dest="use_proxy", default=True, help="Disable proxy routing")
    p_client.add_argument("--output", help="Path to write client response JSON")

    args = parser.parse_args()

    if args.command == "doctor":
        sys.exit(run_doctor(args.url, args.output))
    elif args.command == "launch":
        if args.foreground:
            sys.exit(run_serve(args.port, args.storage_dir, args.pid_file))
        sys.exit(run_launch(args.port, args.storage_dir, args.pid_file, args.timeout))
    elif args.command == "serve":
        sys.exit(run_serve(args.port, args.storage_dir, args.pid_file))
    elif args.command == "teardown":
        sys.exit(run_teardown(args.pid_file))
    elif args.command == "fetch":
        sys.exit(
            run_fetch(
                url=args.url,
                base_url=args.base_url,
                mode=args.mode,
                screenshot=args.screenshot,
                full_page_screenshot=args.full_page,
                include_markdown=not args.no_markdown,
                include_html=args.html,
                download_images=args.download_images,
                bypass_cache=args.bypass_cache,
                country=args.country,
                stealth=args.stealth,
                use_proxy=args.use_proxy,
                output_file=args.output,
            )
        )
    elif args.command == "batch":
        sys.exit(run_batch(args.urls, args.base_url, args.concurrency, args.output))
    elif args.command == "metrics":
        sys.exit(run_metrics(args.base_url, args.output))
    elif args.command == "domains":
        sys.exit(run_domains(args.base_url, args.output))
    elif args.command == "cache-clear":
        sys.exit(run_cache_clear(args.base_url, args.output))
    elif args.command == "client-fetch":
        sys.exit(
            run_client_sdk_fetch(
                url=args.url,
                base_url=args.base_url,
                screenshot=args.screenshot,
                full_page=args.full_page,
                country=args.country,
                stealth=args.stealth,
                use_proxy=args.use_proxy,
                output_file=args.output,
            )
        )


if __name__ == "__main__":
    main()
