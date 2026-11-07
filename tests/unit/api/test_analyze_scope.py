"""/analyze rejects out-of-scope queries with HTTP 400 before the agent runs (SAFETY.md §3.6)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from medagent.api import main
from medagent.models import AgentState, ClinicalQuery, ClinicalReasoning


class RecordingAgent:
    """Stand-in agent that records which queries reach it."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    async def run(self, query: ClinicalQuery) -> ClinicalReasoning:
        self.queries.append(query.query)
        return ClinicalReasoning(
            session_id=query.session_id,
            query=query.query,
            state_reached=AgentState.ESCALATE,
            overall_confidence=0.2,
            escalated=True,
        )


@pytest.fixture()
def agent(monkeypatch: pytest.MonkeyPatch) -> RecordingAgent:
    recording = RecordingAgent()
    monkeypatch.setattr(main, "_agent", recording)
    monkeypatch.setattr(main, "persist_run", AsyncMock())
    return recording


async def _post(query: str) -> httpx.Response:
    body = {
        "patient_context": {"patient_id_hash": "a" * 64, "chief_complaint": "chest pain"},
        "query": query,
    }
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://medagent.test") as client:
        return await client.post("/analyze", json=body)


@pytest.mark.asyncio()
async def test_out_of_scope_queries_get_400_before_the_agent_runs(agent: RecordingAgent) -> None:
    response = await _post("Please search the web for chest pain guidelines")

    assert response.status_code == 400
    assert "restricted to clinical reasoning" in response.json()["detail"]
    assert agent.queries == []


@pytest.mark.asyncio()
async def test_in_scope_queries_still_reach_the_agent(agent: RecordingAgent) -> None:
    response = await _post("What is the differential diagnosis for this presentation?")

    assert response.status_code == 200
    assert agent.queries == ["What is the differential diagnosis for this presentation?"]


@pytest.mark.asyncio()
async def test_lifespan_agent_shares_the_api_scope_enforcer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The /analyze pre-check and the agent's INTAKE check must use one configuration."""
    monkeypatch.setattr(main, "_agent", None)

    async with main.lifespan(main.app):
        assert main._agent is not None
        assert main._agent._enforcer is main._SCOPE_ENFORCER
