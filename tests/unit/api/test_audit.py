"""Tests for GET /audit/{session_id}."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> TestClient:
    """Return a synchronous test client for the FastAPI app."""
    from medagent.api.main import app

    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client


class TestAuditEndpoint:
    """Tests for GET /audit/{session_id}."""

    def test_audit_returns_row_when_found(self, client: TestClient) -> None:
        """GET /audit/{session_id} returns persisted audit metadata."""
        fake_row = {
            "session_id": "sess-123",
            "state_reached": "OUTPUT",
            "escalated": False,
            "overall_confidence": 0.81,
            "model_used": "claude-sonnet-4-6",
            "created_at": datetime(2026, 6, 22, 0, 0, 0),
        }
        with patch("medagent.api.main.fetch_run", new=AsyncMock(return_value=fake_row)):
            response = client.get("/audit/sess-123")
        assert response.status_code == 200
        body = response.json()
        assert body["session_id"] == "sess-123"
        assert body["state_reached"] == "OUTPUT"
        assert body["escalated"] is False
        assert body["overall_confidence"] == 0.81
        assert body["model_used"] == "claude-sonnet-4-6"

    def test_audit_returns_404_when_missing(self, client: TestClient) -> None:
        """GET /audit/{session_id} returns 404 for unknown sessions."""
        with patch("medagent.api.main.fetch_run", new=AsyncMock(return_value=None)):
            response = client.get("/audit/missing-session")
        assert response.status_code == 404
