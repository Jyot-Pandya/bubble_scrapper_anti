"""
Base fetcher definition and RawFetchResult.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict
from pydantic import BaseModel, Field

from apps.scraper_service.models.error import ScraperErrorDetail


class RawFetchResult(BaseModel):
    final_url: str
    status_code: int
    html: str
    method: str
    duration_ms: int
    screenshot_bytes: Optional[bytes] = None
    headers: Dict[str, str] = Field(default_factory=dict)
    error: Optional[ScraperErrorDetail] = None


class BaseFetcher(ABC):
    @abstractmethod
    async def fetch(
        self,
        url: str,
        timeout_ms: int = 30000,
        proxy_url: Optional[str] = None,
        **kwargs,
    ) -> RawFetchResult:
        """Executes raw acquisition."""
        pass
