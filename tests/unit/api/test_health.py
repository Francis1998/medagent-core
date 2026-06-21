"""Tests for the FastAPI /health endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.fixtures import FixtureRequest
    from _pytest.logging import LogCaptureFixture
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock.plugin import MockerFixture


@pytest.fixture()
def client() -> TestClient:
    """Return a synchronous test client without running the lifespan (agent=None)."""
    from medagent.api.main import app

    # Use lifespan=False equivalent — override the agent after construction
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_returns_200(self, client: TestClient) -> None:
        """GET /health must return HTTP 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_schema(self, client: TestClient) -> None:
        """GET /health must return a JSON body with status and agent_ready fields."""
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert "agent_ready" in data
        assert "version" in data
        assert "timestamp" in data

    def test_health_status_ok(self, client: TestClient) -> None:
        """status field must be 'ok'."""
        response = client.get("/health")
        assert response.json()["status"] == "ok"
