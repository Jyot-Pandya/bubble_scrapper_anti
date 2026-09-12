"""
High-quality text, metadata, OpenGraph, JSON-LD, and Markdown extraction
using Trafilatura with BeautifulSoup & Markdownify fallbacks.
"""

import json
from typing import Tuple, Dict, Any, List, Optional
from bs4 import BeautifulSoup
import trafilatura
from markdownify import markdownify as md_convert

from apps.scraper_service.models.response import PageData, Metadata


class ContentExtractor:
    @staticmethod
    def extract_metadata(soup: BeautifulSoup) -> Metadata:
        metadata = Metadata()

        # OpenGraph
        og_site_name = soup.find("meta", property="og:site_name") or soup.find("meta", attrs={"name": "og:site_name"})
        if og_site_name and og_site_name.get("content"):
            metadata.site_name = og_site_name["content"].strip()

        og_title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "og:title"})
        if og_title and og_title.get("content"):
            metadata.og_title = og_title["content"].strip()

        og_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "og:description"})
        if og_desc and og_desc.get("content"):
            metadata.og_description = og_desc["content"].strip()

        og_img = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "og:image"})
        if og_img and og_img.get("content"):
            metadata.og_image = og_img["content"].strip()

        # Twitter Card
        tw_card = soup.find("meta", attrs={"name": "twitter:card"})
        if tw_card and tw_card.get("content"):
            metadata.twitter_card = tw_card["content"].strip()

        tw_title = soup.find("meta", attrs={"name": "twitter:title"})
        if tw_title and tw_title.get("content"):
            metadata.twitter_title = tw_title["content"].strip()

        tw_desc = soup.find("meta", attrs={"name": "twitter:description"})
        if tw_desc and tw_desc.get("content"):
            metadata.twitter_description = tw_desc["content"].strip()

        tw_img = soup.find("meta", attrs={"name": "twitter:image"})
        if tw_img and tw_img.get("content"):
            metadata.twitter_image = tw_img["content"].strip()

        # JSON-LD
        json_ld_list: List[Dict[str, Any]] = []
        for script in soup.find_all("script", type="application/ld+json"):
            content = script.string
            if content:
                try:
                    data = json.loads(content.strip())
                    if isinstance(data, list):
                        json_ld_list.extend(data)
                    elif isinstance(data, dict):
                        json_ld_list.append(data)
                except Exception:
                    pass
        metadata.json_ld = json_ld_list

        return metadata

    @staticmethod
    def extract_canonical(soup: BeautifulSoup, default_url: str) -> str:
        canonical = soup.find("link", rel="canonical")
        if canonical and canonical.get("href"):
            return canonical["href"].strip()
        og_url = soup.find("meta", property="og:url")
        if og_url and og_url.get("content"):
            return og_url["content"].strip()
        return default_url

    @classmethod
    def extract(
        cls,
        html: str,
        url: str,
        include_markdown: bool = True,
        include_html: bool = False,
    ) -> Tuple[PageData, Metadata]:
        soup = BeautifulSoup(html, "html.parser")
        metadata = cls.extract_metadata(soup)
        canonical_url = cls.extract_canonical(soup, url)

        # Primary extraction using trafilatura
        extracted_text = None
        extracted_md = None
        title = None
        author = None
        published_at = None
        language = None
        description = None

        try:
            # Trafilatura metadata extraction
            traf_meta = trafilatura.extract_metadata(html, default_url=url)
            if traf_meta:
                title = traf_meta.title
                author = traf_meta.author
                published_at = traf_meta.date
                language = traf_meta.language
                description = traf_meta.description
                if not metadata.site_name and traf_meta.sitename:
                    metadata.site_name = traf_meta.sitename

            # Trafilatura text extraction
            extracted_text = trafilatura.extract(
                html,
                url=url,
                include_comments=False,
                include_tables=True,
                favor_precision=True,
                output_format="txt",
            )

            if include_markdown:
                extracted_md = trafilatura.extract(
                    html,
                    url=url,
                    include_comments=False,
                    include_tables=True,
                    favor_precision=True,
                    output_format="markdown",
                )
        except Exception:
            pass

        # Fallback to BeautifulSoup if Trafilatura missed title/description
        if not title:
            if soup.title and soup.title.string:
                title = soup.title.string.strip()
            elif metadata.og_title:
                title = metadata.og_title
            else:
                h1 = soup.find("h1")
                if h1:
                    title = h1.get_text().strip()

        if not description:
            desc_tag = soup.find("meta", attrs={"name": "description"})
            if desc_tag and desc_tag.get("content"):
                description = desc_tag["content"].strip()
            elif metadata.og_description:
                description = metadata.og_description

        if not language:
            html_tag = soup.find("html")
            if html_tag and html_tag.get("lang"):
                language = html_tag["lang"].strip()

        # Fallback for text and markdown if Trafilatura text is sparse
        if not extracted_text or len(extracted_text.strip()) < 50:
            # Remove scripts, styles, noscript, etc.
            body = soup.find("body") or soup
            if body:
                # Clone or strip non-content tags
                for bad_tag in body.find_all(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
                    bad_tag.decompose()
                extracted_text = body.get_text(separator="\n", strip=True)
                if include_markdown and not extracted_md:
                    extracted_md = md_convert(str(body), heading_style="ATX").strip()

        if include_markdown and not extracted_md and extracted_text:
            extracted_md = extracted_text

        page_data = PageData(
            final_url=url,
            canonical_url=canonical_url,
            title=title,
            author=author,
            published_at=published_at,
            language=language,
            description=description,
            text=extracted_text,
            markdown=extracted_md if include_markdown else None,
            html=html if include_html else None,
        )

        return page_data, metadata


content_extractor = ContentExtractor()
