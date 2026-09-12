"""
Per-domain rate limiter and courtesy pacing engine as required by Section 17.
"""

import asyncio
import time
from urllib.parse import urlparse
from typing import Dict, Tuple


class DomainRateLimiter:
    def __init__(
        self,
        global_concurrency: int = 20,
        domain_concurrency: int = 2,
        domain_min_interval: float = 0.5,
        domain_cooldown: float = 60.0,
    ):
        self.global_concurrency = global_concurrency
        self.domain_concurrency = domain_concurrency
        self.domain_min_interval = domain_min_interval
        self.domain_cooldown = domain_cooldown

        self._global_semaphore = asyncio.Semaphore(global_concurrency)
        self._domain_semaphores: Dict[str, asyncio.Semaphore] = {}
        self._domain_last_request: Dict[str, float] = {}
        self._domain_cooldown_until: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    def _extract_domain(self, domain_or_url: str) -> str:
        domain_or_url = (domain_or_url or "").strip()
        if not domain_or_url:
            return "default"
        try:
            if "://" not in domain_or_url and not domain_or_url.startswith("//"):
                domain_or_url = "https://" + domain_or_url
            netloc = urlparse(domain_or_url).netloc.lower()
            return netloc.split(":")[0] or "default"
        except Exception:
            return "default"

    async def get_domain_semaphore(self, domain: str) -> asyncio.Semaphore:
        clean_domain = self._extract_domain(domain)
        async with self._lock:
            if clean_domain not in self._domain_semaphores:
                self._domain_semaphores[clean_domain] = asyncio.Semaphore(self.domain_concurrency)
            return self._domain_semaphores[clean_domain]

    def is_in_cooldown(self, domain_or_url: str) -> Tuple[bool, float]:
        """Returns (in_cooldown, remaining_seconds)."""
        domain = self._extract_domain(domain_or_url)
        cooldown_until = self._domain_cooldown_until.get(domain, 0.0)
        now = time.time()
        if cooldown_until > now:
            return True, cooldown_until - now
        return False, 0.0

    def trigger_cooldown(self, domain_or_url: str, duration: float = None):
        """Puts a domain into cooldown following 429 or severe rate limiting."""
        domain = self._extract_domain(domain_or_url)
        if duration is None:
            duration = self.domain_cooldown
        self._domain_cooldown_until[domain] = time.time() + duration

    async def acquire(self, url: str):
        """
        Acquires both global and per-domain execution permits,
        enforcing domain cooldown and min-interval pacing.
        """
        domain = self._extract_domain(url)

        # Check cooldown
        in_cooldown, remaining = self.is_in_cooldown(domain)
        if in_cooldown:
            raise RuntimeError(f"Domain '{domain}' is in rate-limit cooldown for {remaining:.1f}s")

        # Acquire global semaphore
        await self._global_semaphore.acquire()

        try:
            # Acquire domain semaphore
            domain_sem = await self.get_domain_semaphore(domain)
            await domain_sem.acquire()
        except Exception:
            self._global_semaphore.release()
            raise


        # Enforce minimum delay between requests to same domain
        async with self._lock:
            last_req = self._domain_last_request.get(domain, 0.0)
            elapsed = time.time() - last_req
            if elapsed < self.domain_min_interval:
                delay = self.domain_min_interval - elapsed
            else:
                delay = 0.0

        if delay > 0:
            await asyncio.sleep(delay)

        async with self._lock:
            self._domain_last_request[domain] = time.time()

    def release(self, url: str):
        """Releases the per-domain and global execution permits."""
        domain = self._extract_domain(url)
        if domain in self._domain_semaphores:
            try:
                self._domain_semaphores[domain].release()
            except ValueError:
                pass
        try:
            self._global_semaphore.release()
        except ValueError:
            pass


rate_limiter = DomainRateLimiter()
