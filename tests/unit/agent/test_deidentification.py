"""/analyze inputs are de-identified before retrieval or any LLM call (SAFETY.md §3.5)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from medagent.agent.state_machine import ClinicalAgentStateMachine
from medagent.api import main
from medagent.extraction.ner import EntityExtractor
from medagent.llm.base import BaseLLMAdapter, LLMResponse
from medagent.llm.router import MedicalRouter
from medagent.models import ClinicalQuery, FHIRPatientContext, LabResult, Medication
from medagent.reasoning.engine import ReasoningEngine
from medagent.safety.scope_enforcer import ScopeEnforcer

CANARIES = (
    "Canary",  # surname, introduced by an honorific or a "Name:" label
    "87654321",  # MRN
    "415-555-0199",  # phone
    "jane.canary@example.org",  # email
    "03/14/1961",  # date of birth
)


class RecordingAdapter(BaseLLMAdapter):
    """Stub LLM that records every prompt and returns a minimal differential."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

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
        self.prompts.append(prompt)
        hypothesis = {
            "label": "Acute coronary syndrome",
            "icd_code": "I24.9",
            "evidence_for": [{"statement": "Crushing substernal chest pain", "strength": 0.8}],
            "evidence_against": [],
            "uncertainty_note": "Research hypothesis for clinician review.",
        }
        return LLMResponse(content=json.dumps({"hypotheses": [hypothesis]}), model="stub")


class OfflineRetriever:
    """Retrieval stub so the test never touches PubMed, RxNorm or OpenFDA."""

    async def retrieve(self, entities: Any, medications: Any) -> tuple[list[Any], list[Any]]:
        return [], []


def _canary_query() -> ClinicalQuery:
    context = FHIRPatientContext(
        patient_id_hash="MRN 87654321",
        age=63,
        sex="female",
        chief_complaint=(
            "Mrs. Jane Canary (MRN 87654321, DOB 03/14/1961) reports crushing substernal "
            "chest pain; call 415-555-0199 or jane.canary@example.org"
        ),
        clinical_notes="Patient name: Jane Canary. Troponin I elevated; aspirin given.",
        diagnoses_history=["Hypertension per Dr. Canary"],
        medications=[Medication(name="aspirin", dosage="81mg", route="oral")],
        lab_results=[LabResult(test_name="Troponin I", value="2.4", unit="ng/mL", abnormal=True)],
        allergies=["Penicillin (reported by Ms. Canary)"],
    )
    return ClinicalQuery(
        patient_context=context,
        query="Differential for Mrs. Canary, MRN 87654321, phone 415-555-0199?",
    )


@pytest.mark.asyncio()
async def test_canary_identifiers_never_reach_the_llm_prompt() -> None:
    adapter = RecordingAdapter()
    agent = ClinicalAgentStateMachine(
        extractor=EntityExtractor(use_fallback=True),
        retriever=OfflineRetriever(),  # type: ignore[arg-type]
        reasoner=ReasoningEngine(timeout_seconds=30),
        router=MedicalRouter(anthropic=adapter),
        enforcer=ScopeEnforcer(),
    )

    result = await agent.run(_canary_query())

    assert adapter.prompts, "the stub LLM was never called"
    sent = "\n".join(adapter.prompts)
    for canary in CANARIES:
        assert canary not in sent
        assert canary not in result.query
    assert "crushing substernal chest pain" in sent
    assert "[REDACTED-NAME]" in sent


def _agent(adapter: RecordingAdapter) -> ClinicalAgentStateMachine:
    return ClinicalAgentStateMachine(
        extractor=EntityExtractor(use_fallback=True),
        retriever=OfflineRetriever(),  # type: ignore[arg-type]
        reasoner=ReasoningEngine(timeout_seconds=30),
        router=MedicalRouter(anthropic=adapter),
        enforcer=ScopeEnforcer(),
    )


@pytest.mark.asyncio()
async def test_malformed_raw_fhir_is_a_client_error(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = RecordingAdapter()
    monkeypatch.setattr(main, "_agent", _agent(adapter))
    body = {
        "patient_context": {
            "patient_id_hash": "a" * 64,
            "chief_complaint": "chest pain",
            "raw_fhir": {"resourceType": "Bundle", "entry": [{"resource": None}]},
        },
        "query": "What is the differential diagnosis?",
    }

    transport = httpx.ASGITransport(app=main.app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://medagent.test") as client:
        response = await client.post("/analyze", json=body)

    assert response.status_code == 400
    assert "raw_fhir" in response.json()["detail"]
    assert adapter.prompts == []
