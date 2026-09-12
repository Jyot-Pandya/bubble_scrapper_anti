"""
Deduplication and in-memory TTL caching as specified in Section 16.
"""

import hashlib
import time
from collections import OrderedDict
from typing import Optional, Any
from apps.scraper_service.core.security import normalize_url


class CacheEntry:
    def __init__(self, data: Any, ttl: int, content_hash: Optional[str] = None):
        self.data = data
        self.expires_at = time.time() + ttl
        self.created_at = time.time()
        self.content_hash = content_hash

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class AcquisitionCache:
    def __init__(self, max_entries: int = 1000, default_ttl: int = 3600):
        self.max_entries = max_entries
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()

    def _make_key(self, url: str, country: Optional[str] = None) -> str:
        norm = normalize_url(url)
        raw = f"{norm}:country={country.strip().lower()}" if country else norm
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, url: str, country: Optional[str] = None) -> Optional[Any]:
        key = self._make_key(url, country)
        entry = self._cache.get(key)
        if not entry:
            return None

        if entry.is_expired():
            del self._cache[key]
            return None

        # Move to end for LRU
        self._cache.move_to_end(key)
        return entry.data

    def set(
        self,
        url: str,
        data: Any,
        ttl: Optional[int] = None,
        content_hash: Optional[str] = None,
        country: Optional[str] = None,
    ):
        key = self._make_key(url, country)
        if ttl is None:
            ttl = self.default_ttl

        # Evict oldest if full
        if len(self._cache) >= self.max_entries and key not in self._cache:
            self._cache.popitem(last=False)

        self._cache[key] = CacheEntry(data, ttl, content_hash)
        self._cache.move_to_end(key)

    def clear(self):
        self._cache.clear()

    def size(self) -> int:
        return len(self._cache)


acquisition_cache = AcquisitionCache()
