"""
Image discovery, filtering, metadata extraction, and optional downloading
as specified in Section 11 and Section 12.
"""

import hashlib
import io
import mimetypes
import re
from typing import List, Optional, Set
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import httpx
from PIL import Image

from apps.scraper_service.config import settings
from apps.scraper_service.core.security import validate_url_security
from apps.scraper_service.models.response import ImageData, Metadata
from apps.scraper_service.providers.storage.base import BaseStorageProvider

TRACKING_IMAGE_PATTERNS = [
    re.compile(r"/pixel\.(gif|png)", re.I),
    re.compile(r"/track(ing)?\.(gif|png)", re.I),
    re.compile(r"/beacon", re.I),
    re.compile(r"/spacer\.(gif|png)", re.I),
    re.compile(r"1x1", re.I),
    re.compile(r"blank\.gif", re.I),
    re.compile(r"adservice", re.I),
    re.compile(r"doubleclick", re.I),
]


class MediaExtractor:
    @staticmethod
    def _is_noise(src: str, width: Optional[int], height: Optional[int], alt: Optional[str]) -> bool:
        # Check explicit dimensions
        if width is not None and height is not None:
            if width <= 2 and height <= 2:
                return True
            if width <= 16 and height <= 16 and not alt:
                return True

        # Check tracking patterns in URL
        for pattern in TRACKING_IMAGE_PATTERNS:
            if pattern.search(src):
                return True

        # Check data URI transparent 1x1 gifs
        if src.startswith("data:image/gif;base64,R0lGODlhAQABA"):
            return True

        return False

    @classmethod
    def discover_images(cls, html: str, base_url: str, metadata: Optional[Metadata] = None) -> List[ImageData]:
        soup = BeautifulSoup(html, "html.parser")
        images: List[ImageData] = []
        seen_urls: Set[str] = set()
        position = 0

        hero_url = None
        if metadata:
            hero_url = metadata.og_image or metadata.twitter_image

        # 1. Add OpenGraph / Twitter hero image if available
        if hero_url:
            resolved_hero = urljoin(base_url, hero_url)
            images.append(
                ImageData(
                    source_url=hero_url,
                    resolved_url=resolved_hero,
                    alt="Hero image",
                    is_hero=True,
                    position=0,
                    dom_context="metadata",
                    mime_type=mimetypes.guess_type(resolved_hero)[0],
                )
            )
            seen_urls.add(resolved_hero)
            position += 1

        # 2. Extract JSON-LD images
        if metadata and metadata.json_ld:
            for entry in metadata.json_ld:
                if isinstance(entry, dict):
                    img_field = entry.get("image")
                    jsonld_urls = []
                    if isinstance(img_field, str):
                        jsonld_urls.append(img_field)
                    elif isinstance(img_field, list):
                        for it in img_field:
                            if isinstance(it, str):
                                jsonld_urls.append(it)
                            elif isinstance(it, dict) and it.get("url"):
                                jsonld_urls.append(it["url"])
                    elif isinstance(img_field, dict) and img_field.get("url"):
                        jsonld_urls.append(img_field["url"])

                    for j_url in jsonld_urls:
                        if j_url:
                            resolved_j = urljoin(base_url, j_url.strip())
                            if resolved_j not in seen_urls and not cls._is_noise(resolved_j, None, None, None):
                                images.append(
                                    ImageData(
                                        source_url=j_url,
                                        resolved_url=resolved_j,
                                        alt="JSON-LD image",
                                        is_hero=(position == 0),
                                        position=position,
                                        dom_context="json_ld",
                                        mime_type=mimetypes.guess_type(resolved_j)[0],
                                    )
                                )
                                seen_urls.add(resolved_j)
                                position += 1

        # 3. Extract from <picture> sources
        for picture in soup.find_all("picture"):
            for source in picture.find_all("source"):
                srcset = source.get("srcset")
                if srcset:
                    src = srcset.split(",")[0].strip().split(" ")[0]
                    resolved_src = urljoin(base_url, src.strip())
                    if resolved_src not in seen_urls and not cls._is_noise(resolved_src, None, None, None):
                        images.append(
                            ImageData(
                                source_url=src,
                                resolved_url=resolved_src,
                                alt=None,
                                dom_context="picture",
                                position=position,
                                mime_type=mimetypes.guess_type(resolved_src)[0],
                            )
                        )
                        seen_urls.add(resolved_src)
                        position += 1

        # 4. Extract from <img>
        for img in soup.find_all("img"):
            # Check data-src, src, srcset
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or img.get("data-original")
            if not src:
                srcset = img.get("srcset")
                if srcset:
                    # Take largest or first from srcset
                    src = srcset.split(",")[0].strip().split(" ")[0]

            if not src:
                continue

            resolved_src = urljoin(base_url, src.strip())
            if resolved_src in seen_urls:
                continue

            # Parse width/height if available in attributes
            width = None
            height = None
            try:
                if img.get("width"):
                    width = int(re.sub(r"[^\d]", "", str(img["width"])))
                if img.get("height"):
                    height = int(re.sub(r"[^\d]", "", str(img["height"])))
            except Exception:
                pass

            alt = img.get("alt", "").strip() if img.get("alt") else None
            title = img.get("title", "").strip() if img.get("title") else None

            # Filter noise
            if cls._is_noise(resolved_src, width, height, alt):
                continue

            # Determine DOM context
            parent = img.parent
            dom_context = parent.name if parent else "body"

            is_hero_candidate = False
            if hero_url and resolved_src == urljoin(base_url, hero_url):
                is_hero_candidate = True
            elif position == 1 and width and width >= 600:
                is_hero_candidate = True

            images.append(
                ImageData(
                    source_url=src,
                    resolved_url=resolved_src,
                    alt=alt,
                    title=title,
                    width=width,
                    height=height,
                    mime_type=mimetypes.guess_type(resolved_src)[0],
                    dom_context=dom_context,
                    position=position,
                    is_hero=is_hero_candidate,
                )
            )
            seen_urls.add(resolved_src)
            position += 1

        # 5. Discover CSS background images (inline styles: style="background-image: url(...)")
        for elem in soup.find_all(style=re.compile(r"background(-image)?\s*:\s*url", re.I)):
            style = elem.get("style", "")
            match = re.search(r"url\s*\(\s*['\"]?([^'\")]+)['\"]?\s*\)", style, re.I)
            if match:
                bg_src = match.group(1).strip()
                resolved_bg = urljoin(base_url, bg_src)
                if resolved_bg not in seen_urls and not cls._is_noise(resolved_bg, None, None, None):
                    images.append(
                        ImageData(
                            source_url=bg_src,
                            resolved_url=resolved_bg,
                            alt=None,
                            title=None,
                            dom_context=elem.name,
                            position=position,
                            is_hero=False,
                            mime_type=mimetypes.guess_type(resolved_bg)[0],
                        )
                    )
                    seen_urls.add(resolved_bg)
                    position += 1

        return images

    @classmethod
    async def download_images(
        cls,
        images: List[ImageData],
        storage_provider: Optional[BaseStorageProvider] = None,
        max_downloads: int = 5,
        timeout_seconds: float = 10.0,
    ) -> List[ImageData]:
        """
        Downloads top N images, computes hashes, validates with Pillow,
        and saves to storage provider if configured.
        Enforces SSRF protection on all downloaded URLs.
        """
        if not storage_provider or max_downloads <= 0:
            return images

        # Prioritize hero images and early positions
        sorted_images = sorted(images, key=lambda x: (not x.is_hero, x.position))
        targets = sorted_images[:max_downloads]

        headers = {
            "User-Agent": settings.default_user_agent,
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        }
        async with httpx.AsyncClient(headers=headers, timeout=timeout_seconds, follow_redirects=True) as client:
            for img in targets:
                # Security: SSRF validation on image URL
                if settings.ssrf_protection_enabled:
                    is_safe, _ = validate_url_security(img.resolved_url)
                    if not is_safe:
                        continue

                try:
                    resp = await client.get(img.resolved_url)
                    if resp.status_code == 200 and resp.content:
                        content = resp.content
                        img.content_hash = hashlib.sha256(content).hexdigest()

                        # Pillow inspection
                        try:
                            pil_img = Image.open(io.BytesIO(content))
                            img.width, img.height = pil_img.size
                            if not img.mime_type and pil_img.format:
                                img.mime_type = f"image/{pil_img.format.lower()}"
                        except Exception:
                            pass

                        # Store in storage provider
                        ext = mimetypes.guess_extension(img.mime_type or "") or ".jpg"
                        key = f"images/{img.content_hash[:16]}{ext}"
                        img.storage_url = await storage_provider.save(key, content, img.mime_type or "image/jpeg")
                except Exception:
                    pass

        return images


media_extractor = MediaExtractor()
