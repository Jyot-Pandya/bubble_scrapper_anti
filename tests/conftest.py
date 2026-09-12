"""
Pytest configuration and test fixtures.
"""

import pytest
import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


SAMPLE_ARTICLE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Breakthrough in Fusion Energy Announced</title>
    <meta name="description" content="Scientists achieve historic net energy gain in nuclear fusion experiment.">
    <meta name="author" content="Dr. Sarah Connor">
    <meta property="og:title" content="Fusion Energy Breakthrough">
    <meta property="og:description" content="Historic net energy gain recorded by physics team.">
    <meta property="og:image" content="https://example.com/images/fusion-hero.jpg">
    <meta property="og:site_name" content="Science Daily Global">
    <link rel="canonical" href="https://example.com/fusion-breakthrough">
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": "Breakthrough in Fusion Energy",
        "datePublished": "2026-09-09T10:00:00Z",
        "author": {"@type": "Person", "name": "Dr. Sarah Connor"}
    }
    </script>
</head>
<body>
    <header>
        <nav><a href="/">Home</a> | <a href="/news">News</a></nav>
    </header>
    <article>
        <h1>Breakthrough in Fusion Energy Announced</h1>
        <p class="byline">By Dr. Sarah Connor | Published Sept 9, 2026</p>
        <p>In a landmark experiment conducted early this morning, researchers successfully demonstrated a controlled fusion reaction that generated significantly more energy than was required to initiate it. This historic achievement represents a monumental leap forward for clean and virtually limitless energy production.</p>
        <p>The facility utilized high-powered magnetic confinement alongside synchronized laser arrays to stabilize the plasma core for an unprecedented duration. Measurement sensors registered an energy output exceeding input levels by over thirty-five percent, surpassing all previous laboratory benchmarks.</p>
        <figure>
            <img src="/images/plasma-chamber.jpg" alt="Inside the magnetic plasma confinement chamber" width="800" height="500">
            <figcaption>The core magnetic chamber during plasma ignition.</figcaption>
        </figure>
        <p>International observers and independent peer review panels have validated the initial telemetry data. Further commercial scale development is anticipated over the next decade as engineering consortia begin designing prototype power plants.</p>
        <div class="video-container">
            <iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ" width="560" height="315"></iframe>
        </div>
    </article>
    <!-- Tracking pixel and spacer that should be filtered -->
    <img src="https://tracker.adservice.com/pixel.gif?id=123" width="1" height="1" alt="">
    <img src="/images/spacer.gif" width="5" height="5" alt="">
    <footer>
        <p>&copy; 2026 Science Daily Global. All rights reserved.</p>
    </footer>
</body>
</html>
"""

SAMPLE_JS_SHELL_HTML = """<!DOCTYPE html>
<html>
<head><title>React App</title></head>
<body>
    <noscript>You need to enable JavaScript to run this app.</noscript>
    <div id="root"></div>
    <script src="/static/js/bundle.js"></script>
</body>
</html>
"""

SAMPLE_CAPTCHA_HTML = """<!DOCTYPE html>
<html>
<head><title>Attention Required! | Cloudflare</title></head>
<body>
    <h1>Just a moment...</h1>
    <p>Please complete the security check to access example.com</p>
    <div id="cf-browser-verification"></div>
</body>
</html>
"""

SAMPLE_PAYWALL_HTML = """<!DOCTYPE html>
<html>
<head><title>Exclusive Investigative Report</title></head>
<body>
    <h1>Inside the Secret Operations</h1>
    <p>This is the first opening paragraph of the investigative story available for preview.</p>
    <div class="paywall-overlay">
        <h2>Subscribe to read full story</h2>
        <p>This article is for subscribers only. Join now for unlimited digital access.</p>
    </div>
</body>
</html>
"""


@pytest.fixture
def sample_article_html():
    return SAMPLE_ARTICLE_HTML


@pytest.fixture
def sample_js_shell_html():
    return SAMPLE_JS_SHELL_HTML


@pytest.fixture
def sample_captcha_html():
    return SAMPLE_CAPTCHA_HTML


@pytest.fixture
def sample_paywall_html():
    return SAMPLE_PAYWALL_HTML
