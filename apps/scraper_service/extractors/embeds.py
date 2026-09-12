"""
Discovery of videos, embeds, and iframes as specified in Section 14.
"""

import re
from typing import List, Tuple, Set
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from apps.scraper_service.models.response import VideoData, EmbedData

YOUTUBE_PATTERN = re.compile(r"(?:youtube\.com\/(?:watch\?v=|embed\/|shorts\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})", re.I)
VIMEO_PATTERN = re.compile(r"(?:vimeo\.com\/(?:video\/)?)([0-9]+)", re.I)
TIKTOK_PATTERN = re.compile(r"(?:tiktok\.com\/.*\/video\/)([0-9]+)", re.I)


class EmbedExtractor:
    @classmethod
    def discover(cls, html: str, base_url: str) -> Tuple[List[VideoData], List[EmbedData]]:
        soup = BeautifulSoup(html, "html.parser")
        videos: List[VideoData] = []
        embeds: List[EmbedData] = []
        seen_urls: Set[str] = set()

        # 1. HTML5 <video> elements
        for video_tag in soup.find_all("video"):
            poster = video_tag.get("poster")
            resolved_poster = urljoin(base_url, poster.strip()) if poster else None

            # Video src attribute directly
            src = video_tag.get("src")
            if src:
                resolved_src = urljoin(base_url, src.strip())
                if resolved_src not in seen_urls:
                    videos.append(
                        VideoData(
                            source_url=src,
                            resolved_url=resolved_src,
                            type="html5",
                            poster_url=resolved_poster,
                        )
                    )
                    seen_urls.add(resolved_src)

            # Nested <source> tags
            for source_tag in video_tag.find_all("source"):
                s_src = source_tag.get("src")
                if s_src:
                    resolved_s_src = urljoin(base_url, s_src.strip())
                    if resolved_s_src not in seen_urls:
                        videos.append(
                            VideoData(
                                source_url=s_src,
                                resolved_url=resolved_s_src,
                                type="html5",
                                poster_url=resolved_poster,
                            )
                        )
                        seen_urls.add(resolved_s_src)

        # 2. <iframe> elements (YouTube, Vimeo, TikTok, generic embeds)
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src") or iframe.get("data-src")
            if not src:
                continue

            resolved_src = urljoin(base_url, src.strip())
            if resolved_src in seen_urls:
                continue
            seen_urls.add(resolved_src)

            # Check if YouTube
            yt_match = YOUTUBE_PATTERN.search(resolved_src)
            if yt_match:
                video_id = yt_match.group(1)
                videos.append(
                    VideoData(
                        source_url=src,
                        resolved_url=f"https://www.youtube.com/watch?v={video_id}",
                        type="youtube",
                        poster_url=f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                    )
                )
                continue

            # Check if Vimeo
            vimeo_match = VIMEO_PATTERN.search(resolved_src)
            if vimeo_match:
                videos.append(
                    VideoData(
                        source_url=src,
                        resolved_url=resolved_src,
                        type="vimeo",
                    )
                )
                continue

            # Check if TikTok
            tiktok_match = TIKTOK_PATTERN.search(resolved_src)
            if tiktok_match:
                videos.append(
                    VideoData(
                        source_url=src,
                        resolved_url=resolved_src,
                        type="tiktok",
                    )
                )
                continue

            # Generic embed
            embeds.append(
                EmbedData(
                    type="iframe",
                    src=resolved_src,
                    html=str(iframe),
                )
            )

        # 3. Discovered standalone video links in <a> tags
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            resolved_href = urljoin(base_url, href.strip())
            if resolved_href in seen_urls:
                continue

            yt_match = YOUTUBE_PATTERN.search(resolved_href)
            if yt_match:
                video_id = yt_match.group(1)
                videos.append(
                    VideoData(
                        source_url=href,
                        resolved_url=f"https://www.youtube.com/watch?v={video_id}",
                        type="youtube",
                        poster_url=f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                        title=a_tag.get_text().strip() or None,
                    )
                )
                seen_urls.add(resolved_href)

        return videos, embeds


embed_extractor = EmbedExtractor()
