"""Tests for the ClinicalAgentStateMachine."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from medagent.agent.state_machine import (
    ClinicalAgentStateMachine,
    RunContext,
    StateMachineError,
)
from medagent.models import (
    AgentState,
    ClinicalEntity,
    ClinicalQuery,
    FHIRPatientContext,
    Hypothesis,
    RetrievedDocument,
)


@pytest.fixture()
def patient_context() -> FHIRPatientContext:
    """Return a minimal FHIRPatientContext for testing."""
    return FHIRPatientContext(
        patient_id_hash="abc" * 21 + "ab",  # 64-char string
        chief_complaint="Chest pain and shortness of breath",
        clinical_notes="Patient reports 3-day history of worsening chest pain.",
    )


@pytest.fixture()
def clinical_query(patient_context: FHIRPatientContext) -> ClinicalQuery:
    """Return a ClinicalQuery for testing."""
    return ClinicalQuery(
        patient_context=patient_context,
        query="What are the most likely diagnoses?",
    )


@pytest.fixture()
def mock_extractor() -> MagicMock:
    """Return a mock EntityExtractor."""
    extractor = MagicMock()
    extractor.extract = AsyncMock(
        return_value=[
            ClinicalEntity(text="chest pain", label="DISEASE"),
            ClinicalEntity(text="shortness of breath", label="DISEASE"),
        ]
    )
    extractor.get_mesh_terms = MagicMock(return_value=["Chest Pain"])
    return extractor


@pytest.fixture()
def mock_retriever() -> MagicMock:
    """Return a mock RetrievalOrchestrator."""
    retriever = MagicMock()
    retriever.retrieve = AsyncMock(
        return_value=(
            [
                RetrievedDocument(
                    source="pubmed",
                    doc_id="12345",
                    title="Cardiac causes of chest pain",
                    snippet="Myocardial infarction must be ruled out...",
                    relevance_score=0.8,
                )
            ],
            [],  # no drug interactions
        )
    )
    return retriever


@pytest.fixture()
def mock_reasoner(clinical_query: ClinicalQuery) -> MagicMock:
    """Return a mock ReasoningEngine."""
    from medagent.models import EvidenceItem

    reasoner = MagicMock()
    reasoner.reason = AsyncMock(
        return_value=[
            Hypothesis(
                label="Myocardial Infarction",
                evidence_for=[
                    EvidenceItem(
                        direction="FOR",
                        statement="Chest pain with radiation",
                        strength=0.8,
                    )
                ],
                evidence_against=[],
                bayesian_score=0.75,
                rank=1,
            )
        ]
    )
    return reasoner


@pytest.fixture()
def mock_router() -> MagicMock:
    """Return a mock MedicalRouter."""
    return MagicMock()


@pytest.fixture()
def mock_enforcer() -> MagicMock:
    """Return a mock ScopeEnforcer."""
    enforcer = MagicMock()
    enforcer.check_query_in_scope = MagicMock()  # no-op
    return enforcer


@pytest.fixture()
def agent(
    mock_extractor: MagicMock,
    mock_retriever: MagicMock,
    mock_reasoner: MagicMock,
    mock_router: MagicMock,
    mock_enforcer: MagicMock,
) -> ClinicalAgentStateMachine:
    """Return a fully mocked ClinicalAgentStateMachine."""
    return ClinicalAgentStateMachine(
        extractor=mock_extractor,
        retriever=mock_retriever,
        reasoner=mock_reasoner,
        router=mock_router,
        enforcer=mock_enforcer,
        confidence_threshold=0.6,
    )


class TestStateMachineTransitions:
    """Tests for valid/invalid state transitions."""

    def test_valid_transition_succeeds(self, clinical_query: ClinicalQuery) -> None:
        """A valid state transition must update current_state and state_history."""
        ctx = RunContext(query=clinical_query)
        agent = ClinicalAgentStateMachine.__new__(ClinicalAgentStateMachine)
        agent._confidence_threshold = 0.6  # type: ignore[attr-defined]
        agent._transition(ctx, AgentState.ENTITY_EXTRACTION)
        assert ctx.current_state == AgentState.ENTITY_EXTRACTION
        assert AgentState.INTAKE in ctx.state_history

    def test_invalid_transition_raises(self, clinical_query: ClinicalQuery) -> None:
        """An invalid state transition must raise StateMachineError."""
        ctx = RunContext(query=clinical_query)
        agent = ClinicalAgentStateMachine.__new__(ClinicalAgentStateMachine)
        with pytest.raises(StateMachineError):
            # INTAKE cannot jump directly to OUTPUT
            agent._transition(ctx, AgentState.OUTPUT)


class TestAgentRun:
    """Tests for the full agent run loop."""

    @pytest.mark.asyncio()
    async def test_successful_run_reaches_output(
        self,
        agent: ClinicalAgentStateMachine,
        clinical_query: ClinicalQuery,
    ) -> None:
        """A successful run must reach OUTPUT or ESCALATE state."""
        result = await agent.run(clinical_query)
        assert result.state_reached in {AgentState.OUTPUT, AgentState.ESCALATE}

    @pytest.mark.asyncio()
    async def test_result_has_mandatory_disclaimer(
        self,
        agent: ClinicalAgentStateMachine,
        clinical_query: ClinicalQuery,
    ) -> None:
        """The result disclaimer must always be present."""
        result = await agent.run(clinical_query)
        assert "RESEARCH USE ONLY" in result.disclaimer

    @pytest.mark.asyncio()
    async def test_scope_violation_causes_error_state(
        self,
        mock_extractor: MagicMock,
        mock_retriever: MagicMock,
        mock_reasoner: MagicMock,
        mock_router: MagicMock,
        clinical_query: ClinicalQuery,
    ) -> None:
        """A scope violation must result in ERROR state, not propagate as an exception."""
        from medagent.safety.scope_enforcer import ScopeViolationError

        enforcer = MagicMock()
        enforcer.check_query_in_scope = MagicMock(side_effect=ScopeViolationError("Out of scope"))
        agent = ClinicalAgentStateMachine(
            extractor=mock_extractor,
            retriever=mock_retriever,
            reasoner=mock_reasoner,
            router=mock_router,
            enforcer=enforcer,
        )
        result = await agent.run(clinical_query)
        assert result.state_reached == AgentState.ERROR
        assert result.escalated is True

    @pytest.mark.asyncio()
    async def test_low_confidence_triggers_escalate(
        self,
        mock_extractor: MagicMock,
        mock_retriever: MagicMock,
        mock_router: MagicMock,
        mock_enforcer: MagicMock,
        clinical_query: ClinicalQuery,
    ) -> None:
        """Low-confidence hypotheses must trigger ESCALATE state."""
        low_confidence_reasoner = MagicMock()
        low_confidence_reasoner.reason = AsyncMock(
            return_value=[
                Hypothesis(
                    label="Unknown",
                    evidence_for=[],
                    evidence_against=[],
                    bayesian_score=0.1,
                    rank=1,
                )
            ]
        )
        agent = ClinicalAgentStateMachine(
            extractor=mock_extractor,
            retriever=mock_retriever,
            reasoner=low_confidence_reasoner,
            router=mock_router,
            enforcer=mock_enforcer,
            confidence_threshold=0.6,
        )
        result = await agent.run(clinical_query)
        assert result.escalated is True
        assert result.state_reached == AgentState.ESCALATE

    @pytest.mark.asyncio()
    async def test_empty_hypotheses_escalates_even_with_zero_threshold(
        self,
        mock_extractor: MagicMock,
        mock_retriever: MagicMock,
        mock_router: MagicMock,
        mock_enforcer: MagicMock,
        clinical_query: ClinicalQuery,
    ) -> None:
        """No hypotheses must ESCALATE even when the confidence threshold is 0.

        With ``confidence_threshold=0.0`` the mean-confidence gate (``0.0 < 0.0``)
        is False, so without an explicit empty-hypothesis guard the run would
        reach OUTPUT with zero hypotheses — an unsafe result.
        """
        empty_reasoner = MagicMock()
        empty_reasoner.reason = AsyncMock(return_value=[])
        agent = ClinicalAgentStateMachine(
            extractor=mock_extractor,
            retriever=mock_retriever,
            reasoner=empty_reasoner,
            router=mock_router,
            enforcer=mock_enforcer,
            confidence_threshold=0.0,
        )
        result = await agent.run(clinical_query)
        assert result.state_reached == AgentState.ESCALATE
        assert result.escalated is True
        assert result.ranked_hypotheses == []

    @pytest.mark.asyncio()
    async def test_contradictory_evidence_triggers_escalate(
        self,
        mock_extractor: MagicMock,
        mock_retriever: MagicMock,
        mock_router: MagicMock,
        mock_enforcer: MagicMock,
        clinical_query: ClinicalQuery,
    ) -> None:
        """A hypothesis with strong FOR and AGAINST evidence must ESCALATE."""
        from medagent.models import EvidenceItem

        contradictory_reasoner = MagicMock()
        contradictory_reasoner.reason = AsyncMock(
            return_value=[
                Hypothesis(
                    label="Ambiguous diagnosis",
                    evidence_for=[
                        EvidenceItem(
                            direction="FOR", statement="Strong supporting finding", strength=0.9
                        )
                    ],
                    evidence_against=[
                        EvidenceItem(
                            direction="AGAINST",
                            statement="Strong contradicting finding",
                            strength=0.9,
                        )
                    ],
                    bayesian_score=0.9,
                    rank=1,
                )
            ]
        )
        agent = ClinicalAgentStateMachine(
            extractor=mock_extractor,
            retriever=mock_retriever,
            reasoner=contradictory_reasoner,
            router=mock_router,
            enforcer=mock_enforcer,
            confidence_threshold=0.6,
        )
        result = await agent.run(clinical_query)
        assert result.state_reached == AgentState.ESCALATE
        assert result.escalated is True
        assert any("Contradictory" in flag for flag in result.uncertainty_flags)
