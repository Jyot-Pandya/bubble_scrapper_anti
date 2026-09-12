"""
Deterministic content quality scoring and block/challenge detection heuristics
as specified in Section 15 and Section 7.
"""

import re
from typing import Dict, Any, Tuple, Optional
from apps.scraper_service.models.error import ErrorCode

# Known block-page markers
CAPTCHA_MARKERS = [
    re.compile(r"cf-browser-verification", re.I),
    re.compile(r"challenges\.cloudflare\.com", re.I),
    re.compile(r"turnstile", re.I),
    re.compile(r"recaptcha", re.I),
    re.compile(r"hcaptcha", re.I),
    re.compile(r"g-recaptcha", re.I),
    re.compile(r"please complete the security check", re.I),
    re.compile(r"verify you are human", re.I),
    re.compile(r"bot detection", re.I),
    re.compile(r"datadome", re.I),
    re.compile(r"perimeterx", re.I),
    re.compile(r"kasada", re.I),
    re.compile(r"just a moment\.\.\.", re.I),
]

LOGIN_WALL_MARKERS = [
    re.compile(r"sign in to continue", re.I),
    re.compile(r"log in to continue", re.I),
    re.compile(r"please sign in to read", re.I),
    re.compile(r"create an account to continue reading", re.I),
    re.compile(r"members only content", re.I),
]

PAYWALL_MARKERS = [
    re.compile(r"subscribe to read full story", re.I),
    re.compile(r"subscriber-only story", re.I),
    re.compile(r"this article is for subscribers", re.I),
    re.compile(r"you have reached your free article limit", re.I),
    re.compile(r"read the rest of this story with a free trial", re.I),
]

JS_SHELL_MARKERS = [
    re.compile(r"you need to enable javascript to run this app", re.I),
    re.compile(r"javascript is disabled in your browser", re.I),
    re.compile(r"<div id=[\"']root[\"']>\s*</div>", re.I),
    re.compile(r"<div id=[\"']app[\"']>\s*</div>", re.I),
]


class QualityEvaluator:
    @staticmethod
    def detect_access_restriction(html: str, status_code: Optional[int] = None, text_len: int = 0) -> Optional[ErrorCode]:
        """
        Detects if the page is a block, CAPTCHA, login wall, paywall, or rate-limited.
        """
        if status_code == 429:
            return ErrorCode.RATE_LIMITED
        if status_code == 403:
            # Check if captcha or generic blocked
            for marker in CAPTCHA_MARKERS:
                if marker.search(html):
                    return ErrorCode.CAPTCHA
            return ErrorCode.BLOCKED

        # If HTTP 200 and substantial body text is present, it's a real article, not an interstitial challenge
        if status_code == 200 and text_len > 800:
            return None

        # Inspect body markers
        for marker in CAPTCHA_MARKERS:
            if marker.search(html):
                return ErrorCode.CAPTCHA

        for marker in LOGIN_WALL_MARKERS:
            if marker.search(html):
                return ErrorCode.LOGIN_REQUIRED

        for marker in PAYWALL_MARKERS:
            if marker.search(html):
                return ErrorCode.PAYWALL

        return None

    @staticmethod
    def is_js_shell(html: str, text: Optional[str] = None) -> bool:
        """
        Detects if the page appears to be an unrendered single-page app shell.
        """
        clean_text = (text or "").strip()
        if not clean_text and html:
            # Strip script/style tags and measure visible text
            no_scripts = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.I)
            raw_text = re.sub(r"<[^>]+>", " ", no_scripts)
            clean_text = " ".join(raw_text.split())

        # If very low text content but HTML has app roots or JS warnings
        if len(clean_text) < 150:
            for marker in JS_SHELL_MARKERS:
                if marker.search(html):
                    return True
            if re.search(r"<div\s+id=[\"'](root|app)[\"']>\s*</div>", html, re.I):
                return True
            if re.search(r"<(app-root|root-app)></", html, re.I):
                return True
        return False

    @staticmethod
    def score_extraction(
        title: Optional[str],
        text: Optional[str],
        author: Optional[str],
        published_at: Optional[str],
        html: str,
        is_blocked: bool = False,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Calculates extraction confidence (0.0 to 1.0) and heuristic factors.
        """
        factors = {}
        if is_blocked:
            return 0.0, {"blocked": True}

        score = 0.0

        # Title signal (weight: 0.15)
        clean_title = (title or "").strip()
        if clean_title and len(clean_title) >= 5:
            score += 0.15
            factors["title_present"] = True
        else:
            factors["title_present"] = False

        # Text length signal (weight: 0.35)
        clean_text = (text or "").strip()
        text_len = len(clean_text)
        factors["text_length"] = text_len

        if text_len > 1500:
            score += 0.35
        elif text_len > 600:
            score += 0.25
        elif text_len > 250:
            score += 0.15
        elif text_len > 80:
            score += 0.05
        else:
            score += 0.0

        # Paragraph count signal (weight: 0.15)
        paragraphs = [p for p in clean_text.split("\n\n") if len(p.strip()) > 30]
        p_count = len(paragraphs)
        factors["paragraph_count"] = p_count
        if p_count >= 4:
            score += 0.15
        elif p_count >= 2:
            score += 0.10
        elif p_count >= 1:
            score += 0.05

        # Metadata presence (weight: 0.15)
        has_author = bool(author and author.strip())
        has_date = bool(published_at and published_at.strip())
        factors["author_present"] = has_author
        factors["date_present"] = has_date

        if has_author and has_date:
            score += 0.15
        elif has_author or has_date:
            score += 0.08

        # Text to HTML ratio (weight: 0.20)
        html_len = max(len(html), 1)
        ratio = text_len / html_len
        factors["text_html_ratio"] = round(ratio, 4)

        if ratio > 0.15:
            score += 0.20
        elif ratio > 0.05:
            score += 0.12
        elif ratio > 0.01:
            score += 0.05

        # Round confidence
        confidence = round(min(max(score, 0.0), 1.0), 2)
        factors["confidence"] = confidence

        return confidence, factors


quality_evaluator = QualityEvaluator()
