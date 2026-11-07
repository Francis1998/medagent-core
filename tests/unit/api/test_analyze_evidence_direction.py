"""/analyze must not gain confidence from contradicting evidence (SAFETY.md §3.4)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from medagent.agent.state_machine import ClinicalAgentStateMachine
from medagent.api import main
from medagent.extraction.ner import EntityExtractor
from medagent.llm.base import BaseLLMAdapter, LLMResponse
from medagent.llm.router import MedicalRouter
from medagent.reasoning.engine import ReasoningEngine
from medagent.safety.scope_enforcer import ScopeEnforcer

SUPPORTING = [{"statement": "Exertional retrosternal pressure", "strength": 0.7}]
WEAKLY_CONTRADICTING = [
    {"statement": "Normal initial ECG", "strength": 0.3},
    {"statement": "Pain partly reproducible on palpation", "strength": 0.3},
]


class DifferentialAdapter(BaseLLMAdapter):
    """Stub LLM returning one fixed hypothesis."""

    def __init__(self, evidence_against: list[dict[str, Any]]) -> None:
        self._evidence_against = evidence_against

    @property
    def provider_name(self) -> str:
        return "anthropic"

    async def complete(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.1,
    ) -> LLMResponse:
        hypothesis = {
            "label": "Acute coronary syndrome",
            "icd_code": "I24.9",
            "evidence_for": SUPPORTING,
            "evidence_against": self._evidence_against,
            "uncertainty_note": "Research hypothesis for clinician review.",
        }
        return LLMResponse(content=json.dumps({"hypotheses": [hypothesis]}), model="stub")


class OfflineRetriever:
    """Retrieval stub so the test never touches PubMed, RxNorm or OpenFDA."""

    async def retrieve(self, entities: Any, medications: Any) -> tuple[list[Any], list[Any]]:
        return [], []


async def _analyze(
    monkeypatch: pytest.MonkeyPatch, evidence_against: list[dict[str, Any]]
) -> dict[str, Any]:
    agent = ClinicalAgentStateMachine(
        extractor=EntityExtractor(use_fallback=True),
        retriever=OfflineRetriever(),  # type: ignore[arg-type]
        reasoner=ReasoningEngine(timeout_seconds=30),
        router=MedicalRouter(anthropic=DifferentialAdapter(evidence_against)),
        enforcer=ScopeEnforcer(),
        confidence_threshold=0.6,
    )
    monkeypatch.setattr(main, "_agent", agent)
    monkeypatch.setattr(main, "persist_run", AsyncMock())
    body = {
        "patient_context": {"patient_id_hash": "a" * 64, "chief_complaint": "chest pain"},
        "query": "What is the differential diagnosis?",
    }
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://medagent.test") as client:
        response = await client.post("/analyze", json=body)
    assert response.status_code == 200
    result: dict[str, Any] = response.json()["result"]
    return result


@pytest.mark.asyncio()
async def test_weak_contradicting_evidence_does_not_suppress_escalation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = await _analyze(monkeypatch, WEAKLY_CONTRADICTING)

    assert (result["state_reached"], result["escalated"]) == ("ESCALATE", True)
    assert result["overall_confidence"] < 0.6
    assert result["ranked_hypotheses"][0]["bayesian_score"] <= 0.5


@pytest.mark.asyncio()
async def test_contradicting_evidence_never_raises_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    without_against = await _analyze(monkeypatch, [])
    with_against = await _analyze(monkeypatch, WEAKLY_CONTRADICTING)

    assert with_against["overall_confidence"] <= without_against["overall_confidence"]
