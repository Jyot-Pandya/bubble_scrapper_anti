"""
Configuration and settings for Scraper Service using pydantic-settings.
"""

from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="SCRAPER_",
        extra="ignore"
    )

    # Server settings
    app_name: str = "Outside Bubble Scraper Service"
    version: str = "1.0.0"
    environment: str = "production"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # HTTP Acquisition
    default_timeout_ms: int = 30000
    max_redirects: int = 5
    max_response_bytes: int = 15 * 1024 * 1024  # 15 MB safeguard
    default_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36 OutsideBubble/1.0 (https://outsidebubble.org; contact@outsidebubble.org)"
    )

    # Browser Acquisition
    browser_enabled: bool = True
    browser_headless: bool = True
    browser_pool_size: int = 4
    browser_timeout_ms: int = 30000
    browser_viewport_width: int = 1280
    browser_viewport_height: int = 800
    browser_stealth_enabled: bool = True

    # Rate Limiting & Courtesy
    global_concurrency_limit: int = 20
    domain_concurrency_limit: int = 2
    domain_min_interval_seconds: float = 0.5
    domain_cooldown_seconds: float = 60.0

    # Security & SSRF
    ssrf_protection_enabled: bool = True
    allowed_schemes: List[str] = Field(default_factory=lambda: ["http", "https"])

    # Caching & Deduplication
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600
    cache_max_entries: int = 1000

    # Domain Intelligence
    adaptive_enabled: bool = True
    adaptive_failure_threshold: int = 2

    # Storage Settings
    storage_provider: str = "local"  # "local", "s3", or "none"
    local_storage_dir: str = "./storage"
    s3_endpoint: Optional[str] = None
    s3_bucket: Optional[str] = None
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None
    s3_public_url: Optional[str] = None

    # Proxy Settings
    proxy_provider: str = "none"  # "none", "static", "webshare"
    proxy_url: Optional[str] = None
    webshare_username: Optional[str] = None
    webshare_password: Optional[str] = None
    webshare_host: str = "p.webshare.io"
    webshare_port: int = 80


settings = Settings()
