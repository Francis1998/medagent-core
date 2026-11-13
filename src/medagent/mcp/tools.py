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
from decimal import Decimal
from functools import lru_cache
from typing import Any, cast

from pydantic import BaseModel

import medagent.safety as safety_pkg
from medagent.extraction.fhir_parser import (
    FHIRParseError,
    parse_fhir_bundle,
    sanitise_clinical_text,
)
from medagent.llm.validator import redact_prohibited_language
from medagent.logging_config import get_logger
from medagent.mcp.schema import validate
from medagent.models import HepaticFunction, Medication, Severity
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
from medagent.safety.scope_enforcer import ScopeEnforcer
from medagent.safety.serotonin_syndrome_checker import SerotoninSyndromeChecker
from medagent.safety.triple_whammy_checker import TripleWhammyChecker

logger = get_logger(__name__)

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
_EGFR_UNIT_FACTORS = {"ml/min/1.73m2": 1.0, "ml/s/1.73m2": 60.0}
_LOINC_SYSTEM = "http://loinc.org"
# Creatinine-based (and creatinine + cystatin C) eGFR LOINC codes: CKD-EPI 2021,
# CKD-EPI and MDRD variants. The CDS Hooks ``egfr`` prefetch template requests
# exactly these codes.
EGFR_LOINC_CODES: tuple[str, ...] = (
    "98979-8",
    "98980-6",
    "62238-1",
    "77147-7",
    "33914-3",
    "48642-3",
    "48643-1",
    "50044-7",
)
_UCUM_SYSTEM = "http://unitsofmeasure.org"
_MAX_MEDICATIONS = 100

# Medication statuses screened as current therapy, plus proposed orders that are
# screened only on explicit opt-in. Everything else (completed, stopped,
# cancelled, entered-in-error, not-taken, unknown or missing) is excluded.
_CURRENT_STATUSES: dict[str, frozenset[str]] = {
    "MedicationRequest": frozenset({"active", "on-hold"}),
    "MedicationStatement": frozenset({"active", "on-hold"}),
}
_PROPOSED_STATUSES: dict[str, frozenset[str]] = {
    "MedicationRequest": frozenset({"draft"}),
    "MedicationStatement": frozenset({"intended"}),
}
_KNOWN_STATUSES: dict[str, frozenset[str]] = {
    "MedicationRequest": frozenset(
        {"active", "on-hold", "cancelled", "completed", "entered-in-error", "stopped", "draft"}
        | {"unknown"}
    ),
    "MedicationStatement": frozenset(
        {"active", "completed", "entered-in-error", "intended", "stopped", "on-hold"}
        | {"unknown", "not-taken"}
    ),
}
# Resource types reported in resource_counts; anything else is counted as "Other"
# so caller-controlled strings never become output keys.
_KNOWN_RESOURCE_TYPES = frozenset(
    {
        "AllergyIntolerance",
        "CarePlan",
        "CareTeam",
        "Composition",
        "Condition",
        "Coverage",
        "Device",
        "DiagnosticReport",
        "DocumentReference",
        "Encounter",
        "FamilyMemberHistory",
        "Goal",
        "Immunization",
        "Location",
        "Medication",
        "MedicationAdministration",
        "MedicationDispense",
        "MedicationRequest",
        "MedicationStatement",
        "Observation",
        "Organization",
        "Patient",
        "Practitioner",
        "PractitionerRole",
        "Procedure",
        "Provenance",
        "RelatedPerson",
        "ServiceRequest",
        "Specimen",
    }
)
_ABSOLUTE_REFERENCE = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)
# FHIR RESTful URL: <server base>/<ResourceType>/<id>[/_history/<version>].
_RESTFUL_URL = re.compile(
    r"^(?P<base>https?://.+)/[A-Z][A-Za-z]+/[A-Za-z0-9\-.]{1,64}"
    r"(?:/_history/[A-Za-z0-9\-.]{1,64})?$"
)
_INVALIDATED_VERIFICATION = frozenset({"entered-in-error", "refuted"})
_REDACTED_PATIENT = "[REDACTED-PATIENT]"


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


def _clean_text(text: str) -> str:
    """De-identify free text and neutralise prescription phrasing before export."""
    return redact_prohibited_language(sanitise_clinical_text(text)).strip()


def _raw_medication_texts(items: list[Any]) -> list[str]:
    """Return every free-text value supplied in medication arguments."""
    texts: list[str] = []
    for item in items:
        texts.extend([item] if isinstance(item, str) else [str(value) for value in item.values()])
    return texts


def _parse_medications(items: list[Any]) -> list[Medication]:
    """Convert validated medication arguments into de-identified ``Medication`` models."""
    medications: list[Medication] = []
    for item in items:
        fields: dict[str, str] = {"name": item} if isinstance(item, str) else dict(item)
        medications.append(Medication(**{key: _clean_text(value) for key, value in fields.items()}))
    return medications


def _medication_dict(medication: Medication, clean: Callable[[str], str]) -> dict[str, str]:
    """Return a medication as a compact dict of cleaned text without empty fields."""
    data = medication.model_dump(exclude_none=True)
    return {key: clean(str(value)) for key, value in data.items()}


def _enforce_scope(texts: Sequence[str]) -> None:
    """Apply the agent's scope patterns (SAFETY.md §3.6) without logging any text."""
    for text in texts:
        pattern = _SCOPE_ENFORCER.find_violation(text)
        if pattern is not None:
            logger.warning("mcp_scope_violation", pattern=pattern)
            raise ToolInputError(
                "Input rejected by scope enforcement (SAFETY.md §3.6): free text must not "
                "request browsing, code execution or non-clinical tasks."
            )


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
    patient: dict[str, Any] = arguments.get("patient", {})
    raw_allergies: list[str] = patient.get("allergies", [])
    _enforce_scope(_raw_medication_texts(arguments["medications"]) + raw_allergies)
    medications = _parse_medications(arguments["medications"])
    allergies = [_clean_text(allergy) for allergy in raw_allergies]
    context_used = {key: patient[key] for key in sorted(patient)}
    if "allergies" in context_used:
        context_used["allergies"] = allergies
    if "age" in context_used:
        context_used["age"] = int(context_used["age"])
    hepatic = patient.get("hepatic_function")
    egfr = patient.get("egfr")
    ctx = ScreeningContext(
        medications=medications,
        age=context_used.get("age"),
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
        "patient_context_used": context_used,
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
    _enforce_scope(_raw_medication_texts(arguments["medications"]))
    medications = _parse_medications(arguments["medications"])
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


def _egfr_unit_factor(unit: str | None) -> float | None:
    """Return the factor converting ``unit`` to mL/min/1.73m², or None if unsupported."""
    if not unit:
        return None
    key = re.sub(r"[\s{}_^]", "", unit.lower()).replace("²", "2")
    return _EGFR_UNIT_FACTORS.get(key)


def _exact_egfr(value: Any, factor: float) -> float:
    """Convert an eGFR value exactly (decimal arithmetic); NaN when it is not numeric."""
    try:
        return float(Decimal(str(value).strip()) * Decimal(str(factor)))
    except (ArithmeticError, ValueError):
        return math.nan


def _is_egfr_observation(resource: Any) -> bool:
    """True for an Observation that reports an eGFR.

    An eGFR LOINC code identifies it whatever its display text, because
    code-only codings and LOINC's own Display Name ("GFR Creatinine-based
    formula ...") and Short Name ("eGFRcr SerPlBld ...") contain neither "eGFR"
    as a word nor "glomerular filtration". Without such a code, its text or a
    coding display must contain one of them.
    """
    if not isinstance(resource, dict) or resource.get("resourceType") != "Observation":
        return False
    code = resource.get("code")
    if not isinstance(code, dict):
        return False
    codings = code.get("coding")
    codings = [c for c in codings if isinstance(c, dict)] if isinstance(codings, list) else []
    if any(c.get("system") == _LOINC_SYSTEM and c.get("code") in EGFR_LOINC_CODES for c in codings):
        return True
    names = [code.get("text"), *(coding.get("display") for coding in codings)]
    return any(isinstance(name, str) and _EGFR_NAME.search(name) for name in names)


def _lowest_egfr(entries: list[dict[str, Any]]) -> tuple[float | None, int, int]:
    """Return the lowest eGFR in mL/min/1.73m², observations used, observations skipped.

    Each eGFR Observation's ``valueQuantity`` is converted from its unit; one
    without a supported unit or a numeric value is skipped. Values are never
    rounded, so a measurement just above a dosing threshold (e.g. 30.04) cannot
    be pushed onto it.
    """
    values: list[float] = []
    skipped = 0
    for entry in entries:
        resource = entry.get("resource", {})
        if not _is_egfr_observation(resource):
            continue
        quantity = resource.get("valueQuantity")
        quantity = quantity if isinstance(quantity, dict) else {}
        unit = quantity.get("unit")
        factor = _egfr_unit_factor(unit if isinstance(unit, str) else None)
        value = math.nan if factor is None else _exact_egfr(quantity.get("value"), factor)
        if not math.isfinite(value):
            skipped += 1
            continue
        values.append(value)
    return (min(values) if values else None), len(values), skipped


def _prefer_ucum_units(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Let a UCUM-coded eGFR unit drive conversion when the display unit cannot.

    The shared parser keeps only ``valueQuantity.unit``; when that display unit is
    missing, unsupported or disagrees with a supported UCUM ``code``, the coded
    unit is used instead (the input bundle is not modified).
    """
    prepared: list[dict[str, Any]] = []
    for entry in entries:
        resource = entry.get("resource", {})
        quantity = resource.get("valueQuantity")
        if (
            resource.get("resourceType") == "Observation"
            and isinstance(quantity, dict)
            and quantity.get("system") == _UCUM_SYSTEM
            and isinstance(code := quantity.get("code"), str)
        ):
            unit = quantity.get("unit")
            coded = _egfr_unit_factor(code)
            if coded is not None and coded != _egfr_unit_factor(
                unit if isinstance(unit, str) else None
            ):
                entry = {
                    **entry,
                    "resource": {**resource, "valueQuantity": {**quantity, "unit": code}},
                }
        prepared.append(entry)
    return prepared


def _same_identifier(reference: dict[str, Any], own: dict[str, Any]) -> bool:
    """True when a logical reference identifier names one of the Patient's identifiers."""
    if not reference.get("value") or reference.get("value") != own.get("value"):
        return False
    systems = (reference.get("system"), own.get("system"))
    return None in systems or systems[0] == systems[1]


def _belongs_to_patient(subject: dict[str, Any], patient_entry: dict[str, Any]) -> bool:
    """Resolve a subject/patient reference against the bundle's single Patient entry."""
    patient = patient_entry.get("resource", {})
    full_url = patient_entry.get("fullUrl")
    full_url = full_url if isinstance(full_url, str) and full_url else None
    patient_id = patient.get("id") if isinstance(patient.get("id"), str) else None
    reference = subject.get("reference")
    if isinstance(reference, str) and reference:
        if reference == full_url:
            return True
        if _ABSOLUTE_REFERENCE.match(reference):
            return False
        if patient_id is not None and reference == f"Patient/{patient_id}":
            return True
        return full_url is not None and full_url.endswith(f"/{reference}")
    identifier = subject.get("identifier")
    if isinstance(identifier, dict):
        owned = [i for i in patient.get("identifier", []) if isinstance(i, dict)]
        return any(_same_identifier(identifier, own) for own in owned)
    return False


def _subject_key(subject: dict[str, Any]) -> str:
    """Comparable key for a subject reference when no Patient resource is present."""
    reference = subject.get("reference")
    if isinstance(reference, str) and reference:
        return reference
    identifier = subject.get("identifier")
    if isinstance(identifier, dict):
        return f"identifier:{identifier.get('system')}|{identifier.get('value')}"
    return "unresolved"


def _require_single_patient(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Reject bundles whose resources do not provably belong to one patient.

    A relative reference resolves on its entry's own server (FHIR bundle rules), so
    ``Patient/p1`` in entries hosted on two servers names two different patients.

    Returns:
        The Patient resource, or None when the bundle has no Patient.
    """
    patients = [e for e in entries if e.get("resource", {}).get("resourceType") == "Patient"]
    if len(patients) > 1:
        raise ToolInputError(
            f"Bundle contains {len(patients)} Patient resources; send one patient's "
            "resources per call."
        )
    sources = [
        (target, entry.get("fullUrl"))
        for entry in entries
        if entry.get("resource", {}).get("resourceType") != "Patient"
        for field in ("subject", "patient")
        if isinstance(target := entry.get("resource", {}).get(field), dict)
    ]
    subjects = [subject for subject, _ in sources]
    servers = {
        _restful_base(source_url)
        for subject, source_url in sources
        if isinstance(reference := subject.get("reference"), str)
        and reference
        and not _ABSOLUTE_REFERENCE.match(reference)
    }
    if patients:
        servers.add(_restful_base(patients[0].get("fullUrl")))
    if len(servers - {None}) <= 1:
        if patients:
            if all(_belongs_to_patient(subject, patients[0]) for subject in subjects):
                return dict(patients[0]["resource"])
        elif len({_subject_key(subject) for subject in subjects}) <= 1:
            return None
    raise ToolInputError(
        "Bundle mixes patients: a clinical resource references a different patient, or a "
        "patient that cannot be matched to the bundle's Patient; send one patient's "
        "resources per call."
    )


def _is_invalidated(resource: dict[str, Any]) -> bool:
    """True for resources recorded in error, cancelled observations or refuted findings."""
    if resource.get("resourceType") == "Observation" and resource.get("status") in {
        "entered-in-error",
        "cancelled",
    }:
        return True
    verification = resource.get("verificationStatus")
    codings = verification.get("coding", []) if isinstance(verification, dict) else []
    codes = {c.get("code") for c in codings if isinstance(c, dict)}
    return bool(codes & _INVALIDATED_VERIFICATION)


def _patient_redactor(patient: dict[str, Any] | None) -> Callable[[str], str]:
    """Return a function that redacts this Patient's own identifiers from free text."""
    tokens: set[str] = set()
    if patient:
        for name in patient.get("name", []):
            if isinstance(name, dict):
                parts = [name.get("text"), name.get("family")]
                parts += [*name.get("given", []), *name.get("prefix", []), *name.get("suffix", [])]
                tokens.update(p for p in parts if isinstance(p, str))
                if isinstance(name.get("text"), str):
                    tokens.update(name["text"].split())
        for field in ("identifier", "telecom"):
            tokens.update(
                item["value"]
                for item in patient.get(field, [])
                if isinstance(item, dict) and isinstance(item.get("value"), str)
            )
        for address in patient.get("address", []):
            if isinstance(address, dict):
                parts = [address.get("text"), address.get("city"), address.get("postalCode")]
                tokens.update(p for p in [*parts, *address.get("line", [])] if isinstance(p, str))
        tokens.update(
            patient[field] for field in ("id", "birthDate") if isinstance(patient.get(field), str)
        )
    words = sorted({t.strip() for t in tokens if len(t.strip()) >= 2}, key=len, reverse=True)
    if not words:
        return lambda text: text
    pattern = re.compile(
        r"(?<!\w)(?:" + "|".join(re.escape(word) for word in words) + r")(?!\w)",
        re.IGNORECASE,
    )
    return lambda text: pattern.sub(_REDACTED_PATIENT, text)


def _status_label(resource_type: str, raw_status: Any) -> str:
    """Return a recognised FHIR status code, ``missing`` or ``unrecognized``."""
    status = str(raw_status or "").lower()
    if not status:
        return "missing"
    return status if status in _KNOWN_STATUSES[resource_type] else "unrecognized"


def _select_medication_resources(
    entries: list[dict[str, Any]], *, include_proposed: bool
) -> tuple[list[dict[str, Any]], list[str]]:
    """Keep entries with current (and optionally proposed) medications; report the rest."""
    selected: list[dict[str, Any]] = []
    excluded: Counter[tuple[str, str]] = Counter()
    proposed = 0
    for entry in entries:
        resource = entry.get("resource", {})
        resource_type = str(resource.get("resourceType"))
        if resource_type not in _CURRENT_STATUSES:
            continue
        status = _status_label(resource_type, resource.get("status"))
        if status in _CURRENT_STATUSES[resource_type]:
            selected.append(entry)
        elif include_proposed and status in _PROPOSED_STATUSES[resource_type]:
            selected.append(entry)
            proposed += 1
        else:
            excluded[(resource_type, status)] += 1
    notes = [
        f"excluded {resource_type} status {status}: {count}"
        for (resource_type, status), count in sorted(excluded.items())
    ]
    if proposed:
        notes.append(
            f"included {proposed} proposed (draft/intended) medication(s) because "
            "include_proposed is true"
        )
    return selected, notes


def _concept_name(concept: Any) -> str | None:
    """Return a CodeableConcept's text or first coding display; a bare code is not a name."""
    if not isinstance(concept, dict):
        return None
    codings = concept.get("coding")
    candidates = [concept.get("text")]
    if isinstance(codings, list):
        candidates += [c.get("display") for c in codings if isinstance(c, dict)]
    return next((c for c in candidates if isinstance(c, str) and c.strip()), None)


def _restful_base(full_url: Any) -> str | None:
    """Return the server base of a RESTful ``fullUrl``, or None (absent, urn:uuid, ...)."""
    match = _RESTFUL_URL.match(full_url) if isinstance(full_url, str) else None
    return match.group("base") if match else None


def _resolve_medication(
    reference: str,
    entry: dict[str, Any],
    by_url: dict[str, dict[str, Any]],
    by_id: dict[str, list[tuple[str | None, dict[str, Any]]]],
) -> dict[str, Any] | None:
    """Resolve a medicationReference without guessing across servers or duplicate ids.

    Contained references resolve inside the resource; absolute ones by exact
    ``fullUrl``; relative ones against the requesting entry's server base, or by
    a logical id that is unique in the bundle and not hosted on another server.
    """
    resource = entry.get("resource", {})
    if reference.startswith("#"):
        contained = [
            item
            for item in resource.get("contained") or []
            if isinstance(item, dict)
            and item.get("resourceType") == "Medication"
            and f"#{item.get('id')}" == reference
        ]
        return contained[0] if len(contained) == 1 else None
    if reference in by_url:
        return by_url[reference]
    if _ABSOLUTE_REFERENCE.match(reference):
        return None
    base = _restful_base(entry.get("fullUrl"))
    if base is not None and f"{base}/{reference}" in by_url:
        return by_url[f"{base}/{reference}"]
    candidates = by_id.get(reference, [])
    if len(candidates) != 1:
        return None
    candidate_base, medication = candidates[0]
    if base is not None and candidate_base is not None and candidate_base != base:
        return None
    return medication


def _prepare_medication_resources(
    selected: list[dict[str, Any]], entries: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Name selected medications for the adapter and map MedicationStatement.dosage.

    A medication is named only by concept text, a coding display or the reference
    display; code-only or unresolvable medications get an empty concept so the
    adapter skips them and they are reported in ``screening_input_issues``.
    """
    by_url: dict[str, dict[str, Any]] = {}
    by_id: dict[str, list[tuple[str | None, dict[str, Any]]]] = {}
    for entry in entries:
        resource = entry.get("resource", {})
        if resource.get("resourceType") != "Medication":
            continue
        full_url = entry.get("fullUrl")
        if isinstance(full_url, str) and full_url:
            by_url[full_url] = resource
        if isinstance(resource.get("id"), str):
            by_id.setdefault(f"Medication/{resource['id']}", []).append(
                (_restful_base(full_url), resource)
            )
    prepared: list[dict[str, Any]] = []
    for entry in selected:
        resource = entry.get("resource", {})
        copy = dict(resource)
        concept = resource.get("medicationCodeableConcept")
        target = resource.get("medicationReference")
        target = target if isinstance(target, dict) else {}
        reference = target.get("reference")
        if concept is None and isinstance(reference, str):
            medication = _resolve_medication(reference, entry, by_url, by_id)
            concept = medication.get("code") if medication is not None else None
        name = _concept_name(concept)
        copy["medicationCodeableConcept"] = (
            {**concept, "text": name} if name and isinstance(concept, dict) else {}
        )
        if resource.get("resourceType") == "MedicationStatement" and "dosageInstruction" not in (
            resource
        ):
            if isinstance(resource.get("dosage"), list):
                copy["dosageInstruction"] = resource["dosage"]
        prepared.append(copy)
    return prepared


def _clean_record(record: BaseModel, clean: Callable[[str], str]) -> dict[str, Any]:
    """Dump a lab/vital record with every string field de-identified."""
    return {
        key: clean(value) if isinstance(value, str) else value
        for key, value in record.model_dump(mode="json").items()
    }


def _parse_fhir_bundle(arguments: dict[str, Any]) -> ToolOutput:
    """Normalise a FHIR R4 Bundle into de-identified, screening-ready context."""
    bundle: dict[str, Any] = arguments["bundle"]
    all_entries: list[dict[str, Any]] = bundle.get("entry", [])
    patient = _require_single_patient(all_entries)
    entries = [e for e in all_entries if not _is_invalidated(e.get("resource", {}))]
    invalidated = len(all_entries) - len(entries)
    prepared = _prefer_ucum_units(entries)
    try:
        context = parse_fhir_bundle({**bundle, "entry": prepared})
    except FHIRParseError as exc:
        raise ToolInputError(f"Invalid FHIR bundle: {exc}") from exc
    except (AttributeError, LookupError, TypeError, ValueError) as exc:
        raise ToolInputError(
            "FHIR bundle could not be parsed: a resource has an unexpected structure "
            f"({type(exc).__name__})."
        ) from exc

    resources = [entry.get("resource", {}) for entry in entries]
    selected, medication_notes = _select_medication_resources(
        entries, include_proposed=bool(arguments.get("include_proposed", False))
    )
    try:
        adapted = FhirMedicationRequestAdapter().adapt(
            _prepare_medication_resources(selected, entries)
        )
    except (AttributeError, LookupError, TypeError, ValueError) as exc:
        raise ToolInputError(
            "FHIR bundle could not be parsed: a medication resource has an unexpected "
            f"structure ({type(exc).__name__})."
        ) from exc
    _enforce_scope(
        [
            context.chief_complaint,
            *context.diagnoses_history,
            *context.allergies,
            *(
                str(value)
                for med in adapted.medications
                for value in med.model_dump().values()
                if value
            ),
            *(
                str(value)
                for lab in context.lab_results
                for value in lab.model_dump().values()
                if isinstance(value, str)
            ),
            *(vital.name for vital in context.vital_signs),
        ]
    )

    redact_patient = _patient_redactor(patient)

    def clean(text: str) -> str:
        return _clean_text(redact_patient(text))

    medications = [_medication_dict(medication, clean) for medication in adapted.medications]
    allergies = [clean(allergy) for allergy in context.allergies]
    egfr, egfr_used, egfr_skipped = _lowest_egfr(prepared)
    screening_patient: dict[str, Any] = {}
    if context.age is not None:
        screening_patient["age"] = context.age
    if allergies:
        screening_patient["allergies"] = allergies
    if egfr is not None:
        screening_patient["egfr"] = egfr
    screening_input = {"medications": medications, "patient": screening_patient}
    issues = validate(screening_input, _SCREEN_INPUT, "screening_input")
    if adapted.skipped_count:
        issues.append(
            f"{adapted.skipped_count} current medication(s) could not be named and are missing "
            "from screening_input; screening the list unchanged could miss interactions"
        )

    notes = [
        "Direct identifiers (name, birthDate, identifier, telecom, address) and the raw bundle "
        "are not returned; the patient id is HMAC-SHA256 hashed with PII_HASH_SALT, and free "
        "text is de-identified, including the Patient's own names and identifiers.",
        "Only current therapy (status active or on-hold) is kept; draft/intended orders are "
        "added only with include_proposed, and every other status is excluded and counted "
        "in medication_notes.",
        "pregnant, breastfeeding and hepatic_function are not derived from the bundle; "
        "add them to screening_input.patient when known.",
    ]
    if invalidated:
        notes.append(
            f"excluded {invalidated} invalidated resource(s) (entered-in-error, cancelled "
            "observations or refuted findings)."
        )
    if egfr is not None:
        notes.append(f"egfr is the lowest of {egfr_used} eGFR observation(s) in mL/min/1.73m².")
    if egfr_skipped:
        notes.append(
            f"skipped {egfr_skipped} eGFR observation(s) with missing or unsupported units "
            "or non-numeric values."
        )

    resource_types = Counter(
        rtype if (rtype := r.get("resourceType")) in _KNOWN_RESOURCE_TYPES else "Other"
        for r in resources
    )
    result: dict[str, Any] = {
        "patient_id_hash": context.patient_id_hash,
        "age": context.age,
        "sex": context.sex,
        "chief_complaint": clean(context.chief_complaint),
        "diagnoses": [clean(text) for text in context.diagnoses_history],
        "medications": medications,
        "medication_notes": [*medication_notes, *(clean(note) for note in adapted.notes)],
        "allergies": allergies,
        "lab_results": [_clean_record(lab, clean) for lab in context.lab_results],
        "vital_signs": [_clean_record(vital, clean) for vital in context.vital_signs],
        "resource_counts": dict(sorted(resource_types.items())),
        "screening_input": screening_input,
        "screening_input_issues": issues,
        "notes": notes,
        "disclaimer": MANDATORY_DISCLAIMER,
    }
    lines = [
        f"medagent parse_fhir_bundle: patient {context.patient_id_hash[:12]}… (hashed), "
        f"age {context.age if context.age is not None else 'unknown'}, "
        f"{len(medications)} medication(s), {len(allergies)} allergy record(s), "
        f"{len(context.lab_results)} lab result(s).",
        "Pass screening_input to screen_medications to screen this medication list."
        if not issues
        else "screening_input needs changes before screen_medications: " + "; ".join(issues),
        MANDATORY_DISCLAIMER,
    ]
    return ToolOutput(result, "\n".join(lines))


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

_SCREEN_INPUT: dict[str, Any] = {
    "type": "object",
    "properties": {
        "medications": {
            "type": "array",
            "minItems": 1,
            "maxItems": _MAX_MEDICATIONS,
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
        "screening_input_issues": _STRING_LIST,
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
        "screening_input_issues",
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
                    "maxItems": _MAX_MEDICATIONS,
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
            "Parse a single patient's FHIR R4 Bundle (Patient, Condition, MedicationRequest, "
            "MedicationStatement, Observation, AllergyIntolerance) into de-identified patient "
            "context: hashed patient id, age, current medications, allergies, labs and a "
            "screening_input object ready for screen_medications. Identifiers and the raw "
            "bundle are never returned. RESEARCH USE ONLY."
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
                },
                "include_proposed": {
                    "type": "boolean",
                    "default": False,
                    "description": (
                        "Also keep draft MedicationRequests and intended MedicationStatements "
                        "to screen proposed orders against current therapy."
                    ),
                },
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
        input_schema=_SCREEN_INPUT,
        output_schema=_SCREEN_OUTPUT,
        handler=_screen_medications,
    ),
)

TOOLS_BY_NAME: dict[str, ToolSpec] = {tool.name: tool for tool in TOOLS}
