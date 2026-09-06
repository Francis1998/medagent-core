"""Tests for the deterministic SOAP note structurer."""

from __future__ import annotations

from medagent.models import ClinicalEntity, LabResult, Medication
from medagent.reasoning import SoapStructurer as ExportedStructurer
from medagent.reasoning.soap_structurer import SoapStructurer


def test_structures_chief_complaint_into_subjective() -> None:
    """Chief complaint lands in the subjective section."""
    note = SoapStructurer().structure(chief_complaint="Shortness of breath for 2 days")
    assert "Shortness of breath" in note.subjective
    assert "RESEARCH USE ONLY" in note.rationale


def test_routes_symptom_sentences_to_subjective() -> None:
    """Patient-reported symptom language is treated as subjective."""
    note = SoapStructurer().structure(
        clinical_note="Patient reports chest tightness. Denies fever."
    )
    assert "reports chest tightness" in note.subjective.lower()
    assert "denies fever" in note.subjective.lower()


def test_labs_and_exam_go_to_objective() -> None:
    """Labs and exam cues populate objective."""
    note = SoapStructurer().structure(
        clinical_note="On exam lungs are clear.",
        lab_results=[LabResult(test_name="Troponin", value="0.04", unit="ng/mL", abnormal=True)],
    )
    assert "lungs are clear" in note.objective.lower()
    assert "Troponin=0.04" in note.objective
    assert "abnormal" in note.objective


def test_assessment_from_impression_and_disease_entities() -> None:
    """Impression sentences and disease entities feed assessment."""
    note = SoapStructurer().structure(
        clinical_note="Impression: likely community-acquired pneumonia.",
        entities=[ClinicalEntity(text="pneumonia", label="DISEASE")],
    )
    assert "community-acquired pneumonia" in note.assessment.lower()
    assert "pneumonia" in note.assessment.lower()


def test_plan_is_non_prescriptive() -> None:
    """Plan hints never include prescribe/dose language."""
    note = SoapStructurer().structure(
        clinical_note="Plan: prescribe amoxicillin 500mg TID.",
        medications=[Medication(name="Lisinopril 10mg")],
        lab_results=[LabResult(test_name="WBC", value="14", unit="k/uL", abnormal=True)],
    )
    lowered = note.plan.lower()
    assert "500mg" not in lowered
    assert " amoxicillin" not in lowered
    assert "tid" not in lowered
    assert "consider clinician review" in lowered
    assert "lisinopril" in lowered
    assert "wbc" in lowered
    assert (
        "medication-order" in lowered
        or "non-prescriptive" in lowered
        or "no medication order" in lowered
    )


def test_empty_inputs_yield_placeholders() -> None:
    """Empty inputs still return a SoapNote with placeholders and rationale."""
    note = SoapStructurer().structure()
    assert note.subjective == "(none documented)"
    assert note.objective == "(none documented)"
    assert note.assessment == "(none documented)"
    assert "non-prescriptive" in note.plan.lower()
    assert "RESEARCH USE ONLY" in note.rationale


def test_exported_from_reasoning_package() -> None:
    """SoapStructurer is exported from medagent.reasoning."""
    note = ExportedStructurer().structure(chief_complaint="Cough")
    assert "Cough" in note.subjective


def test_dedupes_repeated_plan_hints() -> None:
    """Duplicate medication hints are collapsed."""
    note = SoapStructurer().structure(
        medications=[Medication(name="Metformin"), Medication(name="Metformin")]
    )
    assert note.plan.lower().count("metformin") == 1
