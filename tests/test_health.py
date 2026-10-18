"""Tests for the GET /status health endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_status_returns_200_and_valid_json() -> None:
    """GET /status should return HTTP 200 with valid JSON."""
    client = TestClient(app)
    response = client.get("/status")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "ghoomai-agent"
    assert "version" in body
