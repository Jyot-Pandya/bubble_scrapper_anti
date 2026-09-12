"""
Outside Bubble Scraper Client Package.
"""

from .client import ScraperClient, AsyncScraperClient
from .exceptions import ScraperClientError, ScraperAPIError, ScraperTimeoutError
from .models import (
    FetchMode,
    FetchRequest,
    BatchFetchRequest,
    NormalizedResponse,
    PageData,
    Metadata,
    AssetData,
    CapturesData,
    FetchProvenance,
    QualityData,
    ImageData,
    VideoData,
    EmbedData,
    ErrorCode,
    ScraperErrorDetail,
)

__all__ = [
    "ScraperClient",
    "AsyncScraperClient",
    "ScraperClientError",
    "ScraperAPIError",
    "ScraperTimeoutError",
    "FetchMode",
    "FetchRequest",
    "BatchFetchRequest",
    "NormalizedResponse",
    "PageData",
    "Metadata",
    "AssetData",
    "CapturesData",
    "FetchProvenance",
    "QualityData",
    "ImageData",
    "VideoData",
    "EmbedData",
    "ErrorCode",
    "ScraperErrorDetail",
]
