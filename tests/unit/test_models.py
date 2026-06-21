"""Unit tests for core Pydantic domain models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from medagent.models import (
    AgentState,
    ClinicalQuery,
    ClinicalReasoning,
    DrugInteractionWarning,
    EvidenceItem,
    FHIRPatientContext,
    Severity,
)


class TestEvidenceItem:
    """Tests for EvidenceItem validation."""

    def test_valid_for_direction(self) -> None:
        """EvidenceItem with direction='FOR' must be constructible."""
        item = EvidenceItem(direction="FOR", statement="Symptom matches presentation")
        assert item.direction == "FOR"

    def test_valid_against_direction(self) -> None:
        """EvidenceItem with direction='AGAINST' must be constructible."""
        item = EvidenceItem(direction="AGAINST", statement="Lab value inconsistent")
        assert item.direction == "AGAINST"

    def test_invalid_direction_raises(self) -> None:
        """Invalid direction must raise a ValidationError."""
        with pytest.raises(ValidationError):
            EvidenceItem(direction="MAYBE", statement="Something")

    def test_strength_clamped_to_range(self) -> None:
        """Strength must be in [0, 1]."""
        with pytest.raises(ValidationError):
            EvidenceItem(direction="FOR", statement="x", strength=1.5)

    def test_frozen_model_immutable(self) -> None:
        """EvidenceItem is frozen — mutation must raise."""
        item = EvidenceItem(direction="FOR", statement="s")
        with pytest.raises(ValidationError):
            item.direction = "AGAINST"  # type: ignore[misc]


class TestDrugInteractionWarning:
    """Tests for the dual-source validation invariant on DrugInteractionWarning."""

    def test_requires_two_sources(self) -> None:
        """A warning with fewer than 2 sources must raise at construction time."""
        with pytest.raises(Exception, match="≥2"):
            DrugInteractionWarning(
                drug_a="metformin",
                drug_b="ibuprofen",
                severity=Severity.MODERATE,
                mechanism="mechanism",
                clinical_consequence="consequence",
                sources=["rxnorm"],  # only 1 source
            )

    def test_two_sources_valid(self) -> None:
        """A warning with exactly 2 sources must be constructible."""
        warning = DrugInteractionWarning(
            drug_a="warfarin",
            drug_b="aspirin",
            severity=Severity.HIGH,
            mechanism="Additive anticoagulation",
            clinical_consequence="Increased bleeding risk",
            sources=["rxnorm", "openfda"],
        )
        assert warning.validated is False  # default
        assert len(warning.sources) == 2


class TestClinicalQuery:
    """Tests for ClinicalQuery input model."""

    def test_inputs_hash_deterministic(self) -> None:
        """The same patient context + query must always produce the same inputs_hash."""
        ctx = FHIRPatientContext(
            patient_id_hash="abc123",
            chief_complaint="chest pain",
        )
        q1 = ClinicalQuery(patient_context=ctx, query="differential diagnosis?")
        q2 = ClinicalQuery(patient_context=ctx, query="differential diagnosis?")
        assert q1.inputs_hash == q2.inputs_hash

    def test_inputs_hash_changes_with_query(self) -> None:
        """Different queries must produce different hashes."""
        ctx = FHIRPatientContext(
            patient_id_hash="abc123",
            chief_complaint="chest pain",
        )
        q1 = ClinicalQuery(patient_context=ctx, query="query A")
        q2 = ClinicalQuery(patient_context=ctx, query="query B")
        assert q1.inputs_hash != q2.inputs_hash

    def test_session_id_is_uuid(self) -> None:
        """Auto-generated session_id must be a non-empty string."""
        ctx = FHIRPatientContext(patient_id_hash="x", chief_complaint="y")
        query = ClinicalQuery(patient_context=ctx, query="test")
        assert len(query.session_id) > 0


class TestClinicalReasoning:
    """Tests for the ClinicalReasoning output model."""

    def test_default_disclaimer_present(self) -> None:
        """The mandatory disclaimer must always be populated."""
        result = ClinicalReasoning(
            session_id="s1",
            query="test",
            state_reached=AgentState.OUTPUT,
            overall_confidence=0.8,
        )
        assert "RESEARCH USE ONLY" in result.disclaimer

    def test_escalated_defaults_to_false(self) -> None:
        """Escalated flag must default to False."""
        result = ClinicalReasoning(
            session_id="s1",
            query="test",
            state_reached=AgentState.OUTPUT,
            overall_confidence=0.9,
        )
        assert result.escalated is False

    def test_confidence_range_validation(self) -> None:
        """overall_confidence outside [0, 1] must raise."""
        with pytest.raises(ValidationError):
            ClinicalReasoning(
                session_id="s1",
                query="test",
                state_reached=AgentState.OUTPUT,
                overall_confidence=1.5,  # invalid
            )
