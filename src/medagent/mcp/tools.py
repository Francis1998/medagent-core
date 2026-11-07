"""Deterministic, offline MCP tools built on medagent's existing safety components.

Every tool is read-only and network-free. Results carry ``structuredContent``
that conforms to the tool's ``outputSchema``, a text rendering, and the
mandatory research-use disclaimer. Findings come verbatim from the repository's
deterministic checkers: they are advisory, never modify a medication list, and
are never prescribing directives.
"""

from __future__ import annotations

import inspect
import math
import re
import typing
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, cast

from pydantic import BaseModel

import medagent.safety as safety_pkg
from medagent.extraction.fhir_parser import (
    FHIRParseError,
    parse_fhir_bundle,
    sanitise_clinical_text,
)
from medagent.models import HepaticFunction, LabResult, Medication, Severity
from medagent.safety.acei_arb_duplication_checker import AceiArbDuplicationChecker
from medagent.safety.allergy_checker import AllergyChecker
from medagent.safety.allergy_interclass_checker import AllergyInterClassCrossReactivityChecker
from medagent.safety.anticholinergic_burden_checker import AnticholinergicBurdenChecker
from medagent.safety.anticoag_bleeding_checker import AnticoagBleedingChecker
from medagent.safety.beers_criteria_checker import BeersCriteriaChecker
from medagent.safety.black_box_warning_checker import BlackBoxWarningChecker
from medagent.safety.disclaimer import MANDATORY_DISCLAIMER
from medagent.safety.duplicate_therapy import DuplicateTherapyChecker
from medagent.safety.fhir_medication_request_adapter import FhirMedicationRequestAdapter
from medagent.safety.hepatic_dose_checker import HepaticDoseChecker
from medagent.safety.lactation_checker import LactationSafetyChecker
from medagent.safety.pii_hasher import hash_pii
from medagent.safety.pregnancy_checker import PregnancySafetyChecker
from medagent.safety.qt_prolongation_checker import QTProlongationChecker
from medagent.safety.qtc_ddi_checker import QtcDdiChecker
from medagent.safety.renal_dose_checker import RenalDoseChecker
from medagent.safety.scope_enforcer import ScopeEnforcer, ScopeViolationError
from medagent.safety.serotonin_syndrome_checker import SerotoninSyndromeChecker
from medagent.safety.triple_whammy_checker import TripleWhammyChecker

SEVERITY_ORDER: tuple[str, ...] = tuple(severity.value for severity in Severity)
_SEVERITY_RANK = {name: rank for rank, name in enumerate(SEVERITY_ORDER)}
_ESCALATING_SEVERITIES = frozenset({Severity.CRITICAL.value, Severity.HIGH.value})
CATEGORIES: tuple[str, ...] = ("patient_context", "medication_list", "interaction")
_CATEGORY_RANK = {name: rank for rank, name in enumerate(CATEGORIES)}

COVERAGE_NOTE = (
    "Deterministic, offline rule set: absence of a finding is NOT evidence of safety. "
    "Coverage is limited to the listed checks and name-based matching; every finding is "
    "advisory and must be reviewed by a licensed clinician. Nothing here is a prescription "
    "or treatment order."
)

READ_ONLY_ANNOTATIONS: dict[str, bool] = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}

_SCOPE_ENFORCER = ScopeEnforcer()
_EGFR_NAME = re.compile(r"\begfr\b|glomerular filtration", re.IGNORECASE)


class ToolInputError(ValueError):
    """Tool arguments the model can correct; reported as an ``isError`` tool result."""


@dataclass(frozen=True)
class ToolOutput:
    """Successful tool output: structured content plus a short text summary."""

    structured: dict[str, Any]
    summary: str


@dataclass(frozen=True)
class ScreeningContext:
    """De-identified inputs shared by every deterministic check."""

    medications: list[Medication]
    age: int | None = None
    pregnant: bool | None = None
    breastfeeding: bool | None = None
    egfr: float | None = None
    hepatic_function: HepaticFunction | None = None
    allergies: list[str] | None = None


@dataclass(frozen=True)
class SafetyCheck:
    """One existing deterministic checker exposed through the MCP tools."""

    id: str
    title: str
    category: str
    checker_cls: type
    safety_section: str | None
    run: Callable[[ScreeningContext], Sequence[BaseModel]]
    requires: tuple[str, ...] = ()

    @property
    def checker(self) -> str:
        """Class name of the underlying checker."""
        return self.checker_cls.__name__


@dataclass(frozen=True)
class ToolSpec:
    """An MCP tool definition and the handler that implements it."""

    name: str
    title: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], ToolOutput]

    def definition(self) -> dict[str, Any]:
        """Return the MCP ``Tool`` object advertised by ``tools/list``."""
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "inputSchema": self.input_schema,
            "outputSchema": self.output_schema,
            "annotations": dict(READ_ONLY_ANNOTATIONS),
        }


# ---------------------------------------------------------------------------
# Check registry (existing checkers only)
# ---------------------------------------------------------------------------

_PATIENT_CONTEXT_CHECKS: tuple[SafetyCheck, ...] = (
    SafetyCheck(
        "allergy",
        "Drug-allergy conflicts (direct and intra-class)",
        "patient_context",
        AllergyChecker,
        "3.9",
        lambda ctx: AllergyChecker().check(ctx.medications, ctx.allergies or []),
        ("allergies",),
    ),
    SafetyCheck(
        "allergy_interclass",
        "Allergy inter-class cross-reactivity",
        "patient_context",
        AllergyInterClassCrossReactivityChecker,
        "3.130",
        lambda ctx: AllergyInterClassCrossReactivityChecker().check(
            ctx.medications, ctx.allergies or []
        ),
        ("allergies",),
    ),
    SafetyCheck(
        "pregnancy",
        "Pregnancy safety (teratogens / contraindicated agents)",
        "patient_context",
        PregnancySafetyChecker,
        "3.11",
        lambda ctx: PregnancySafetyChecker().check(ctx.medications, bool(ctx.pregnant)),
        ("pregnant",),
    ),
    SafetyCheck(
        "lactation",
        "Lactation / breastfeeding medication safety",
        "patient_context",
        LactationSafetyChecker,
        "3.28",
        lambda ctx: LactationSafetyChecker().check(ctx.medications, bool(ctx.breastfeeding)),
        ("breastfeeding",),
    ),
    SafetyCheck(
        "beers_criteria",
        "AGS Beers Criteria for adults aged 65+",
        "patient_context",
        BeersCriteriaChecker,
        "3.15",
        lambda ctx: BeersCriteriaChecker().check(ctx.medications, ctx.age),
        ("age",),
    ),
    SafetyCheck(
        "renal_dose",
        "Renal dosing against eGFR",
        "patient_context",
        RenalDoseChecker,
        "3.16",
        lambda ctx: RenalDoseChecker().check(ctx.medications, ctx.egfr),
        ("egfr",),
    ),
    SafetyCheck(
        "hepatic_dose",
        "Hepatic dosing against Child-Pugh class",
        "patient_context",
        HepaticDoseChecker,
        "3.17",
        lambda ctx: HepaticDoseChecker().check(ctx.medications, ctx.hepatic_function),
        ("hepatic_function",),
    ),
)

_MEDICATION_LIST_CHECKS: tuple[SafetyCheck, ...] = (
    SafetyCheck(
        "duplicate_therapy",
        "Duplicate therapy within a therapeutic class",
        "medication_list",
        DuplicateTherapyChecker,
        "3.10",
        lambda ctx: DuplicateTherapyChecker().check(ctx.medications),
    ),
    SafetyCheck(
        "qt_prolongation",
        "Additive QT-prolongation burden",
        "medication_list",
        QTProlongationChecker,
        "3.12",
        lambda ctx: QTProlongationChecker().check(ctx.medications),
    ),
    SafetyCheck(
        "anticholinergic_burden",
        "Cumulative anticholinergic (ACB) burden",
        "medication_list",
        AnticholinergicBurdenChecker,
        "3.13",
        lambda ctx: AnticholinergicBurdenChecker().check(ctx.medications),
    ),
    SafetyCheck(
        "serotonin_syndrome",
        "Serotonergic combinations",
        "medication_list",
        SerotoninSyndromeChecker,
        "3.14",
        lambda ctx: SerotoninSyndromeChecker().check(ctx.medications),
    ),
    SafetyCheck(
        "black_box_warning",
        "FDA boxed (black-box) warnings",
        "medication_list",
        BlackBoxWarningChecker,
        "3.23",
        lambda ctx: BlackBoxWarningChecker().check(ctx.medications),
    ),
    SafetyCheck(
        "acei_arb_duplication",
        "ACEI + ARB + ARNI dual RAAS blockade",
        "medication_list",
        AceiArbDuplicationChecker,
        "3.50",
        lambda ctx: AceiArbDuplicationChecker().check(ctx.medications),
    ),
)

_EXPLICIT_INTERACTION_CHECKS: tuple[SafetyCheck, ...] = (
    SafetyCheck(
        "qtc_ddi",
        "QTc drug-drug interaction pairs",
        "interaction",
        QtcDdiChecker,
        "3.27",
        lambda ctx: QtcDdiChecker().check(ctx.medications),
    ),
    SafetyCheck(
        "anticoag_bleeding",
        "Anticoagulant + bleeding-augmenter combinations",
        "interaction",
        AnticoagBleedingChecker,
        "3.33",
        lambda ctx: AnticoagBleedingChecker().check(ctx.medications),
    ),
    SafetyCheck(
        "triple_whammy",
        "NSAID + ACEI/ARB/ARNI + diuretic (triple whammy)",
        "interaction",
        TripleWhammyChecker,
        "3.46",
        lambda ctx: TripleWhammyChecker().check(ctx.medications),
    ),
)

_PAIRWISE_RECORD_FIELDS = frozenset(
    {"partner_agent", "partner_medication", "severity", "rationale"}
)


def _doc_title(cls: type) -> str:
    """Return the first docstring line of ``cls`` without a trailing period."""
    doc = inspect.getdoc(cls) or cls.__name__
    return doc.splitlines()[0].rstrip(".")


def _is_pairwise_interaction_checker(cls: type) -> bool:
    """True for checkers shaped ``check(medications) -> list[<pairwise risk>]``."""
    check = getattr(cls, "check", None)
    if not callable(check):
        return False
    try:
        parameters = [name for name in inspect.signature(check).parameters if name != "self"]
        hints = typing.get_type_hints(check)
    except (NameError, TypeError, ValueError):
        return False
    record_types = typing.get_args(hints.get("return"))
    if parameters != ["medications"] or len(record_types) != 1:
        return False
    fields = getattr(record_types[0], "model_fields", {})
    return _PAIRWISE_RECORD_FIELDS <= set(fields)


def _medication_only_runner(cls: type) -> Callable[[ScreeningContext], Sequence[BaseModel]]:
    """Wrap a ``check(medications)`` checker class as a check runner."""

    def run(ctx: ScreeningContext) -> Sequence[BaseModel]:
        return cast(Sequence[BaseModel], cls().check(ctx.medications))

    return run


@lru_cache(maxsize=1)
def interaction_checks() -> tuple[SafetyCheck, ...]:
    """Return every offline drug-interaction check, sorted by id.

    Pairwise interaction checkers exported by :mod:`medagent.safety` (any
    ``check(medications)`` returning records with ``partner_agent`` and
    ``partner_medication``) are discovered automatically, so new rules added to
    the safety package are screened without touching the MCP layer.
    """
    checks: dict[type, SafetyCheck] = {
        check.checker_cls: check for check in _EXPLICIT_INTERACTION_CHECKS
    }
    for name in sorted(safety_pkg.__all__):
        cls = getattr(safety_pkg, name, None)
        if not inspect.isclass(cls) or cls in checks:
            continue
        if not _is_pairwise_interaction_checker(cls):
            continue
        module_name = cls.__module__.rsplit(".", 1)[-1]
        checks[cls] = SafetyCheck(
            module_name.removesuffix("_checker"),
            _doc_title(cls),
            "interaction",
            cls,
            None,
            _medication_only_runner(cls),
        )
    return tuple(sorted(checks.values(), key=lambda check: check.id))


def screening_checks() -> tuple[SafetyCheck, ...]:
    """Return the patient-context and medication-list checks run by the screen."""
    return _PATIENT_CONTEXT_CHECKS + _MEDICATION_LIST_CHECKS


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _parse_medications(items: list[Any]) -> list[Medication]:
    """Convert validated medication arguments into ``Medication`` models."""
    medications: list[Medication] = []
    for item in items:
        if isinstance(item, str):
            medications.append(Medication(name=item.strip()))
        else:
            fields = {key: value.strip() for key, value in item.items()}
            medications.append(Medication(**fields))
    return medications


def _medication_dict(medication: Medication) -> dict[str, str]:
    """Return a medication as a compact dict without empty fields."""
    data = medication.model_dump(exclude_none=True)
    return {key: str(value) for key, value in data.items()}


def _enforce_scope(texts: Sequence[str]) -> None:
    """Apply the agent's ScopeEnforcer (SAFETY.md §3.6) to free-text arguments."""
    joined = "\n".join(text for text in texts if text)
    if not joined:
        return
    try:
        _SCOPE_ENFORCER.check_query_in_scope(joined)
    except ScopeViolationError as exc:
        raise ToolInputError(
            f"Input rejected by scope enforcement (SAFETY.md §3.6): {exc}"
        ) from exc


_MEDICATION_LIST_FIELDS = frozenset({"medications", "medication_names"})
_MEDICATION_FIELDS = frozenset({"medication", "medication_a", "medication_b"})


def _involved_medications(details: dict[str, Any]) -> list[str]:
    """Collect the medication names a checker record refers to, in field order."""
    names: list[str] = []
    for key, value in details.items():
        if key in _MEDICATION_LIST_FIELDS and isinstance(value, list):
            names.extend(str(item) for item in value)
        elif isinstance(value, str) and (key in _MEDICATION_FIELDS or key.endswith("_medication")):
            names.append(value)
    return list(dict.fromkeys(names))


def _normalise_finding(check: SafetyCheck, record: BaseModel) -> dict[str, Any]:
    """Convert a checker record into the stable MCP finding shape."""
    details = record.model_dump(mode="json")
    severity = str(details.pop("severity"))
    rationale = str(details.pop("rationale"))
    return {
        "check_id": check.id,
        "checker": check.checker,
        "category": check.category,
        "safety_section": check.safety_section,
        "severity": severity,
        "medications": _involved_medications(details),
        "rationale": rationale,
        "details": details,
    }


def _run_checks(checks: Sequence[SafetyCheck], ctx: ScreeningContext) -> list[dict[str, Any]]:
    """Run checks and return findings sorted by severity, category and check id."""
    findings = [_normalise_finding(check, record) for check in checks for record in check.run(ctx)]
    findings.sort(
        key=lambda finding: (
            _SEVERITY_RANK.get(finding["severity"], len(SEVERITY_ORDER)),
            _CATEGORY_RANK[finding["category"]],
            finding["check_id"],
            finding["medications"],
        )
    )
    return findings


def _severity_summary(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Return counts, the highest severity and the escalation recommendation."""
    counts = Counter(finding["severity"] for finding in findings)
    highest = findings[0]["severity"] if findings else None
    return {
        "finding_count": len(findings),
        "severity_counts": {name: counts.get(name, 0) for name in SEVERITY_ORDER},
        "highest_severity": highest,
        "escalation_recommended": any(f["severity"] in _ESCALATING_SEVERITIES for f in findings),
    }


def _shorten(text: str, limit: int = 240) -> str:
    """Collapse whitespace and truncate ``text`` for the human summary."""
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def _findings_summary(tool: str, medications: list[Medication], result: dict[str, Any]) -> str:
    """Render the human-readable text block for a screening result."""
    findings: list[dict[str, Any]] = result["findings"]
    if findings:
        escalation = " (escalation recommended)" if result["escalation_recommended"] else ""
        header = (
            f"medagent {tool}: {len(findings)} finding(s) for {len(medications)} medication(s); "
            f"highest severity {result['highest_severity']}{escalation}."
        )
    else:
        header = f"medagent {tool}: no findings for {len(medications)} medication(s)."
    lines = [header]
    for finding in findings:
        involved = ", ".join(finding["medications"]) or "medication list"
        lines.append(
            f"[{finding['severity']}] {finding['check_id']} ({involved}): "
            f"{_shorten(finding['rationale'])}"
        )
    skipped: list[dict[str, Any]] = result.get("checks_skipped", [])
    if skipped:
        not_run = ", ".join(f"{s['check_id']} (needs {', '.join(s['missing'])})" for s in skipped)
        lines.append(f"Not run, missing patient context: {not_run}.")
    lines.extend([COVERAGE_NOTE, MANDATORY_DISCLAIMER])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------


def _screen_medications(arguments: dict[str, Any]) -> ToolOutput:
    """Screen a medication list with the patient-context, list and interaction checks."""
    medications = _parse_medications(arguments["medications"])
    patient: dict[str, Any] = arguments.get("patient", {})
    allergies = [allergy.strip() for allergy in patient.get("allergies", [])]
    _enforce_scope(
        [text for med in medications for text in (med.name, med.dosage or "")] + allergies
    )
    hepatic = patient.get("hepatic_function")
    egfr = patient.get("egfr")
    ctx = ScreeningContext(
        medications=medications,
        age=patient.get("age"),
        pregnant=patient.get("pregnant"),
        breastfeeding=patient.get("breastfeeding"),
        egfr=float(egfr) if egfr is not None else None,
        hepatic_function=HepaticFunction(hepatic.upper()) if hepatic else None,
        allergies=allergies if "allergies" in patient else None,
    )

    runnable: list[SafetyCheck] = []
    skipped: list[dict[str, Any]] = []
    for check in screening_checks():
        missing = [field for field in check.requires if getattr(ctx, field) is None]
        if missing:
            skipped.append({"check_id": check.id, "missing": missing})
        else:
            runnable.append(check)
    interactions = interaction_checks() if arguments.get("include_interactions", True) else ()
    findings = _run_checks([*runnable, *interactions], ctx)

    patient_ref = arguments.get("patient_ref")
    result: dict[str, Any] = {
        "medications_screened": [medication.name for medication in medications],
        "patient_context_used": {key: patient[key] for key in sorted(patient)},
        "patient_ref_hash": hash_pii(patient_ref) if patient_ref else None,
        "checks_run": [check.id for check in runnable],
        "checks_skipped": skipped,
        "interaction_rules_evaluated": len(interactions),
        "findings": findings,
        **_severity_summary(findings),
        "network_used": False,
        "coverage_note": COVERAGE_NOTE,
        "disclaimer": MANDATORY_DISCLAIMER,
    }
    return ToolOutput(result, _findings_summary("screen_medications", medications, result))


def _check_drug_interactions(arguments: dict[str, Any]) -> ToolOutput:
    """Evaluate the offline drug-drug interaction rules for a medication list."""
    medications = _parse_medications(arguments["medications"])
    _enforce_scope([text for med in medications for text in (med.name, med.dosage or "")])
    checks = interaction_checks()
    findings = _run_checks(checks, ScreeningContext(medications=medications))
    result: dict[str, Any] = {
        "medications_checked": [medication.name for medication in medications],
        "rules_evaluated": len(checks),
        "findings": findings,
        **_severity_summary(findings),
        "network_used": False,
        "coverage_note": COVERAGE_NOTE,
        "disclaimer": MANDATORY_DISCLAIMER,
    }
    return ToolOutput(result, _findings_summary("check_drug_interactions", medications, result))


def _lowest_egfr(labs: list[LabResult]) -> tuple[float | None, int]:
    """Return the lowest numeric eGFR lab value and how many were found."""
    values: list[float] = []
    for lab in labs:
        if not _EGFR_NAME.search(lab.test_name):
            continue
        try:
            value = float(lab.value)
        except ValueError:
            continue
        if math.isfinite(value):
            values.append(value)
    return (min(values) if values else None), len(values)


def _parse_fhir_bundle(arguments: dict[str, Any]) -> ToolOutput:
    """Normalise a FHIR R4 Bundle into de-identified, screening-ready context."""
    bundle: dict[str, Any] = arguments["bundle"]
    try:
        context = parse_fhir_bundle(bundle)
    except FHIRParseError as exc:
        raise ToolInputError(f"Invalid FHIR bundle: {exc}") from exc
    except (AttributeError, TypeError, ValueError) as exc:
        raise ToolInputError(
            "FHIR bundle could not be parsed: a resource has an unexpected structure "
            f"({type(exc).__name__})."
        ) from exc

    resources = [entry.get("resource", {}) for entry in bundle.get("entry", [])]
    medication_resources = [
        resource
        for resource in resources
        if resource.get("resourceType") in {"MedicationRequest", "MedicationStatement"}
    ]
    adapted = FhirMedicationRequestAdapter().adapt(medication_resources)
    medications = [_medication_dict(medication) for medication in adapted.medications]
    egfr, egfr_count = _lowest_egfr(context.lab_results)

    screening_patient: dict[str, Any] = {}
    if context.age is not None:
        screening_patient["age"] = context.age
    if context.allergies:
        screening_patient["allergies"] = list(context.allergies)
    if egfr is not None:
        screening_patient["egfr"] = egfr

    notes = [
        "Direct identifiers (name, birthDate, identifier, telecom, address) and the raw bundle "
        "are not returned; the patient id is HMAC-SHA256 hashed with PII_HASH_SALT.",
        "Medications exclude stopped, cancelled and entered-in-error requests.",
        "pregnant, breastfeeding and hepatic_function are not derived from the bundle; "
        "add them to screening_input.patient when known.",
    ]
    if egfr is not None:
        notes.append(f"egfr is the lowest of {egfr_count} numeric eGFR observation(s).")

    result: dict[str, Any] = {
        "patient_id_hash": context.patient_id_hash,
        "age": context.age,
        "sex": context.sex,
        "chief_complaint": sanitise_clinical_text(context.chief_complaint),
        "diagnoses": [sanitise_clinical_text(text) for text in context.diagnoses_history],
        "medications": medications,
        "medication_notes": list(adapted.notes),
        "allergies": list(context.allergies),
        "lab_results": [lab.model_dump(mode="json") for lab in context.lab_results],
        "vital_signs": [vital.model_dump(mode="json") for vital in context.vital_signs],
        "resource_counts": dict(
            sorted(Counter(str(r.get("resourceType", "Unknown")) for r in resources).items())
        ),
        "screening_input": {"medications": medications, "patient": screening_patient},
        "notes": notes,
        "disclaimer": MANDATORY_DISCLAIMER,
    }
    summary = "\n".join(
        [
            f"medagent parse_fhir_bundle: patient {context.patient_id_hash[:12]}… (hashed), "
            f"age {context.age if context.age is not None else 'unknown'}, "
            f"{len(medications)} medication(s), {len(context.allergies)} allergy record(s), "
            f"{len(context.lab_results)} lab result(s).",
            "Pass screening_input to screen_medications to screen this medication list.",
            MANDATORY_DISCLAIMER,
        ]
    )
    return ToolOutput(result, summary)


_PLATFORM_CONTROLS: tuple[dict[str, Any], ...] = (
    {
        "id": "mandatory_disclaimer",
        "title": "Mandatory research-use disclaimer",
        "safety_section": "3.1",
        "description": "Every agent output and every MCP tool result carries the "
        "RESEARCH USE ONLY disclaimer.",
    },
    {
        "id": "system_prompt_constraints",
        "title": "Immutable system prompt constraints",
        "safety_section": "3.2",
        "description": "LLM calls forbid prescriptions, dosage recommendations, browsing "
        "and code execution.",
    },
    {
        "id": "medical_output_validation",
        "title": "Prohibited prescription-language validation",
        "safety_section": "3.3",
        "description": "Outputs matching prescription patterns are rejected; MCP tool "
        "results are screened with the same patterns and withheld on a match.",
    },
    {
        "id": "escalate_state",
        "title": "ESCALATE on low confidence or contradictory evidence",
        "safety_section": "3.4",
        "description": "Low-confidence or contradictory agent runs end in ESCALATE; MCP "
        "screens set escalation_recommended for HIGH or CRITICAL findings.",
    },
    {
        "id": "pii_deidentification",
        "title": "PII de-identification",
        "safety_section": "3.5",
        "description": "Patient identifiers are HMAC-SHA256 hashed; MCP logs and audit "
        "records contain hashes only, and free text is redacted.",
    },
    {
        "id": "scope_enforcement",
        "title": "Scope enforcement",
        "safety_section": "3.6",
        "description": "Requests for browsing, code execution or non-clinical topics are "
        "rejected, including free-text MCP tool arguments.",
    },
    {
        "id": "drug_interaction_dual_source",
        "title": "Drug-interaction dual-source validation (HTTP API)",
        "safety_section": "3.7",
        "description": "Network-sourced interaction warnings need two independent sources; "
        "the MCP interaction tool uses offline rules only.",
    },
    {
        "id": "hard_timeouts",
        "title": "Hard timeouts",
        "safety_section": "3.8",
        "description": "Agent stages and the whole run are bounded by configured timeouts.",
    },
)


@lru_cache(maxsize=1)
def safety_control_catalog() -> tuple[dict[str, Any], ...]:
    """Return the hard constraints and every check exposed through MCP."""
    catalog = [
        {
            **control,
            "category": "platform",
            "kind": "hard_constraint",
            "checker": None,
            "requires": [],
        }
        for control in _PLATFORM_CONTROLS
    ]
    for check in (*screening_checks(), *interaction_checks()):
        catalog.append(
            {
                "id": check.id,
                "title": check.title,
                "safety_section": check.safety_section,
                "description": _doc_title(check.checker_cls),
                "category": check.category,
                "kind": "deterministic_checker",
                "checker": check.checker,
                "requires": list(check.requires),
            }
        )
    return tuple(catalog)


def _list_safety_controls(arguments: dict[str, Any]) -> ToolOutput:
    """List the hard safety controls and checks, optionally filtered."""
    category = arguments.get("category")
    query = arguments.get("query", "").strip().lower()
    if query:
        _enforce_scope([query])
    controls = [
        control
        for control in safety_control_catalog()
        if (category is None or control["category"] == category)
        and (
            not query
            or any(
                query in str(control[key]).lower()
                for key in ("id", "title", "description", "checker")
            )
        )
    ]
    by_category = Counter(control["category"] for control in controls)
    counts = {name: by_category.get(name, 0) for name in ("platform", *CATEGORIES)}
    result: dict[str, Any] = {
        "count": len(controls),
        "counts_by_category": counts,
        "controls": controls,
        "disclaimer": MANDATORY_DISCLAIMER,
    }
    breakdown = ", ".join(f"{name} {count}" for name, count in counts.items())
    summary = "\n".join(
        [
            f"medagent list_safety_controls: {len(controls)} control(s) ({breakdown}).",
            MANDATORY_DISCLAIMER,
        ]
    )
    return ToolOutput(result, summary)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

_NON_BLANK = r"\S"

_MEDICATION_ITEM: dict[str, Any] = {
    "anyOf": [
        {
            "type": "string",
            "minLength": 1,
            "maxLength": 200,
            "pattern": _NON_BLANK,
            "description": "Medication name, optionally with strength, e.g. 'warfarin 5 mg'.",
        },
        {
            "type": "object",
            "properties": {
                "name": {"type": "string", "minLength": 1, "maxLength": 200, "pattern": _NON_BLANK},
                "dosage": {"type": "string", "maxLength": 200},
                "route": {"type": "string", "maxLength": 100},
                "frequency": {"type": "string", "maxLength": 100},
                "rxnorm_code": {"type": "string", "maxLength": 32},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    ]
}

_PATIENT_CONTEXT: dict[str, Any] = {
    "type": "object",
    "description": (
        "Optional de-identified patient context. Checks whose inputs are missing are "
        "reported in checks_skipped. Direct identifiers are not accepted."
    ),
    "properties": {
        "age": {"type": "integer", "minimum": 0, "maximum": 150},
        "pregnant": {"type": "boolean"},
        "breastfeeding": {"type": "boolean"},
        "egfr": {
            "type": "number",
            "minimum": 0,
            "maximum": 250,
            "description": "Estimated GFR in mL/min/1.73m².",
        },
        "hepatic_function": {
            "type": "string",
            "enum": ["normal", "mild", "moderate", "severe"],
            "description": "Child-Pugh class: mild = A, moderate = B, severe = C.",
        },
        "allergies": {
            "type": "array",
            "maxItems": 50,
            "items": {"type": "string", "minLength": 1, "maxLength": 200, "pattern": _NON_BLANK},
        },
    },
    "additionalProperties": False,
}

_SEVERITY_SCHEMA: dict[str, Any] = {"type": "string", "enum": list(SEVERITY_ORDER)}
_NULLABLE_STRING: dict[str, Any] = {"anyOf": [{"type": "string"}, {"type": "null"}]}

_FINDING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "check_id": {"type": "string"},
        "checker": {"type": "string"},
        "category": {"type": "string", "enum": list(CATEGORIES)},
        "safety_section": _NULLABLE_STRING,
        "severity": _SEVERITY_SCHEMA,
        "medications": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string"},
        "details": {"type": "object"},
    },
    "required": [
        "check_id",
        "checker",
        "category",
        "safety_section",
        "severity",
        "medications",
        "rationale",
        "details",
    ],
    "additionalProperties": False,
}

_SUMMARY_PROPERTIES: dict[str, Any] = {
    "findings": {"type": "array", "items": _FINDING_SCHEMA},
    "finding_count": {"type": "integer", "minimum": 0},
    "severity_counts": {
        "type": "object",
        "properties": {name: {"type": "integer", "minimum": 0} for name in SEVERITY_ORDER},
        "required": list(SEVERITY_ORDER),
        "additionalProperties": False,
    },
    "highest_severity": {"anyOf": [_SEVERITY_SCHEMA, {"type": "null"}]},
    "escalation_recommended": {"type": "boolean"},
    "network_used": {"type": "boolean", "const": False},
    "coverage_note": {"type": "string"},
    "disclaimer": {"type": "string", "const": MANDATORY_DISCLAIMER},
}
_SUMMARY_REQUIRED = list(_SUMMARY_PROPERTIES)

_STRING_LIST: dict[str, Any] = {"type": "array", "items": {"type": "string"}}

_SCREEN_OUTPUT: dict[str, Any] = {
    "type": "object",
    "properties": {
        "medications_screened": _STRING_LIST,
        "patient_context_used": {"type": "object"},
        "patient_ref_hash": _NULLABLE_STRING,
        "checks_run": _STRING_LIST,
        "checks_skipped": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"check_id": {"type": "string"}, "missing": _STRING_LIST},
                "required": ["check_id", "missing"],
                "additionalProperties": False,
            },
        },
        "interaction_rules_evaluated": {"type": "integer", "minimum": 0},
        **_SUMMARY_PROPERTIES,
    },
    "required": [
        "medications_screened",
        "patient_context_used",
        "patient_ref_hash",
        "checks_run",
        "checks_skipped",
        "interaction_rules_evaluated",
        *_SUMMARY_REQUIRED,
    ],
    "additionalProperties": False,
}

_INTERACTIONS_OUTPUT: dict[str, Any] = {
    "type": "object",
    "properties": {
        "medications_checked": _STRING_LIST,
        "rules_evaluated": {"type": "integer", "minimum": 0},
        **_SUMMARY_PROPERTIES,
    },
    "required": ["medications_checked", "rules_evaluated", *_SUMMARY_REQUIRED],
    "additionalProperties": False,
}

_MEDICATION_OUT: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "dosage": {"type": "string"},
        "route": {"type": "string"},
        "frequency": {"type": "string"},
        "rxnorm_code": {"type": "string"},
    },
    "required": ["name"],
    "additionalProperties": False,
}

_FHIR_OUTPUT: dict[str, Any] = {
    "type": "object",
    "properties": {
        "patient_id_hash": {"type": "string", "minLength": 64, "maxLength": 64},
        "age": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
        "sex": _NULLABLE_STRING,
        "chief_complaint": {"type": "string"},
        "diagnoses": _STRING_LIST,
        "medications": {"type": "array", "items": _MEDICATION_OUT},
        "medication_notes": _STRING_LIST,
        "allergies": _STRING_LIST,
        "lab_results": {"type": "array", "items": {"type": "object"}},
        "vital_signs": {"type": "array", "items": {"type": "object"}},
        "resource_counts": {"type": "object", "additionalProperties": {"type": "integer"}},
        "screening_input": {
            "type": "object",
            "properties": {
                "medications": {"type": "array", "items": _MEDICATION_OUT},
                "patient": {"type": "object"},
            },
            "required": ["medications", "patient"],
            "additionalProperties": False,
        },
        "notes": _STRING_LIST,
        "disclaimer": {"type": "string", "const": MANDATORY_DISCLAIMER},
    },
    "required": [
        "patient_id_hash",
        "age",
        "sex",
        "chief_complaint",
        "diagnoses",
        "medications",
        "medication_notes",
        "allergies",
        "lab_results",
        "vital_signs",
        "resource_counts",
        "screening_input",
        "notes",
        "disclaimer",
    ],
    "additionalProperties": False,
}

_CONTROL_CATEGORIES = ["platform", *CATEGORIES]

_CONTROLS_OUTPUT: dict[str, Any] = {
    "type": "object",
    "properties": {
        "count": {"type": "integer", "minimum": 0},
        "counts_by_category": {
            "type": "object",
            "properties": {name: {"type": "integer"} for name in _CONTROL_CATEGORIES},
            "required": _CONTROL_CATEGORIES,
            "additionalProperties": False,
        },
        "controls": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "category": {"type": "string", "enum": _CONTROL_CATEGORIES},
                    "kind": {
                        "type": "string",
                        "enum": ["hard_constraint", "deterministic_checker"],
                    },
                    "checker": _NULLABLE_STRING,
                    "safety_section": _NULLABLE_STRING,
                    "requires": _STRING_LIST,
                    "description": {"type": "string"},
                },
                "required": [
                    "id",
                    "title",
                    "category",
                    "kind",
                    "checker",
                    "safety_section",
                    "requires",
                    "description",
                ],
                "additionalProperties": False,
            },
        },
        "disclaimer": {"type": "string", "const": MANDATORY_DISCLAIMER},
    },
    "required": ["count", "counts_by_category", "controls", "disclaimer"],
    "additionalProperties": False,
}

TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="check_drug_interactions",
        title="Offline drug-drug interaction check",
        description=(
            "Evaluate medagent's deterministic, offline drug-drug interaction rules (pairwise "
            "checkers plus QTc, anticoagulant-bleeding and triple-whammy combinations) for a "
            "medication list. No network calls. Findings are advisory for clinician review, "
            "never prescriptions. RESEARCH USE ONLY."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "medications": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 50,
                    "items": _MEDICATION_ITEM,
                    "description": "Active medications (names or objects).",
                }
            },
            "required": ["medications"],
            "additionalProperties": False,
        },
        output_schema=_INTERACTIONS_OUTPUT,
        handler=_check_drug_interactions,
    ),
    ToolSpec(
        name="list_safety_controls",
        title="List medagent safety controls",
        description=(
            "List medagent's hard safety constraints and every deterministic check the MCP "
            "tools run, with SAFETY.md sections and required inputs. Filter by category or a "
            "case-insensitive text query. RESEARCH USE ONLY."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": _CONTROL_CATEGORIES},
                "query": {"type": "string", "minLength": 1, "maxLength": 100},
            },
            "additionalProperties": False,
        },
        output_schema=_CONTROLS_OUTPUT,
        handler=_list_safety_controls,
    ),
    ToolSpec(
        name="parse_fhir_bundle",
        title="Normalise a FHIR R4 Bundle",
        description=(
            "Parse a FHIR R4 Bundle (Patient, Condition, MedicationRequest, Observation, "
            "AllergyIntolerance) into de-identified patient context: hashed patient id, age, "
            "active medications, allergies, labs and a screening_input object ready for "
            "screen_medications. Identifiers and the raw bundle are never returned. "
            "RESEARCH USE ONLY."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "bundle": {
                    "type": "object",
                    "description": "FHIR R4 Bundle resource.",
                    "properties": {
                        "resourceType": {"type": "string", "const": "Bundle"},
                        "entry": {
                            "type": "array",
                            "maxItems": 5000,
                            "items": {
                                "type": "object",
                                "properties": {"resource": {"type": "object"}},
                            },
                        },
                    },
                    "required": ["resourceType"],
                }
            },
            "required": ["bundle"],
            "additionalProperties": False,
        },
        output_schema=_FHIR_OUTPUT,
        handler=_parse_fhir_bundle,
    ),
    ToolSpec(
        name="screen_medications",
        title="Medication safety screen",
        description=(
            "Screen a medication list against medagent's deterministic safety checkers: "
            "allergies, pregnancy, lactation, Beers (65+), renal (eGFR) and hepatic "
            "(Child-Pugh) dosing, duplicate therapy, QT, anticholinergic and serotonergic "
            "burden, boxed warnings, plus the offline drug-interaction rules. Offline and "
            "deterministic; findings are advisory for clinician review, never prescriptions. "
            "RESEARCH USE ONLY."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "medications": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 50,
                    "items": _MEDICATION_ITEM,
                    "description": "Active medications (names or objects).",
                },
                "patient": _PATIENT_CONTEXT,
                "patient_ref": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 200,
                    "description": (
                        "Optional caller reference used only to link audit records. It is "
                        "HMAC-SHA256 hashed with PII_HASH_SALT before logging and is never "
                        "echoed back."
                    ),
                },
                "include_interactions": {
                    "type": "boolean",
                    "default": True,
                    "description": "Also run the offline drug-interaction rules.",
                },
            },
            "required": ["medications"],
            "additionalProperties": False,
        },
        output_schema=_SCREEN_OUTPUT,
        handler=_screen_medications,
    ),
)

TOOLS_BY_NAME: dict[str, ToolSpec] = {tool.name: tool for tool in TOOLS}
