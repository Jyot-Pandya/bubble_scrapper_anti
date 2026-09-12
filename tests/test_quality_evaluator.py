"""
Tests for quality evaluation, confidence scoring, and block-page detection.
"""

from apps.scraper_service.core.quality import quality_evaluator
from apps.scraper_service.models.error import ErrorCode


def test_detect_captcha(sample_captcha_html):
    code = quality_evaluator.detect_access_restriction(sample_captcha_html, status_code=403)
    assert code == ErrorCode.CAPTCHA


def test_detect_paywall(sample_paywall_html):
    code = quality_evaluator.detect_access_restriction(sample_paywall_html, status_code=200)
    assert code == ErrorCode.PAYWALL


def test_detect_rate_limit():
    code = quality_evaluator.detect_access_restriction("Rate limit exceeded", status_code=429)
    assert code == ErrorCode.RATE_LIMITED


def test_detect_js_shell(sample_js_shell_html):
    is_shell = quality_evaluator.is_js_shell(sample_js_shell_html, "")
    assert is_shell is True


def test_high_quality_article_score(sample_article_html):
    title = "Breakthrough in Fusion Energy Announced"
    text = (
        "In a landmark experiment conducted early this morning, researchers successfully demonstrated a controlled fusion reaction that generated significantly more energy than was required to initiate it. This historic achievement represents a monumental leap forward for clean and virtually limitless energy production.\n\n"
        "The facility utilized high-powered magnetic confinement alongside synchronized laser arrays to stabilize the plasma core for an unprecedented duration. Measurement sensors registered an energy output exceeding input levels by over thirty-five percent, surpassing all previous laboratory benchmarks.\n\n"
        "International observers and independent peer review panels have validated the initial telemetry data. Further commercial scale development is anticipated over the next decade as engineering consortia begin designing prototype power plants.\n\n"
        "Additional research teams across Europe and Asia are coordinating to replicate the results under varying isotopic mixtures to optimize fuel cycle sustainability."
    )
    author = "Dr. Sarah Connor"
    published_at = "2026-09-09T10:00:00Z"

    confidence, factors = quality_evaluator.score_extraction(
        title=title,
        text=text,
        author=author,
        published_at=published_at,
        html=sample_article_html,
    )

    assert confidence >= 0.8
    assert factors["title_present"] is True
    assert factors["author_present"] is True
    assert factors["date_present"] is True
    assert factors["paragraph_count"] >= 3


def test_sparse_or_empty_score():
    confidence, factors = quality_evaluator.score_extraction(
        title="",
        text="Hello world",
        author=None,
        published_at=None,
        html="<div>Hello world</div>",
    )
    assert confidence < 0.3
