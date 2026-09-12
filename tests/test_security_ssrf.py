"""
Tests for SSRF prevention and security validation.
"""

import pytest
from apps.scraper_service.core.security import validate_url_security


def test_allowed_public_url():
    is_safe, error = validate_url_security("https://example.com/news")
    assert is_safe is True
    assert error == ""


def test_forbidden_schemes():
    forbidden_schemes = [
        "file:///etc/passwd",
        "file://C:/Windows/System32/drivers/etc/hosts",
        "ftp://example.com/file.txt",
        "gopher://example.com",
        "javascript:alert(1)",
    ]
    for url in forbidden_schemes:
        is_safe, error = validate_url_security(url)
        assert is_safe is False
        assert "is forbidden" in error or "Invalid URL" in error


def test_blocked_localhost():
    hosts = [
        "http://localhost/admin",
        "http://localhost:8000/metrics",
        "http://127.0.0.1/secret",
        "http://127.0.0.1:3000",
        "http://0.0.0.0:8080",
        "http://[::1]/internal",
    ]
    for url in hosts:
        is_safe, error = validate_url_security(url)
        assert is_safe is False
        assert "blocked" in error or "restricted" in error


def test_blocked_cloud_metadata():
    metadata_endpoints = [
        "http://169.254.169.254/latest/meta-data/",
        "http://169.254.169.254/computeMetadata/v1/",
        "http://metadata.google.internal/computeMetadata/v1/",
    ]
    for url in metadata_endpoints:
        is_safe, error = validate_url_security(url)
        assert is_safe is False
        assert "metadata" in error.lower() or "restricted" in error.lower() or "blocked" in error.lower()


def test_blocked_private_subnets():
    private_ips = [
        "http://10.0.0.1/status",
        "http://10.255.0.1/api",
        "http://172.16.0.1/config",
        "http://172.31.255.255/db",
        "http://192.168.1.1/router",
        "http://192.168.0.100:8000",
    ]
    for url in private_ips:
        is_safe, error = validate_url_security(url)
        assert is_safe is False
        assert "restricted" in error.lower() or "private" in error.lower()
