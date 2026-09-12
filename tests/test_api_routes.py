"""
Tests for FastAPI API endpoints and routing.
"""

import pytest
from fastapi.testclient import TestClient
from apps.scraper_service.main import app


@pytest.fixture
def test_client():
    return TestClient(app)


def test_health_endpoint(test_client):
    response = test_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "browser_enabled" in data
    assert "version" in data


def test_metrics_endpoint(test_client):
    response = test_client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "uptime_seconds" in data
    assert "stages" in data
    assert "latencies" in data


def test_domains_endpoint(test_client):
    response = test_client.get("/domains")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_ssrf_blocked_endpoint(test_client):
    payload = {
        "url": "http://127.0.0.1:8000/secret",
        "mode": "auto",
    }
    response = test_client.post("/fetch", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["errors"]) > 0
    assert data["errors"][0]["code"] == "ssrf_blocked"
    assert data["quality"]["extraction_confidence"] == 0.0


def test_batch_fetch_validation(test_client):
    # Empty batch request should return 400
    response = test_client.post("/fetch/batch", json={})
    assert response.status_code == 400


def test_cache_clear_endpoint(test_client):
    response = test_client.post("/cache/clear")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cleared"
    assert data["cache_entries"] == 0


def test_batch_fetch_execution(test_client):
    payload = {
        "urls": [
            "http://127.0.0.1/blocked1",
            "http://127.0.0.1/blocked2",
        ],
        "mode": "auto",
        "concurrency": 2,
    }
    response = test_client.post("/fetch/batch", json=payload)
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    assert all(item["errors"][0]["code"] == "ssrf_blocked" for item in items)

