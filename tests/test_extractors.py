"""
Tests for ContentExtractor, MediaExtractor, and EmbedExtractor.
"""

from apps.scraper_service.extractors.content import content_extractor
from apps.scraper_service.extractors.media import media_extractor
from apps.scraper_service.extractors.embeds import embed_extractor


def test_content_extractor(sample_article_html):
    page_data, metadata = content_extractor.extract(
        html=sample_article_html,
        url="https://example.com/news/fusion",
        include_markdown=True,
        include_html=True,
    )

    # Core Page Data
    assert page_data.title is not None
    assert "Fusion" in page_data.title
    assert page_data.language == "en"
    assert page_data.canonical_url == "https://example.com/fusion-breakthrough"
    assert page_data.text is not None
    assert "confinement chamber" in page_data.text.lower() or "plasma" in page_data.text.lower()
    assert page_data.markdown is not None

    # Metadata
    assert metadata.site_name == "Science Daily Global"
    assert metadata.og_title == "Fusion Energy Breakthrough"
    assert metadata.og_image == "https://example.com/images/fusion-hero.jpg"
    assert len(metadata.json_ld) >= 1
    assert metadata.json_ld[0]["@type"] == "NewsArticle"


def test_media_extractor(sample_article_html):
    _, metadata = content_extractor.extract(
        html=sample_article_html,
        url="https://example.com/news/fusion",
    )
    images = media_extractor.discover_images(
        html=sample_article_html,
        base_url="https://example.com/news/fusion",
        metadata=metadata,
    )

    assert len(images) >= 2

    # Hero image from metadata
    hero_imgs = [img for img in images if img.is_hero]
    assert len(hero_imgs) >= 1
    assert hero_imgs[0].resolved_url == "https://example.com/images/fusion-hero.jpg"

    # Article image
    article_imgs = [img for img in images if "plasma-chamber" in img.resolved_url]
    assert len(article_imgs) == 1
    assert article_imgs[0].width == 800
    assert article_imgs[0].height == 500
    assert article_imgs[0].resolved_url == "https://example.com/images/plasma-chamber.jpg"

    # Filtered images: verify 1x1 pixel and spacer were omitted
    all_resolved = [img.resolved_url for img in images]
    assert not any("pixel.gif" in u for u in all_resolved)
    assert not any("spacer.gif" in u for u in all_resolved)


def test_embed_extractor(sample_article_html):
    videos, embeds = embed_extractor.discover(
        html=sample_article_html,
        base_url="https://example.com/news/fusion",
    )

    # Should discover the YouTube iframe
    assert len(videos) == 1
    yt = videos[0]
    assert yt.type == "youtube"
    assert yt.resolved_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert yt.poster_url == "https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"
