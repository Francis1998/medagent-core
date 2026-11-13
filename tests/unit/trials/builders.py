"""Builders for synthetic FHIR bundles and trial definitions used by the trial tests.

Every identifier carries a CANARY marker so tests can prove none is ever exported.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from medagent.trials.screening import TrialScreening, screen_trials

ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = ROOT / "examples" / "trials"
AS_OF = date(2026, 11, 12)

LOINC = "http://loinc.org"
SNOMED = "http://snomed.info/sct"
ICD10CM = "http://hl7.org/fhir/sid/icd-10-cm"
UCUM = "http://unitsofmeasure.org"
EGFR = {"system": LOINC, "code": "98979-8"}

PATIENT: dict[str, Any] = {
    "resourceType": "Patient",
    "id": "pt-canary-0001",
    "identifier": [{"system": "urn:mrn", "value": "MRN-CANARY-4242"}],
    "name": [{"family": "Canaryson", "given": ["Quillon"]}],
    "telecom": [{"system": "phone", "value": "415-555-0199"}],
    "address": [{"line": ["9 Canary Lane"], "city": "Canarytown", "postalCode": "94999"}],
    "gender": "female",
    "birthDate": "1961-05-14",
}
IDENTIFIERS = (
    "pt-canary-0001",
    "MRN-CANARY-4242",
    "Canaryson",
    "Quillon",
    "415-555-0199",
    "Canary Lane",
    "Canarytown",
    "94999",
    "1961-05-14",
)


def example(name: str) -> Any:
    """Load a file from examples/trials/."""
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def bundle(*resources: dict[str, Any], patient: dict[str, Any] | None = PATIENT) -> dict[str, Any]:
    """A collection Bundle: the patient (if any) followed by ``resources``."""
    entries = [{"resource": patient}] if patient is not None else []
    for index, resource in enumerate(resources):
        entries.append({"resource": {"id": f"res-canary-{index}", **resource}})
    return {"resourceType": "Bundle", "type": "collection", "entry": entries}


def condition(
    code: tuple[str, str] = (SNOMED, "44054006"),
    text: str = "Type 2 diabetes mellitus",
    *,
    status: str | None = "active",
    verification: str | None = None,
    onset: str | None = None,
) -> dict[str, Any]:
    resource: dict[str, Any] = {
        "resourceType": "Condition",
        "code": {"coding": [{"system": code[0], "code": code[1]}], "text": text},
        "subject": {"reference": "Patient/pt-canary-0001"},
    }
    if status is not None:
        resource["clinicalStatus"] = {"coding": [{"code": status}]}
    if verification is not None:
        resource["verificationStatus"] = {"coding": [{"code": verification}]}
    if onset is not None:
        resource["onsetDateTime"] = onset
    return resource


def observation(
    value: Any = 52,
    unit: str | None = "mL/min/1.73m2",
    *,
    code: dict[str, str] = EGFR,
    text: str = "eGFR",
    effective: str | None = "2026-10-30",
    comparator: str | None = None,
    high: float | None = None,
    high_unit: str | None = None,
    ucum: str | None = None,
    status: str = "final",
) -> dict[str, Any]:
    quantity: dict[str, Any] = {"value": value}
    if unit is not None:
        quantity["unit"] = unit
    if ucum is not None:
        quantity.update(system=UCUM, code=ucum)
    if comparator is not None:
        quantity["comparator"] = comparator
    resource: dict[str, Any] = {
        "resourceType": "Observation",
        "status": status,
        "code": {"coding": [code], "text": text},
        "subject": {"reference": "Patient/pt-canary-0001"},
        "valueQuantity": quantity,
    }
    if effective is not None:
        resource["effectiveDateTime"] = effective
    if high is not None:
        bound: dict[str, Any] = {"value": high}
        if high_unit is not None:
            bound["unit"] = high_unit
        resource["referenceRange"] = [{"high": bound}]
    return resource


def coded_status(question: str, answer: tuple[str, str], effective: str | None) -> dict[str, Any]:
    """A pregnancy (82810-3) or breastfeeding (63895-7) status Observation."""
    resource: dict[str, Any] = {
        "resourceType": "Observation",
        "status": "final",
        "code": {"coding": [{"system": LOINC, "code": question}], "text": "status"},
        "subject": {"reference": "Patient/pt-canary-0001"},
        "valueCodeableConcept": {"coding": [{"system": answer[0], "code": answer[1]}]},
    }
    if effective is not None:
        resource["effectiveDateTime"] = effective
    return resource


def medication(
    text: str | None,
    *,
    status: str = "active",
    rxnorm: str | None = None,
    resource_type: str = "MedicationRequest",
) -> dict[str, Any]:
    concept: dict[str, Any] = {}
    if text is not None:
        concept["text"] = text
    if rxnorm is not None:
        concept["coding"] = [
            {"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": rxnorm}
        ]
    return {
        "resourceType": resource_type,
        "status": status,
        "medicationCodeableConcept": concept,
        "subject": {"reference": "Patient/pt-canary-0001"},
    }


def trial(
    *inclusion: dict[str, Any],
    exclusion: tuple[dict[str, Any], ...] = (),
    module: dict[str, Any] | None = None,
    trial_id: str = "TEST-001",
) -> dict[str, Any]:
    definition: dict[str, Any] = {
        "schema_version": "1.0",
        "trial_id": trial_id,
        "version": "1",
        "title": f"Synthetic test trial {trial_id}",
        "inclusion": list(inclusion),
        "exclusion": list(exclusion),
    }
    if module is not None:
        definition["eligibilityModule"] = module
    return definition


def lab(
    criterion_id: str = "lab",
    operator: str = ">=",
    value: float | None = 30,
    unit: str | None = "mL/min/1.73m2",
    *,
    codes: tuple[dict[str, str], ...] = (EGFR,),
    **extra: Any,
) -> dict[str, Any]:
    criterion: dict[str, Any] = {
        "id": criterion_id,
        "type": "lab",
        "text": f"lab criterion {criterion_id}",
        "codes": list(codes),
        "operator": operator,
        **extra,
    }
    if value is not None:
        criterion["value"] = value
    if unit is not None:
        criterion["unit"] = unit
    return criterion


def screen(
    patient_bundle: dict[str, Any], *trials: dict[str, Any], **kwargs: Any
) -> TrialScreening:
    kwargs.setdefault("as_of", AS_OF)
    return screen_trials(patient_bundle, trials, **kwargs)


def result_of(
    screening: TrialScreening, criterion_id: str, trial_id: str = "TEST-001"
) -> dict[str, Any]:
    """The structured result of one criterion."""
    for item in screening.structured()["trials"]:
        if item["trial_id"] == trial_id:
            for criterion in item["criteria"]:
                if criterion["criterion_id"] == criterion_id:
                    return dict(criterion)
    raise AssertionError(f"criterion {criterion_id} not found")


def status_of(screening: TrialScreening, criterion_id: str, trial_id: str = "TEST-001") -> str:
    return str(result_of(screening, criterion_id, trial_id)["status"])


def trial_of(screening: TrialScreening, trial_id: str = "TEST-001") -> dict[str, Any]:
    return next(item for item in screening.structured()["trials"] if item["trial_id"] == trial_id)
