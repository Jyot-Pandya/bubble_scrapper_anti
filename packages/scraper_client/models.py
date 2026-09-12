"""
Shared type definitions and models for Outside Bubble Scraper Client SDK.
Provides full Pydantic models for type safety without dependency on backend service code.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ErrorCode(str, Enum):
    DNS_ERROR = "dns_error"
    CONNECTION_TIMEOUT = "connection_timeout"
    READ_TIMEOUT = "read_timeout"
    TLS_ERROR = "tls_error"
    BLOCKED = "blocked"
    RATE_LIMITED = "rate_limited"
    CAPTCHA = "captcha"
    LOGIN_REQUIRED = "login_required"
    PAYWALL = "paywall"
    ROBOTS_RESTRICTED = "robots_restricted"
    UNSUPPORTED_CONTENT = "unsupported_content"
    EMPTY_CONTENT = "empty_content"
    BROWSER_CRASH = "browser_crash"
    PROXY_FAILURE = "proxy_failure"
    GEO_UNAVAILABLE = "geo_unavailable"
    EXTRACTION_FAILED = "extraction_failed"
    SSRF_BLOCKED = "ssrf_blocked"
    UNKNOWN = "unknown"


class ScraperErrorDetail(BaseModel):
    code: ErrorCode = Field(..., description="Standardized taxonomy error code")
    message: str = Field(..., description="Human-readable error description")
    stage: str = Field("unknown", description="Acquisition stage where error occurred")
    retryable: bool = Field(False, description="Whether this request could succeed on retry")
    status_code: Optional[int] = Field(None, description="HTTP status code if available")


class FetchMode(str, Enum):
    AUTO = "auto"
    HTTP = "http"
    BROWSER = "browser"


class FetchRequest(BaseModel):
    url: str = Field(..., description="Target public URL to acquire and extract")
    mode: FetchMode = Field(FetchMode.AUTO, description="Acquisition mode: auto, http, or browser")
    include_markdown: bool = Field(True, description="Whether to include structured markdown in output")
    include_html: bool = Field(False, description="Whether to include raw HTML in output")
    include_images: bool = Field(True, description="Whether to discover and extract image metadata")
    download_images: bool = Field(False, description="Whether to download discovered images to storage")
    screenshot: bool = Field(False, description="Whether to capture a viewport screenshot")
    full_page_screenshot: bool = Field(False, description="Whether to capture a full-page screenshot")
    country: Optional[str] = Field(None, description="Optional ISO 3166-1 alpha-2 country code for geo-proxy routing")
    timeout_ms: int = Field(30000, ge=1000, le=120000, description="Request timeout in milliseconds")
    bypass_cache: bool = Field(False, description="Bypass the cache and force a fresh acquisition")
    wait_selector: Optional[str] = Field(None, description="Optional CSS selector to wait for in browser mode")
    wait_ms: Optional[int] = Field(None, ge=0, le=15000, description="Optional delay in ms to wait for dynamic scripts")
    stealth: bool = Field(True, description="Enable browser stealth anti-detection evasions (masks webdriver, chrome runtime, plugins)")
    use_proxy: bool = Field(True, description="Whether to route request through configured proxy provider")


class BatchFetchRequest(BaseModel):
    requests: Optional[List[FetchRequest]] = Field(None, description="Detailed list of fetch requests")
    urls: Optional[List[str]] = Field(None, description="Simple list of URLs using default settings")
    mode: FetchMode = Field(FetchMode.AUTO, description="Default mode if urls list provided")
    include_markdown: bool = Field(True, description="Default markdown setting if urls list provided")
    include_html: bool = Field(False, description="Default html setting if urls list provided")
    include_images: bool = Field(True, description="Default images setting if urls list provided")
    download_images: bool = Field(False, description="Default download images setting if urls list provided")
    screenshot: bool = Field(False, description="Default screenshot setting if urls list provided")
    full_page_screenshot: bool = Field(False, description="Default full page screenshot setting if urls list provided")
    country: Optional[str] = Field(None, description="Default country setting if urls list provided")
    timeout_ms: int = Field(30000, description="Default timeout setting if urls list provided")
    bypass_cache: bool = Field(False, description="Default bypass cache setting if urls list provided")
    stealth: bool = Field(True, description="Default stealth mode setting if urls list provided")
    use_proxy: bool = Field(True, description="Default proxy setting if urls list provided")
    concurrency: int = Field(5, ge=1, le=20, description="Max concurrent requests in batch")


class RequestEcho(BaseModel):
    url: str = Field(..., description="The original requested URL")


class PageData(BaseModel):
    final_url: str = Field(..., description="Final URL after following all redirects")
    canonical_url: Optional[str] = Field(None, description="Canonical URL from link[rel=canonical]")
    title: Optional[str] = Field(None, description="Extracted article or document title")
    author: Optional[str] = Field(None, description="Extracted author or creator")
    published_at: Optional[str] = Field(None, description="Publication timestamp in ISO 8601 or raw format")
    language: Optional[str] = Field(None, description="Detected or declared document language")
    description: Optional[str] = Field(None, description="Document summary or meta description")
    text: Optional[str] = Field(None, description="Extracted clean body text without boilerplate")
    markdown: Optional[str] = Field(None, description="Extracted structured markdown content")
    html: Optional[str] = Field(None, description="Raw HTML if requested")


class Metadata(BaseModel):
    site_name: Optional[str] = Field(None, description="Website brand or publisher name")
    og_title: Optional[str] = Field(None, description="og:title meta tag content")
    og_description: Optional[str] = Field(None, description="og:description meta tag content")
    og_image: Optional[str] = Field(None, description="og:image meta tag content")
    twitter_card: Optional[str] = Field(None, description="twitter:card meta tag content")
    twitter_title: Optional[str] = Field(None, description="twitter:title meta tag content")
    twitter_description: Optional[str] = Field(None, description="twitter:description meta tag content")
    twitter_image: Optional[str] = Field(None, description="twitter:image meta tag content")
    json_ld: List[Dict[str, Any]] = Field(default_factory=list, description="Extracted JSON-LD structured data")


class ImageData(BaseModel):
    source_url: str = Field(..., description="Source URL as found in HTML")
    resolved_url: str = Field(..., description="Fully resolved absolute URL")
    alt: Optional[str] = Field(None, description="Image alt text")
    title: Optional[str] = Field(None, description="Image title attribute")
    width: Optional[int] = Field(None, description="Width in pixels")
    height: Optional[int] = Field(None, description="Height in pixels")
    mime_type: Optional[str] = Field(None, description="Image MIME type")
    dom_context: Optional[str] = Field(None, description="Parent element tag (e.g., article, header, figure)")
    position: int = Field(0, description="Order of appearance in DOM")
    is_hero: bool = Field(False, description="Flag indicating high likelihood of being primary hero image")
    storage_url: Optional[str] = Field(None, description="Storage object URL if download was requested")
    content_hash: Optional[str] = Field(None, description="SHA-256 hash if downloaded")


class VideoData(BaseModel):
    source_url: str = Field(..., description="Source video or embed URL")
    resolved_url: str = Field(..., description="Fully resolved absolute URL")
    type: str = Field("unknown", description="Video type: youtube, vimeo, tiktok, html5, iframe")
    poster_url: Optional[str] = Field(None, description="Poster image URL")
    title: Optional[str] = Field(None, description="Video title if available")


class EmbedData(BaseModel):
    type: str = Field(..., description="Embed type: iframe, audio, widget")
    src: Optional[str] = Field(None, description="Source URL")
    html: Optional[str] = Field(None, description="Embed HTML snippet")


class AssetData(BaseModel):
    images: List[ImageData] = Field(default_factory=list, description="Discovered page images")
    videos: List[VideoData] = Field(default_factory=list, description="Discovered videos and video embeds")
    embeds: List[EmbedData] = Field(default_factory=list, description="Discovered external embeds")


class CapturesData(BaseModel):
    screenshot_url: Optional[str] = Field(None, description="Storage or data URL for viewport screenshot")
    full_page_screenshot_url: Optional[str] = Field(None, description="Storage or data URL for full-page screenshot")
    screenshot_data: Optional[str] = Field(None, description="Base64 data or key if returned directly")


class FetchProvenance(BaseModel):
    method: str = Field(..., description="Acquisition method: http, browser, crawl4ai, or cache")
    status_code: Optional[int] = Field(None, description="HTTP response status code")
    attempts: int = Field(1, description="Number of attempts or escalations executed")
    duration_ms: int = Field(..., description="Total execution time in milliseconds")
    retrieved_at: str = Field(..., description="Timestamp of acquisition in ISO 8601")
    proxy_used: bool = Field(False, description="Whether a proxy was used")
    country: Optional[str] = Field(None, description="Target or exit country code")


class QualityData(BaseModel):
    content_detected: bool = Field(..., description="Whether meaningful article content was detected")
    text_length: int = Field(0, description="Length of extracted body text in characters")
    extraction_confidence: float = Field(0.0, ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    details: Optional[Dict[str, Any]] = Field(None, description="Detailed heuristic signals")


class NormalizedResponse(BaseModel):
    request: RequestEcho = Field(..., description="Original request details")
    page: PageData = Field(..., description="Extracted page text and core metadata")
    metadata: Metadata = Field(default_factory=Metadata, description="Social and semantic metadata")
    assets: AssetData = Field(default_factory=AssetData, description="Discovered assets (images, videos, embeds)")
    captures: CapturesData = Field(default_factory=CapturesData, description="Captured screenshots")
    fetch: FetchProvenance = Field(..., description="Provenance information about the acquisition")
    quality: QualityData = Field(..., description="Deterministic extraction quality metrics")
    errors: List[ScraperErrorDetail] = Field(default_factory=list, description="Errors encountered during acquisition")


__all__ = [
    "ErrorCode",
    "ScraperErrorDetail",
    "FetchMode",
    "FetchRequest",
    "BatchFetchRequest",
    "RequestEcho",
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
]
