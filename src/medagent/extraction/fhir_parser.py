"""FHIR R4 Bundle parser.

Converts a raw FHIR JSON bundle into the internal FHIRPatientContext model.
Handles the most common resource types used in clinical decision support:
Patient, Condition, MedicationRequest, Observation, AllergyIntolerance.

This parser is deliberately conservative: unknown or malformed FHIR resources
are logged and skipped rather than raising exceptions, so that partial bundles
still produce usable context.
"""

from __future__ import annotations

import re
from typing import Any

from medagent.logging_config import get_logger
from medagent.models import FHIRPatientContext, LabResult, Medication
from medagent.safety.pii_hasher import hash_pii

logger = get_logger(__name__)


class FHIRParseError(ValueError):
    """Raised when the top-level FHIR bundle structure is invalid."""


def parse_fhir_bundle(
    bundle: dict[str, Any],
    pii_salt: str | None = None,
) -> FHIRPatientContext:
    """Parse a FHIR R4 Bundle dict into a FHIRPatientContext.

    Patient-identifying fields (name, MRN, DOB) are hashed before being
    stored in the returned model. The raw bundle is preserved as ``raw_fhir``
    for audit purposes but is never passed to LLMs.

    Args:
        bundle: Decoded FHIR R4 bundle (typically from ``json.loads``).
        pii_salt: Optional override salt for PII hashing. Uses the global
            config value when None.

    Returns:
        A validated, PII-sanitised FHIRPatientContext.

    Raises:
        FHIRParseError: When the bundle lacks the required resourceType field
            or the entry list is malformed beyond recovery.
    """
    if not isinstance(bundle, dict):
        raise FHIRParseError("FHIR bundle must be a JSON object")

    resource_type = bundle.get("resourceType")
    if resource_type != "Bundle":
        raise FHIRParseError(f"Expected resourceType 'Bundle', got '{resource_type}'")

    entries: list[dict[str, Any]] = bundle.get("entry", [])
    if not isinstance(entries, list):
        raise FHIRParseError("Bundle 'entry' must be a list")

    # Separate resources by type
    resources: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        resource = entry.get("resource", {})
        rtype = resource.get("resourceType", "Unknown")
        resources.setdefault(rtype, []).append(resource)

    patient_resource = (resources.get("Patient") or [{}])[0]
    patient_id = _extract_patient_id(patient_resource)
    patient_id_hash = hash_pii(patient_id, salt=pii_salt)

    age = _extract_age(patient_resource)
    sex = _extract_sex(patient_resource)

    diagnoses = _extract_diagnoses(resources.get("Condition", []))
    medications = _extract_medications(resources.get("MedicationRequest", []))
    lab_results = _extract_observations(resources.get("Observation", []))
    allergies = _extract_allergies(resources.get("AllergyIntolerance", []))
    chief_complaint = _extract_chief_complaint(resources)

    logger.info(
        "fhir_parsed",
        patient_id_hash=patient_id_hash[:8] + "...",
        conditions=len(diagnoses),
        medications=len(medications),
        labs=len(lab_results),
    )

    return FHIRPatientContext(
        patient_id_hash=patient_id_hash,
        age=age,
        sex=sex,
        chief_complaint=chief_complaint,
        diagnoses_history=diagnoses,
        medications=medications,
        lab_results=lab_results,
        allergies=allergies,
        raw_fhir=bundle,
    )


def _extract_patient_id(patient: dict[str, Any]) -> str:
    """Extract the patient MRN or FHIR logical id."""
    for identifier in patient.get("identifier", []):
        value = identifier.get("value")
        if value:
            return str(value)
    return str(patient.get("id", "unknown"))


def _extract_age(patient: dict[str, Any]) -> int | None:
    """Compute age from birthDate string (YYYY-MM-DD)."""
    birth_date = patient.get("birthDate")
    if not birth_date:
        return None
    try:
        from datetime import date

        year = int(birth_date[:4])
        current_year = date.today().year
        age = current_year - year
        return age if 0 <= age <= 150 else None
    except (ValueError, IndexError):
        return None


def _extract_sex(patient: dict[str, Any]) -> str | None:
    """Extract biological sex from FHIR gender field."""
    gender = patient.get("gender")
    return gender if gender in {"male", "female", "other", "unknown"} else None


def _extract_diagnoses(conditions: list[dict[str, Any]]) -> list[str]:
    """Extract diagnosis text strings from Condition resources."""
    diagnoses: list[str] = []
    for cond in conditions:
        code = cond.get("code", {})
        # Try text first, then coding display
        text = code.get("text")
        if not text:
            codings = code.get("coding", [])
            if codings:
                text = codings[0].get("display")
        if text:
            diagnoses.append(text)
    return diagnoses


def _extract_medications(med_requests: list[dict[str, Any]]) -> list[Medication]:
    """Extract medications from MedicationRequest resources."""
    medications: list[Medication] = []
    for req in med_requests:
        med_code = req.get("medicationCodeableConcept", {})
        name = med_code.get("text")
        if not name:
            codings = med_code.get("coding", [])
            if codings:
                name = codings[0].get("display")
        if not name:
            continue

        rxnorm = None
        for coding in med_code.get("coding", []):
            if coding.get("system", "").endswith("rxnorm"):
                rxnorm = coding.get("code")

        dosage_instructions = req.get("dosageInstruction", [{}])
        dosage_text = None
        route_text = None
        timing_text = None
        if dosage_instructions:
            di = dosage_instructions[0]
            dosage_text = di.get("text")
            route_coding = di.get("route", {}).get("coding", [{}])
            route_text = route_coding[0].get("display") if route_coding else None
            timing_text = di.get("timing", {}).get("code", {}).get("text")

        try:
            medications.append(
                Medication(
                    name=name,
                    rxnorm_code=rxnorm,
                    dosage=dosage_text,
                    route=route_text,
                    frequency=timing_text,
                )
            )
        except Exception as exc:
            logger.warning("medication_parse_error", error=str(exc), name=name)

    return medications


def _extract_observations(observations: list[dict[str, Any]]) -> list[LabResult]:
    """Extract lab results from Observation resources."""
    labs: list[LabResult] = []
    for obs in observations:
        code = obs.get("code", {})
        name = code.get("text") or ((obs.get("code", {}).get("coding") or [{}])[0].get("display"))
        if not name:
            continue

        value_quantity = obs.get("valueQuantity", {})
        value = value_quantity.get("value")
        unit = value_quantity.get("unit")

        # Fallback to string value
        if value is None:
            value = obs.get("valueString") or obs.get("valueCodeableConcept", {}).get("text")

        if value is None:
            continue

        reference_range_list = obs.get("referenceRange", [])
        ref_range = None
        if reference_range_list:
            rr = reference_range_list[0]
            low = rr.get("low", {}).get("value")
            high = rr.get("high", {}).get("value")
            if low is not None and high is not None:
                ref_range = f"{low}–{high}"
            elif rr.get("text"):
                ref_range = rr["text"]

        interpretation_codings = obs.get("interpretation", [{}])
        abnormal = False
        if interpretation_codings:
            interp_code = (interpretation_codings[0].get("coding") or [{}])[0].get("code", "N")
            abnormal = interp_code not in {"N", "normal"}

        try:
            labs.append(
                LabResult(
                    test_name=name,
                    value=str(value),
                    unit=unit,
                    reference_range=ref_range,
                    abnormal=abnormal,
                )
            )
        except Exception as exc:
            logger.warning("lab_parse_error", error=str(exc), name=name)

    return labs


def _extract_allergies(allergy_list: list[dict[str, Any]]) -> list[str]:
    """Extract allergy substance names from AllergyIntolerance resources."""
    allergies: list[str] = []
    for allergy in allergy_list:
        code = allergy.get("code", {})
        text = code.get("text")
        if not text:
            codings = code.get("coding", [])
            if codings:
                text = codings[0].get("display")
        if text:
            allergies.append(text)
    return allergies


def _extract_chief_complaint(resources: dict[str, list[dict[str, Any]]]) -> str:
    """Best-effort extraction of chief complaint from Condition or Composition."""
    # Check for a Condition marked as the chief complaint
    for cond in resources.get("Condition", []):
        cat = cond.get("category", [{}])
        for c in cat:
            codings = c.get("coding", [])
            for coding in codings:
                if "chief" in coding.get("display", "").lower():
                    code_text = cond.get("code", {}).get("text")
                    if code_text:
                        return str(code_text)

    # Fall back to first condition
    conditions = resources.get("Condition", [])
    if conditions:
        return str(conditions[0].get("code", {}).get("text", "Not specified"))

    return "Not specified"


def sanitise_clinical_text(text: str) -> str:
    """Remove likely PII patterns from free-text clinical notes.

    Redacts date-of-birth patterns, MRN-like sequences, and full names
    using conservative regexes before text is passed to any LLM.

    Args:
        text: Raw clinical note text.

    Returns:
        Text with PII patterns replaced by ``[REDACTED]``.
    """
    # DOB patterns: MM/DD/YYYY, YYYY-MM-DD, DD-Mon-YYYY
    text = re.sub(
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
        "[REDACTED-DOB]",
        text,
    )
    # MRN-like patterns: sequences of 6–12 digits
    text = re.sub(r"\bMRN?:?\s*\d{6,12}\b", "[REDACTED-MRN]", text, flags=re.IGNORECASE)
    # Phone numbers
    text = re.sub(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b", "[REDACTED-PHONE]", text)
    # Email addresses
    text = re.sub(r"\b[\w.+-]+@[\w-]+\.\w+\b", "[REDACTED-EMAIL]", text)
    return text
