"""/analyze inputs are de-identified before retrieval or any LLM call (SAFETY.md §3.5)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from medagent.agent.state_machine import ClinicalAgentStateMachine
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
