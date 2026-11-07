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

from medagent.extraction.ner import is_clinical_term
from medagent.logging_config import get_logger
from medagent.models import FHIRPatientContext, LabResult, Medication, VitalSign
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
    observations = resources.get("Observation", [])
    lab_results = _extract_observations(observations)
    vital_signs = _extract_vital_signs(observations)
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
        vital_signs=vital_signs,
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
    """Compute age from a FHIR birthDate.

    FHIR ``birthDate`` may be a partial date (``YYYY``, ``YYYY-MM`` or
    ``YYYY-MM-DD``). The birthday-not-yet-reached case is accounted for at the
    finest granularity available: month and day for a full date, month alone for
    a ``YYYY-MM`` date, so the age is not overstated by one year. With only the
    year, a year-difference best effort is used.
    """
    birth_date = patient.get("birthDate")
    if not birth_date:
        return None
    try:
        from datetime import date

        parts = birth_date.split("-")
        year = int(parts[0])
        today = date.today()
        age = today.year - year
        if len(parts) >= 3:
            birth_month = int(parts[1])
            birth_day = int(parts[2])
            if (today.month, today.day) < (birth_month, birth_day):
                age -= 1
        elif len(parts) == 2:
            birth_month = int(parts[1])
            if today.month < birth_month:
                age -= 1
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
            logger.warning("medication_parse_error", error_type=type(exc).__name__)

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
            logger.warning("lab_parse_error", error_type=type(exc).__name__)

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


# A name word is a Unicode word that may contain combining accents (e + U+0301)
# and inner apostrophes or hyphens (O'Neil-Smith, Núñez), or up to three
# initials with their dots (Q., J.Q.). Words are joined by spaces or tabs only
# (a "Surname, Given" comma is also allowed after a label), so a match never
# continues onto the next line; at most six words are considered after the cue,
# and no word of a run may be an honorific, so each title gets its own match.
_MARKS = "\u0300-\u036f\u1ab0-\u1aff\u1dc0-\u1dff\u20d0-\u20ff\ufe20-\ufe2f"
_HONORIFICS = r"(?:Mrs|Mr|Ms|Miss|Mx|Dr|Prof)"
_NAME_WORD = (
    rf"(?:[^\W\d_][{_MARKS}]*\.){{1,3}}(?!\w)"
    rf"|[^\W\d_](?:[^\W\d_]|[{_MARKS}]|['’-](?=[^\W\d_]))*"
)
_NOT_TITLE = rf"(?!{_HONORIFICS}\b)"
_NAME_RUN = rf"{_NOT_TITLE}(?:{_NAME_WORD})(?:[ \t]+{_NOT_TITLE}(?:{_NAME_WORD})){{0,5}}"
_LABELLED_RUN = (
    rf"{_NOT_TITLE}(?:{_NAME_WORD})(?:(?:[ \t]*,[ \t]*|[ \t]+){_NOT_TITLE}(?:{_NAME_WORD})){{0,5}}"
)
# Lower-case surname particles kept inside a cued name (van der Canary, de la Cruz).
_NAME_PARTICLES = frozenset(
    {"al", "bin", "da", "das", "de", "del", "della", "der", "di", "do", "dos", "du", "ibn"}
    | {"la", "le", "st", "ten", "ter", "van", "von"}
)
_HONORIFIC_NAME = re.compile(rf"\b{_HONORIFICS}\.?[ \t]+(?P<run>{_NAME_RUN})")
# The label must start the text, a line or a clause, so "Drug name: Warfarin"
# and "Generic name: ..." are never treated as personal names.
_LABELLED_NAME = re.compile(
    rf"(?P<label>(?<![^\n;.,(|])[ \t]*(?i:patient[ \t]+name|name)[ \t]*:[ \t]*)"
    rf"(?P<run>{_LABELLED_RUN})"
)


def _redact_name_run(match: re.Match[str]) -> str:
    """Replace the cue and the name words of a run, keeping what follows.

    The name ends at the last capitalised word before the first lower-case word
    that is not a surname particle, or before a known clinical term such as
    "COPD". A labelled match keeps its label.
    """
    parts = re.split(r"([ \t]*,[ \t]*|[ \t]+)", match.group("run"))
    name_end = 0
    for index in range(0, len(parts), 2):
        word = parts[index]
        if word[:1].isupper() and not (name_end and is_clinical_term(word.rstrip("."))):
            name_end = index + 1
        elif not (name_end and word.lower() in _NAME_PARTICLES):
            break
    if name_end == 0:
        return match.group(0)
    label = match.groupdict().get("label") or ""
    return label + "[REDACTED-NAME]" + "".join(parts[name_end:])


def sanitise_clinical_text(text: str) -> str:
    """Remove likely PII patterns from free-text clinical notes.

    Redacts dates (``MM/DD/YYYY``, ``YYYY-MM-DD``, ``DD-Mon-YYYY``), ``MR``/``MRN``-
    labelled numbers, US Social Security numbers, phone numbers, email addresses,
    and capitalised names introduced by an honorific (Mr, Mrs, Ms, Miss, Mx, Dr,
    Prof) or by a ``Name:``/``Patient name:`` label that starts the text, a line
    or a clause. Names without such a cue are not detected.

    Args:
        text: Raw clinical note text.

    Returns:
        Text with PII patterns replaced by ``[REDACTED-*]`` placeholders.
    """
    # DOB patterns: MM/DD/YYYY (or with '-' separators)
    text = re.sub(
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
        "[REDACTED-DOB]",
        text,
    )
    # ISO-8601 dates (YYYY-MM-DD) — the FHIR ``birthDate`` format. The numeric
    # pattern above cannot match these because its first group is 1–2 digits.
    text = re.sub(
        r"\b\d{4}-\d{2}-\d{2}\b",
        "[REDACTED-DOB]",
        text,
    )
    # DD-Mon-YYYY (e.g. 15-Jan-2020)
    text = re.sub(
        r"\b\d{1,2}-[A-Za-z]{3}-\d{4}\b",
        "[REDACTED-DOB]",
        text,
    )
    # MRN-labelled numbers of any length; a bare "MR" label needs 6–12 digits so
    # that clinical text such as "MR 2+" (mitral regurgitation) is kept.
    text = re.sub(r"\bMRN\s*[:#]?\s*\d{1,12}\b", "[REDACTED-MRN]", text, flags=re.IGNORECASE)
    text = re.sub(r"\bMR:?\s*\d{6,12}\b", "[REDACTED-MRN]", text, flags=re.IGNORECASE)
    # US Social Security numbers (NNN-NN-NNNN). Neither the date patterns above
    # (which need 1-2 digit leading groups) nor the phone pattern below (which
    # needs a 3-digit middle group) match the SSN 3-2-4 shape, so SSNs listed as
    # PII in the de-identification contract otherwise leaked through unredacted.
    text = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED-SSN]", text)
    # Phone numbers, including an optional country code and a parenthesised area
    # code. A leading ``\b`` cannot match before the ``(`` of a ``(415) 555-1234``
    # number (``(`` is a non-word character), so such numbers previously leaked
    # through unredacted; ``(?<!\w)``/``(?!\w)`` boundaries hold whether the
    # number starts with a digit, a ``(``, or a ``+``. A separator (or the parens)
    # is still required so a bare run of ten digits is not treated as a phone.
    text = re.sub(
        r"(?<!\w)(?:\+?\d{1,3}[-.\s])?(?:\(\d{3}\)[-.\s]?|\d{3}[-.\s])\d{3}[-.\s]?\d{4}(?!\w)",
        "[REDACTED-PHONE]",
        text,
    )
    # Email addresses. The domain must match *every* dotted label, not just the
    # first, so a multi-label domain (a subdomain such as ``mail.hospital.org``
    # or a compound TLD such as ``acme.co.uk``) is fully redacted rather than
    # leaving a trailing ``.org`` / ``.co.uk`` fragment revealing the organisation.
    text = re.sub(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b", "[REDACTED-EMAIL]", text)
    # Personal names, only when a cue marks them as names: an honorific, or a
    # "Name:" / "Patient name:" label (the label is kept). Case-sensitive
    # honorifics keep abbreviations such as "MS Contin" and "dr." untouched.
    text = _HONORIFIC_NAME.sub(_redact_name_run, text)
    return _LABELLED_NAME.sub(_redact_name_run, text)


_VITAL_NAME_HINTS: tuple[str, ...] = (
    "spo2",
    "oxygen saturation",
    "o2 sat",
    "respiratory rate",
    "respiration rate",
    "systolic",
    "heart rate",
    "pulse",
    "temperature",
    "body temperature",
)


def _extract_vital_signs(observations: list[dict[str, Any]]) -> list[VitalSign]:
    """Extract adult vital-sign Observations as VitalSign records.

    Conservative best-effort parsing: only Observations whose display/text
    looks like SpO2, RR, systolic BP, heart rate, or temperature are kept.
    Malformed entries are skipped. RESEARCH USE ONLY educational support.
    """
    vitals: list[VitalSign] = []
    for obs in observations:
        try:
            code = obs.get("code", {})
            name = code.get("text") or ((code.get("coding") or [{}])[0].get("display"))
            if not name:
                continue
            lowered = str(name).lower()
            if not any(hint in lowered for hint in _VITAL_NAME_HINTS):
                continue
            # Prefer systolic component for blood pressure panels.
            if "blood pressure" in lowered and "systolic" not in lowered:
                components = obs.get("component") or []
                systolic = None
                for component in components:
                    ccode = component.get("code", {})
                    cname = ccode.get("text") or (
                        (ccode.get("coding") or [{}])[0].get("display") or ""
                    )
                    if "systolic" in str(cname).lower():
                        quantity = component.get("valueQuantity") or {}
                        if quantity.get("value") is not None:
                            systolic = VitalSign(
                                name="systolic_bp",
                                value=float(quantity["value"]),
                                unit=quantity.get("unit") or "mmHg",
                            )
                            break
                if systolic is not None:
                    vitals.append(systolic)
                continue
            value_quantity = obs.get("valueQuantity") or {}
            value = value_quantity.get("value")
            unit = value_quantity.get("unit")
            if value is None:
                continue
            vitals.append(VitalSign(name=str(name), value=float(value), unit=unit))
        except Exception as exc:
            logger.warning("vital_parse_error", error_type=type(exc).__name__)
    return vitals
