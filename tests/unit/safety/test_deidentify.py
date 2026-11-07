"""Unit tests for :mod:`medagent.safety.deidentify` (SAFETY.md §3.5)."""

from __future__ import annotations

from typing import Any

import pytest

from medagent.models import (
    ClinicalQuery,
    FHIRPatientContext,
    LabResult,
    Medication,
    VitalSign,
)
from medagent.safety.deidentify import deidentify_query
from medagent.safety.pii_hasher import hash_pii

DIGEST = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"


def _query(patient_id_hash: str = DIGEST, **context: object) -> ClinicalQuery:
    fields: dict[str, object] = {"patient_id_hash": patient_id_hash, "chief_complaint": "cough"}
    fields.update(context)
    return ClinicalQuery(patient_context=FHIRPatientContext(**fields), query="Differential?")


def test_every_narrative_field_is_sanitised() -> None:
    query = ClinicalQuery(
        patient_context=FHIRPatientContext(
            patient_id_hash=DIGEST,
            chief_complaint="Mr. John Canary, call 415-555-0199",
            clinical_notes="Name: John Canary; email john@canary.example.org",
            diagnoses_history=["Asthma (MRN 12345678)"],
            allergies=["Penicillin per Dr. Canary"],
        ),
        query="Seen 03/14/2026 - SSN 123-45-6789?",
    )

    clean = deidentify_query(query)
    context = clean.patient_context

    assert context.chief_complaint == "[REDACTED-NAME], call [REDACTED-PHONE]"
    assert context.clinical_notes == "Name: [REDACTED-NAME]; email [REDACTED-EMAIL]"
    assert context.diagnoses_history == ["Asthma ([REDACTED-MRN])"]
    assert context.allergies == ["Penicillin per [REDACTED-NAME]"]
    assert clean.query == "Seen [REDACTED-DOB] - SSN [REDACTED-SSN]?"
    assert clean.session_id == query.session_id


def test_patient_ids_are_hashed_unless_already_a_digest() -> None:
    raw = deidentify_query(_query(patient_id_hash="MRN-0042"))
    digest = deidentify_query(_query(patient_id_hash=DIGEST))
    upper = deidentify_query(_query(patient_id_hash=DIGEST.upper()))

    assert raw.patient_context.patient_id_hash == hash_pii("MRN-0042")
    assert digest.patient_context.patient_id_hash == DIGEST
    assert upper.patient_context.patient_id_hash == DIGEST.upper()


def test_structured_clinical_records_are_unchanged() -> None:
    medications = [Medication(name="warfarin", dosage="5 mg", route="oral", frequency="daily")]
    labs = [LabResult(test_name="INR", value="3.4", unit="ratio", abnormal=True)]
    vitals = [VitalSign(name="heart rate", value=88.0, unit="bpm")]
    query = _query(
        age=81, sex="female", medications=medications, lab_results=labs, vital_signs=vitals
    )

    context = deidentify_query(query).patient_context

    assert context.medications == medications
    assert context.lab_results == labs
    assert context.vital_signs == vitals
    assert (context.age, context.sex) == (81, "female")


def test_raw_fhir_patient_identifiers_are_removed() -> None:
    patient = {
        "resourceType": "Patient",
        "id": "p1",
        "name": [{"family": "Canary"}],
        "birthDate": "1961-03-14",
        "identifier": [{"value": "MRN-0042"}],
        "telecom": [{"value": "415-555-0199"}],
        "address": [{"city": "Springfield"}],
    }
    bundle = {"resourceType": "Bundle", "entry": [{"resource": patient}]}

    context = deidentify_query(_query(raw_fhir=bundle)).patient_context

    assert context.raw_fhir is not None
    kept = context.raw_fhir["entry"][0]["resource"]
    assert kept == {"resourceType": "Patient", "id": "p1"}
    assert bundle["entry"][0]["resource"]["name"] == [{"family": "Canary"}]


@pytest.mark.parametrize(
    "raw_fhir",
    [
        {"entry": [{"resource": None}]},
        {"entry": ["not-an-object"]},
        {"entry": {"resource": {"resourceType": "Patient", "name": [{"family": "Canary"}]}}},
        {"resourceType": "Patient", "name": [{"family": "Canary"}]},
    ],
)
def test_malformed_raw_fhir_is_rejected_with_a_value_error(raw_fhir: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="raw_fhir"):
        deidentify_query(_query(raw_fhir=raw_fhir))
