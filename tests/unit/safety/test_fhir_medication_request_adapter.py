"""Tests for FHIR MedicationRequest adapter (safety-panel facing)."""

from __future__ import annotations

from medagent.models import Severity
from medagent.safety import FhirMedicationRequestAdapter as ExportedAdapter
from medagent.safety.fhir_medication_request_adapter import FhirMedicationRequestAdapter


def test_single_medication_request_codeable_concept() -> None:
    payload = {
        "resourceType": "MedicationRequest",
        "status": "active",
        "medicationCodeableConcept": {
            "text": "Amoxicillin 500mg",
            "coding": [
                {
                    "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                    "code": "308182",
                    "display": "Amoxicillin 500 MG",
                }
            ],
        },
        "dosageInstruction": [
            {
                "text": "500 mg",
                "route": {"coding": [{"display": "oral"}]},
                "timing": {"code": {"text": "BID"}},
            }
        ],
    }
    result = FhirMedicationRequestAdapter().adapt(payload)
    assert len(result.medications) == 1
    assert result.medications[0].name == "Amoxicillin 500mg"
    assert result.medications[0].rxnorm_code == "308182"
    assert result.medications[0].dosage == "500 mg"
    assert result.medications[0].route == "oral"
    assert result.medications[0].frequency == "BID"
    assert "RESEARCH USE ONLY" in result.rationale
    assert result.severity is Severity.LOW


def test_list_of_requests() -> None:
    payload = [
        {
            "resourceType": "MedicationRequest",
            "medicationCodeableConcept": {"text": "Metformin"},
        },
        {
            "resourceType": "MedicationRequest",
            "medicationCodeableConcept": {"text": "Lisinopril"},
        },
    ]
    result = FhirMedicationRequestAdapter().adapt(payload)
    assert [m.name for m in result.medications] == ["Metformin", "Lisinopril"]
    assert result.resource_count == 2
    assert result.skipped_count == 0


def test_bundle_entries() -> None:
    payload = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "resourceType": "MedicationRequest",
                    "medicationCodeableConcept": {"text": "Warfarin"},
                }
            },
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "p1",
                }
            },
        ],
    }
    result = FhirMedicationRequestAdapter().adapt(payload)
    assert len(result.medications) == 1
    assert result.medications[0].name == "Warfarin"
    assert result.skipped_count == 1
    assert any("Patient" in n for n in result.notes)


def test_skips_cancelled_and_stopped() -> None:
    payload = [
        {
            "resourceType": "MedicationRequest",
            "status": "cancelled",
            "medicationCodeableConcept": {"text": "Ibuprofen"},
        },
        {
            "resourceType": "MedicationRequest",
            "status": "stopped",
            "medicationCodeableConcept": {"text": "Codeine"},
        },
        {
            "resourceType": "MedicationRequest",
            "status": "active",
            "medicationCodeableConcept": {"text": "Acetaminophen"},
        },
    ]
    result = FhirMedicationRequestAdapter().adapt(payload)
    assert [m.name for m in result.medications] == ["Acetaminophen"]
    assert result.skipped_count == 2


def test_medication_reference_display_fallback() -> None:
    payload = {
        "resourceType": "MedicationRequest",
        "medicationReference": {"display": "Insulin glargine"},
    }
    result = FhirMedicationRequestAdapter().adapt(payload)
    assert result.medications[0].name == "Insulin glargine"
    assert any("medicationReference" in n for n in result.notes)


def test_none_payload() -> None:
    result = FhirMedicationRequestAdapter().adapt(None)
    assert result.medications == []
    assert result.severity is Severity.UNKNOWN
    assert "RESEARCH USE ONLY" in result.rationale


def test_keyed_dict_medication_request_list() -> None:
    payload = {
        "MedicationRequest": [
            {"medicationCodeableConcept": {"coding": [{"display": "Atorvastatin"}]}}
        ]
    }
    result = FhirMedicationRequestAdapter().adapt(payload)
    assert result.medications[0].name == "Atorvastatin"


def test_skips_missing_name() -> None:
    payload = {
        "resourceType": "MedicationRequest",
        "medicationCodeableConcept": {},
    }
    result = FhirMedicationRequestAdapter().adapt(payload)
    assert result.medications == []
    assert result.skipped_count == 1


def test_check_duck_typed_returns_list() -> None:
    results = FhirMedicationRequestAdapter().check(
        {"medicationCodeableConcept": {"text": "Digoxin"}}
    )
    assert len(results) == 1
    assert results[0].medications[0].name == "Digoxin"


def test_exported_from_safety_package() -> None:
    result = ExportedAdapter().adapt(
        {
            "resourceType": "MedicationRequest",
            "medicationCodeableConcept": {"text": "Gabapentin"},
        }
    )
    assert result.medications[0].name == "Gabapentin"
    assert "RESEARCH USE ONLY" in result.rationale
