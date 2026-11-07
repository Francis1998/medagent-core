"""Evaluate CDS Hooks ``order-sign`` / ``order-select`` calls with the deterministic checks.

FHIR → medagent → cards:

1. The draft MedicationRequests in ``context.draftOrders`` (for ``order-select``,
   split into the selected orders and the rest) and the prefetched Patient,
   active medications, allergies and eGFR observations are bound to
   ``context.patientId``; a resource that names any other patient is rejected.
2. Each group is normalised by the MCP ``parse_fhir_bundle`` tool, which applies
   the medication status policy, names medications from text or display only,
   de-identifies free text, enforces scope and converts eGFR units exactly.
3. The combined list is screened once by the MCP ``screen_medications`` tool:
   every patient-context, medication-list and offline interaction check.
4. Findings that involve none of the ordered (``order-select``: selected)
   medications are dropped; the rest become one card per involved-medication set.

No FHIR server, LLM or other network service is ever called. RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from medagent.cds_hooks.requests import (
    MAX_BUNDLE_ENTRIES,
    CdsHooksRequestError,
    HookRequest,
    parse_hook_request,
)
from medagent.cds_hooks.services import (
    GUIDE_URL,
    ORDER_SELECT,
    OVERRIDE_REASON_SYSTEM,
    OVERRIDE_REASONS,
    PREFETCH_PURPOSE,
    PREFETCH_TEMPLATES,
    SAFETY_URL,
    SOURCE_LABEL,
    TOPIC_SYSTEM,
    CdsService,
)
from medagent.llm.validator import MedicalOutputValidationError, MedicalOutputValidator
from medagent.logging_config import get_logger
from medagent.mcp.schema import validate
from medagent.mcp.tools import (
    COVERAGE_NOTE,
    TOOLS_BY_NAME,
    ToolInputError,
    _select_medication_resources,
    interaction_checks,
    screening_checks,
)
from medagent.safety.disclaimer import MANDATORY_DISCLAIMER
from medagent.safety.pii_hasher import hash_pii

logger = get_logger(__name__)

SUMMARY_MAX_CHARS = 139  # CDS Hooks 2.0: "<140-character summary"

# medagent severity -> CDS Hooks card indicator (documented in CDS_HOOKS_GUIDE.md).
INDICATOR_BY_SEVERITY: dict[str, str] = {
    "CRITICAL": "critical",
    "HIGH": "warning",
    "MODERATE": "warning",
    "LOW": "info",
    "UNKNOWN": "warning",
}
INDICATOR_RANK: dict[str, int] = {"critical": 0, "warning": 1, "info": 2}
COVERAGE_TOPIC = "screen_coverage"
TOPIC_DISPLAY: dict[str, str] = {
    "interaction": "Drug-drug interaction",
    "medication_list": "Medication-list risk",
    "patient_context": "Patient-specific risk",
    COVERAGE_TOPIC: "Screening coverage",
}

_SEVERITY_WORD = {
    "CRITICAL": "Critical",
    "HIGH": "High",
    "MODERATE": "Moderate",
    "LOW": "Low",
    "UNKNOWN": "Unrated",
}
_ESCALATING = frozenset({"CRITICAL", "HIGH"})
_PREFETCH_RESOURCE_TYPES: dict[str, frozenset[str]] = {
    "activeMedications": frozenset({"MedicationRequest", "MedicationStatement", "Medication"}),
    "allergies": frozenset({"AllergyIntolerance"}),
    "egfr": frozenset({"Observation"}),
}
_GAP_TEXT = {
    "missing": "was not provided",
    "error": "held an error (OperationOutcome) or unexpected data; only its usable entries were "
    "screened",
    "incomplete": "was paginated, so only its first page was screened (this service never "
    "fetches more)",
}
_PATIENT_REFERENCE = re.compile(
    r"(?:https?://\S+/)?Patient/(?P<id>[A-Za-z0-9\-.]{1,64})(?:/_history/[A-Za-z0-9\-.]{1,64})?"
)
# Inline GitHub Flavored Markdown that caller-derived text must not create: code,
# emphasis, strikethrough, links/images, raw HTML, entities, math and extended
# autolinks (``scheme://``, ``www.``, ``user@host``). Block-level syntax cannot
# start inside that text, because every such line begins with fixed text.
_MARKDOWN_SPECIAL = re.compile(r"[\\`*_~\[\]<>&$@]|:(?=//)|(?<=www)\.", re.IGNORECASE)

_PARSE = TOOLS_BY_NAME["parse_fhir_bundle"]
_SCREEN = TOOLS_BY_NAME["screen_medications"]
_MEDICATIONS_SCHEMA: dict[str, Any] = _SCREEN.input_schema["properties"]["medications"]
_PATIENT_SCHEMA: dict[str, Any] = _SCREEN.input_schema["properties"]["patient"]
_OUTPUT_GUARD = MedicalOutputValidator()


@dataclass(frozen=True)
class HookResult:
    """Cards for one service call plus the de-identified audit events describing it."""

    cards: list[dict[str, Any]]
    audit_events: list[dict[str, Any]]
    finding_count: int
    prefetch_gaps: tuple[str, ...]

    @property
    def highest_indicator(self) -> str | None:
        """Most urgent card indicator, or None without cards."""
        indicators = [str(card["indicator"]) for card in self.cards]
        return min(indicators, key=lambda name: INDICATOR_RANK.get(name, 3), default=None)


@dataclass
class _Context:
    """Prefetched data bound to the patient in context."""

    patient: dict[str, Any]
    medications: list[dict[str, Any]] = field(default_factory=list)
    medication_definitions: list[dict[str, Any]] = field(default_factory=list)
    allergies: list[dict[str, Any]] = field(default_factory=list)
    observations: list[dict[str, Any]] = field(default_factory=list)
    allergies_known: bool = False
    gaps: dict[str, str] = field(default_factory=dict)


@dataclass
class _Coverage:
    """What the screen could not cover, reported on the coverage card."""

    gaps: dict[str, str]
    unscreened_ordered: int = 0
    unscreened_other: int = 0
    status_notes: list[str] = field(default_factory=list)
    unused_context: list[str] = field(default_factory=list)
    not_run: str | None = None

    def needs_card(self) -> bool:
        return bool(
            self.gaps
            or self.unscreened_ordered
            or self.unscreened_other
            or self.unused_context
            or self.not_run
        )


# ---------------------------------------------------------------------------
# FHIR input
# ---------------------------------------------------------------------------


def _patient_mismatch() -> CdsHooksRequestError:
    return CdsHooksRequestError(
        "patient_mismatch",
        "Every draft order and prefetched resource must reference context.patientId; "
        "send one patient's resources per call.",
    )


def _names_patient(target: Any, patient_id: str) -> bool:
    """True when a FHIR reference points at ``Patient/<patient_id>`` (relative or absolute)."""
    reference = target.get("reference") if isinstance(target, dict) else None
    match = _PATIENT_REFERENCE.fullmatch(reference) if isinstance(reference, str) else None
    return match is not None and match.group("id") == patient_id


def _bound(entry: Mapping[str, Any], patient_id: str) -> dict[str, Any]:
    """Copy a clinical entry with its patient reference verified and made relative.

    The CDS Client's request fixes the patient; any ``subject``/``patient``
    reference to someone else (or one that cannot be verified, such as an
    identifier-only reference) is rejected rather than screened.
    """
    resource: dict[str, Any] = dict(entry["resource"])
    for name in ("subject", "patient"):
        if name in resource:
            if not _names_patient(resource[name], patient_id):
                raise _patient_mismatch()
            resource[name] = {"reference": f"Patient/{patient_id}"}
    return {"resource": resource}


def _reports_error(outcome: Mapping[str, Any]) -> bool:
    issues = outcome.get("issue")
    return isinstance(issues, list) and any(
        isinstance(issue, dict) and issue.get("severity") in {"error", "fatal"} for issue in issues
    )


def _prefetched_entries(
    value: Mapping[str, Any], allowed: frozenset[str]
) -> tuple[list[dict[str, Any]], str | None]:
    """Return the usable entries of one prefetched search result and its gap, if any."""
    if value.get("resourceType") in allowed:
        return [{"resource": dict(value)}], None
    if value.get("resourceType") != "Bundle":
        return [], "error"
    raw = value.get("entry", [])
    if not isinstance(raw, list):
        return [], "error"
    if len(raw) > MAX_BUNDLE_ENTRIES:
        raise CdsHooksRequestError(
            "too_many_entries",
            f"Each prefetched Bundle must have at most {MAX_BUNDLE_ENTRIES} entries.",
        )
    entries: list[dict[str, Any]] = []
    gap: str | None = None
    for item in raw:
        resource = item.get("resource") if isinstance(item, dict) else None
        if not isinstance(resource, dict):
            gap = "error"
        elif resource.get("resourceType") == "OperationOutcome":
            gap = "error" if _reports_error(resource) else gap
        elif resource.get("resourceType") in allowed:
            entries.append(dict(item))
    links = value.get("link")
    if gap is None and isinstance(links, list):
        if any(isinstance(link, dict) and link.get("relation") == "next" for link in links):
            gap = "incomplete"
    return entries, gap


def _read_prefetch(prefetch: Mapping[str, Any], patient_id: str) -> _Context:
    """Bind the prefetched data to the patient and record which keys are unusable.

    A key the client omits is ``missing``; ``null`` means the client has no data
    for the query (CDS Hooks 2.0), which is complete information, not a gap.
    """
    context = _Context(patient={"resourceType": "Patient", "id": patient_id})
    for key in PREFETCH_TEMPLATES:
        if key not in prefetch:
            context.gaps[key] = "missing"
            continue
        value = prefetch[key]
        if value is None:
            continue
        if not isinstance(value, dict):
            context.gaps[key] = "error"
            continue
        if key == "patient":
            if value.get("resourceType") != "Patient":
                context.gaps[key] = "error"
            elif value.get("id", patient_id) != patient_id:
                raise _patient_mismatch()
            else:
                context.patient = {**value, "id": patient_id}
            continue
        entries, gap = _prefetched_entries(value, _PREFETCH_RESOURCE_TYPES[key])
        if gap is not None:
            context.gaps[key] = gap
        for entry in entries:
            resource_type = entry["resource"].get("resourceType")
            if resource_type == "Medication":
                context.medication_definitions.append(entry)
            elif key == "activeMedications":
                context.medications.append(_bound(entry, patient_id))
            elif key == "allergies":
                context.allergies.append(_bound(entry, patient_id))
            else:
                context.observations.append(_bound(entry, patient_id))
    # A satisfied allergies key (null = none on record) lets the allergy checks run.
    context.allergies_known = "allergies" in prefetch and context.gaps.get("allergies") != "error"
    return context


def _references(entry: Mapping[str, Any]) -> set[str]:
    """Ways a ``selections`` item can name a draftOrders entry: ``Type/id`` or ``fullUrl``."""
    resource = entry["resource"]
    names: set[str] = set()
    resource_type, resource_id = resource.get("resourceType"), resource.get("id")
    if isinstance(resource_type, str) and isinstance(resource_id, str):
        names.add(f"{resource_type}/{resource_id}")
    full_url = entry.get("fullUrl")
    if isinstance(full_url, str) and full_url:
        names.add(full_url)
    return names


def _split_orders(
    request: HookRequest, draft_requests: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (ordered, other) draft MedicationRequests; ``order-select`` focuses on selections."""
    if not request.selections:
        return draft_requests, []
    wanted = set(request.selections)
    found = set().union(*(_references(entry) for entry in request.draft_entries))
    if not wanted <= found:
        raise CdsHooksRequestError(
            "unknown_selection",
            "context.selections must reference resources in context.draftOrders, "
            "e.g. 'MedicationRequest/<id>'.",
        )
    ordered = [entry for entry in draft_requests if _references(entry) & wanted]
    other = [entry for entry in draft_requests if not _references(entry) & wanted]
    return ordered, other


def _bundle(patient: Mapping[str, Any], entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": dict(patient)}, *entries],
    }


def _parse(bundle: dict[str, Any], *, include_proposed: bool) -> dict[str, Any]:
    """Run the MCP ``parse_fhir_bundle`` tool; its errors become HTTP 400s."""
    arguments = {"bundle": bundle, "include_proposed": include_proposed}
    if validate(arguments, _PARSE.input_schema):
        raise CdsHooksRequestError(
            "too_many_entries",
            f"Each group of FHIR resources must have at most {MAX_BUNDLE_ENTRIES} entries.",
        )
    try:
        return _PARSE.handler(arguments).structured
    except ToolInputError as exc:
        # Messages are fixed text plus counts (see mcp/tools.py); no caller text.
        raise CdsHooksRequestError("invalid_fhir", f"FHIR data rejected: {exc}") from None
    except (AttributeError, LookupError, TypeError, ValueError) as exc:
        raise CdsHooksRequestError(
            "invalid_fhir",
            "FHIR data could not be parsed: a resource has an unexpected structure "
            f"({type(exc).__name__}).",
        ) from None


def _screenable(medication: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return the medication within the screening limits, keeping only its name if needed."""
    item_schema: dict[str, Any] = _MEDICATIONS_SCHEMA["items"]
    candidate = dict(medication)
    if not validate(candidate, item_schema):
        return candidate
    name_only = {"name": medication.get("name")}
    return name_only if not validate(name_only, item_schema) else None


def _named_medications(
    context: _Context, entries: list[dict[str, Any]], definitions: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], int]:
    """Parse status-filtered medication entries; return the screenable ones and the rest's count.

    ``include_proposed`` is safe here because the status policy has already been
    applied by ``_select_medication_resources``.
    """
    if not entries:
        return [], 0
    result = _parse(_bundle(context.patient, [*entries, *definitions]), include_proposed=True)
    screenable = [med for raw in result["medications"] if (med := _screenable(raw)) is not None]
    return screenable, len(entries) - len(screenable)


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _check_titles() -> dict[str, str]:
    return {check.id: check.title for check in (*screening_checks(), *interaction_checks())}


def _plain(text: str) -> str:
    """One line of text without control or format characters (e.g. bidi overrides)."""
    cleaned = "".join(" " if unicodedata.category(char) in {"Cc", "Cf"} else char for char in text)
    return " ".join(cleaned.split())


def _md(text: str) -> str:
    """Render caller-derived text as inert Markdown (no links, images, HTML or emphasis)."""
    return _MARKDOWN_SPECIAL.sub(lambda match: "\\" + match.group(0), _plain(text))


def _fit(prefix: str, body: str, suffix: str = "") -> str:
    """Join a summary, shortening ``body`` so the result stays under 140 characters."""
    budget = SUMMARY_MAX_CHARS - len(prefix) - len(suffix)
    if len(body) > budget:
        body = body[: max(budget - 1, 0)].rstrip() + "…"
    return (prefix + body + suffix)[:SUMMARY_MAX_CHARS]


def _source(topic: str) -> dict[str, Any]:
    return {
        "label": SOURCE_LABEL,
        "url": SAFETY_URL,
        "topic": {"system": TOPIC_SYSTEM, "code": topic, "display": TOPIC_DISPLAY[topic]},
    }


def _links() -> list[dict[str, str]]:
    return [
        {
            "label": "How this research-only service screens orders",
            "url": GUIDE_URL,
            "type": "absolute",
        }
    ]


def _override_reasons() -> list[dict[str, str]]:
    return [{"system": OVERRIDE_REASON_SYSTEM, **reason} for reason in OVERRIDE_REASONS]


def _disclaimer_lines() -> list[str]:
    return [
        f"**{MANDATORY_DISCLAIMER}**",
        "",
        "Advisory output of medagent-core's deterministic, offline medication-safety checks "
        "for review by a licensed clinician. It is not a prescription or treatment order, and "
        "this service never changes, adds or cancels orders.",
    ]


def _skipped_text(skipped: Sequence[Mapping[str, Any]]) -> str:
    return ", ".join(
        f"`{item['check_id']}` (needs {', '.join(f'`{need}`' for need in item['missing'])})"
        for item in skipped
    )


def _finding_card(
    findings: list[dict[str, Any]],
    provenance: Mapping[str, list[str]],
    skipped: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """One card for every finding that involves the same set of medications."""
    top = findings[0]
    severity = str(top["severity"])
    medications = [str(name) for name in top["medications"]]
    topic = str(top["category"])
    label = (
        TOPIC_DISPLAY["interaction"]
        if topic == "interaction"
        else _check_titles().get(top["check_id"], TOPIC_DISPLAY[topic])
    )
    suffix = f" ({len(findings)} checks)" if len(findings) > 1 else ""
    summary = _fit(
        f"{_SEVERITY_WORD.get(severity, 'Unrated')} — {label}: ",
        " + ".join(_plain(name) for name in medications) or "medication list",
        suffix,
    )

    involved = "; ".join(
        f"{_md(name)} ({' and '.join(provenance[name])})" if name in provenance else _md(name)
        for name in medications
    )
    detail = [
        *_disclaimer_lines(),
        "",
        f"**Medications involved:** {involved or 'the medication list'}",
        "",
        f"**Deterministic checks that fired ({len(findings)}):**",
        "",
    ]
    for index, finding in enumerate(findings, start=1):
        section = f" · SAFETY.md §{finding['safety_section']}" if finding["safety_section"] else ""
        detail.append(
            f"{index}. `{finding['check_id']}` ({finding['checker']}) · severity "
            f"**{finding['severity']}**{section}"
        )
        detail.append(f"   *Rationale:* {_md(str(finding['rationale']))}")
    if severity in _ESCALATING:
        detail += [
            "",
            "**Escalation recommended:** HIGH and CRITICAL findings need review by a licensed "
            "clinician or pharmacist.",
        ]
    if skipped:
        detail += ["", f"**Not run in this call (missing context):** {_skipped_text(skipped)}."]
    detail += ["", f"*{COVERAGE_NOTE}*"]
    return {
        "uuid": str(uuid.uuid4()),
        "summary": summary,
        "indicator": INDICATOR_BY_SEVERITY.get(severity, "warning"),
        "detail": "\n".join(detail),
        "source": _source(topic),
        "overrideReasons": _override_reasons(),
        "links": _links(),
    }


def _coverage_card(coverage: _Coverage) -> dict[str, Any]:
    """Info card (warning when nothing could be screened) describing coverage gaps."""
    unscreened = coverage.unscreened_ordered + coverage.unscreened_other
    if coverage.not_run:
        indicator = "warning"
        summary = _fit("Medication-safety screen not run: ", coverage.not_run)
    else:
        indicator = "info"
        parts = []
        if coverage.gaps:
            missing = set(coverage.gaps.values()) == {"missing"}
            parts.append(
                ("missing" if missing else "incomplete") + " prefetch " + ", ".join(coverage.gaps)
            )
        if unscreened:
            parts.append(f"{unscreened} medication(s) not screened")
        if coverage.unused_context:
            parts.append("unusable " + ", ".join(coverage.unused_context))
        summary = _fit("Partial medication-safety screen: ", "; ".join(parts))

    detail = [
        *_disclaimer_lines(),
        "",
        "The deterministic screen ran with less information than it needs, so its cards (or "
        "their absence) cover only part of the regimen. This service never queries the FHIR "
        "server and never calls an LLM.",
        "",
    ]
    if coverage.not_run:
        detail.append(f"- **The screen did not run:** {coverage.not_run}.")
    for key, gap in coverage.gaps.items():
        consequence = f": {PREFETCH_PURPOSE[key]}" if gap == "missing" else ""
        detail.append(f"- Prefetch `{key}` {_GAP_TEXT[gap]}{consequence}.")
    if coverage.unscreened_ordered:
        detail.append(
            f"- {coverage.unscreened_ordered} ordered medication(s) could not be screened: no "
            "medication name (code-only, or a medicationReference that is not in the request) "
            "or a name longer than the screening limit."
        )
    if coverage.unscreened_other:
        detail.append(
            f"- {coverage.unscreened_other} other medication(s) (unsigned or current) could not "
            "be screened for the same reasons."
        )
    for key in coverage.unused_context:
        detail.append(f"- `{key}` was outside the screening limits and was not used.")
    for note in coverage.status_notes:
        detail.append(f"- Not screened because of order status: {_md(note)}.")
    detail += [
        "",
        "Configure the EHR to satisfy the prefetch templates listed by `GET /cds-services`.",
        "",
        f"*{COVERAGE_NOTE}*",
    ]
    return {
        "uuid": str(uuid.uuid4()),
        "summary": summary,
        "indicator": indicator,
        "detail": "\n".join(detail),
        "source": _source(COVERAGE_TOPIC),
        "links": _links(),
    }


def _strings(value: Any) -> Iterator[str]:
    """Yield every string value and object key nested in ``value``."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _guarded(card: dict[str, Any], check_ids: Sequence[str]) -> dict[str, Any]:
    """Withhold a card whose text matches prohibited prescription language (SAFETY.md §3.3)."""
    try:
        for text in _strings(card):
            _OUTPUT_GUARD.check_prohibited_language(text)
    except MedicalOutputValidationError:
        logger.error("cds_hooks_card_withheld", check_ids=list(check_ids))
        modules = ", ".join(f"`{check_id}`" for check_id in check_ids)
        return {
            "uuid": str(uuid.uuid4()),
            "summary": "Medication-safety finding withheld by the output guard; escalate it",
            "indicator": card["indicator"],
            "detail": "\n".join(
                [
                    *_disclaimer_lines(),
                    "",
                    f"A finding from {modules} was withheld because its text matched prohibited "
                    "prescription language (SAFETY.md §3.3). Escalate to a licensed clinician "
                    "or pharmacist.",
                ]
            ),
            "source": card["source"],
            "links": _links(),
        }
    return card


# ---------------------------------------------------------------------------
# Service call
# ---------------------------------------------------------------------------


def _relevant(finding: Mapping[str, Any], ordered: set[str], known: set[str]) -> bool:
    """Keep findings that involve an ordered medication, or that cannot be attributed."""
    involved = [str(name) for name in finding["medications"]]
    return not involved or any(name in ordered or name not in known for name in involved)


def _result(
    service: CdsService,
    request: HookRequest,
    cards: list[tuple[dict[str, Any], list[str]]],
    finding_count: int,
    gaps: Mapping[str, str],
) -> HookResult:
    """Assemble the response and its audit events (hashes, ids and codes only)."""
    instance_hash = hash_pii(request.hook_instance)
    fired = sorted({check_id for _, ids in cards for check_id in ids} - {COVERAGE_TOPIC})
    events: list[dict[str, Any]] = [
        {
            "event": "card",
            "service_id": service.id,
            "hook": service.hook,
            "hook_instance_hash": instance_hash,
            "card_uuid": card["uuid"],
            "indicator": card["indicator"],
            "check_ids": ",".join(ids),
        }
        for card, ids in cards
    ]
    result = HookResult(
        cards=[card for card, _ in cards],
        audit_events=events,
        finding_count=finding_count,
        prefetch_gaps=tuple(gaps),
    )
    events.insert(
        0,
        {
            "event": "service_call",
            "service_id": service.id,
            "hook": service.hook,
            "hook_instance_hash": instance_hash,
            "patient_id_hash": hash_pii(request.patient_id),
            "user_id_hash": hash_pii(request.user_id),
            "card_count": len(cards),
            "finding_count": finding_count,
            "indicator": result.highest_indicator,
            "check_ids": ",".join(fired) or None,
            "prefetch_gaps": ",".join(gaps) or None,
        },
    )
    return result


def _current_context(
    context: _Context, current: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any], int]:
    """Parse prefetched current therapy, allergies, eGFR and age into screening input.

    Returns:
        (screenable current medications, patient context, unscreenable count).
    """
    parsed = _parse(
        _bundle(
            context.patient,
            [*current, *context.medication_definitions, *context.allergies, *context.observations],
        ),
        include_proposed=False,
    )
    medications = [med for raw in parsed["medications"] if (med := _screenable(raw)) is not None]
    patient: dict[str, Any] = dict(parsed["screening_input"]["patient"])
    if context.allergies_known:
        patient.setdefault("allergies", [])
    return medications, patient, len(current) - len(medications)


def _provenance(
    screened: Sequence[str], n_ordered: int, n_other: int, hook: str
) -> dict[str, list[str]]:
    """Label each screened medication name with where it came from."""
    ordered_label = "selected order" if hook == ORDER_SELECT else "draft order"
    labels: dict[str, list[str]] = {}
    for index, name in enumerate(screened):
        if index < n_ordered:
            label = ordered_label
        elif index < n_ordered + n_other:
            label = "other unsigned order"
        else:
            label = "current medication"
        names = labels.setdefault(name, [])
        if label not in names:
            names.append(label)
    return labels


def _screen(
    request: HookRequest,
    ordered: list[dict[str, Any]],
    other: list[dict[str, Any]],
    current: list[dict[str, Any]],
    patient: dict[str, Any],
    coverage: _Coverage,
) -> tuple[list[tuple[dict[str, Any], list[str]]], int]:
    """Screen the regimen once and return (cards with their check ids, finding count)."""
    medications = [*ordered, *other, *current]
    max_medications = int(_MEDICATIONS_SCHEMA["maxItems"])
    arguments = {"medications": medications, "patient": patient}
    if not ordered:
        coverage.not_run = "no ordered medication could be named"
    elif len(medications) > max_medications:
        coverage.not_run = (
            f"the regimen has more than {max_medications} medications, the screening limit"
        )
    elif validate(arguments, _SCREEN.input_schema):
        coverage.not_run = "the screening input could not be validated"
    if coverage.not_run:
        return [], 0
    try:
        screen = _SCREEN.handler(arguments).structured
    except ToolInputError as exc:
        # Fixed scope-enforcement text (SAFETY.md §3.6); no caller text.
        raise CdsHooksRequestError("scope_violation", str(exc)) from None

    screened = [str(name) for name in screen["medications_screened"]]
    provenance = _provenance(screened, len(ordered), len(other), request.hook)
    ordered_names = set(screened[: len(ordered)])
    findings = [
        finding
        for finding in screen["findings"]
        if _relevant(finding, ordered_names, set(screened))
    ]
    # Findings arrive sorted by severity, category and check id, so groups (and
    # cards) keep a deterministic, most-severe-first order.
    groups: dict[frozenset[str], list[dict[str, Any]]] = {}
    for finding in findings:
        groups.setdefault(frozenset(finding["medications"]), []).append(finding)
    cards: list[tuple[dict[str, Any], list[str]]] = []
    for group in groups.values():
        check_ids = [str(finding["check_id"]) for finding in group]
        card = _finding_card(group, provenance, screen["checks_skipped"])
        cards.append((_guarded(card, check_ids), check_ids))
    return cards, len(findings)


def evaluate_hook(service: CdsService, body: Any) -> HookResult:
    """Validate a CDS Hooks call and screen its medication orders.

    Args:
        service: The CDS Service addressed by the request path.
        body: Decoded JSON request body.

    Returns:
        The cards (``[]`` when there is nothing to report) and audit events.

    Raises:
        CdsHooksRequestError: For invalid requests, including resources that
            reference a patient other than ``context.patientId``.
    """
    request = parse_hook_request(body, service)
    patient_id = request.patient_id
    context = _read_prefetch(request.prefetch, patient_id)
    draft_requests = [
        entry
        for entry in request.draft_entries
        if entry["resource"].get("resourceType") == "MedicationRequest"
    ]
    draft_definitions = [
        dict(entry)
        for entry in request.draft_entries
        if entry["resource"].get("resourceType") == "Medication"
    ]
    ordered_entries, other_entries = _split_orders(request, draft_requests)
    ordered, status_notes = _select_medication_resources(
        [_bound(entry, patient_id) for entry in ordered_entries], include_proposed=True
    )
    if not ordered:
        # No medication order to screen (e.g. only lab orders or discontinuations).
        return _result(service, request, [], 0, context.gaps)
    other, _ = _select_medication_resources(
        [_bound(entry, patient_id) for entry in other_entries], include_proposed=True
    )
    # A current order that is being revised in this session is screened once, as a draft.
    draft_ids = {
        resource_id
        for entry in draft_requests
        if isinstance(resource_id := entry["resource"].get("id"), str)
    }
    current, _ = _select_medication_resources(
        [
            entry
            for entry in context.medications
            if not (
                entry["resource"].get("resourceType") == "MedicationRequest"
                and entry["resource"].get("id") in draft_ids
            )
        ],
        include_proposed=False,
    )

    ordered_meds, unscreened_ordered = _named_medications(context, ordered, draft_definitions)
    other_meds, unscreened_other = _named_medications(context, other, draft_definitions)
    current_meds, patient, unscreened_current = _current_context(context, current)
    coverage = _Coverage(
        gaps=context.gaps,
        unscreened_ordered=unscreened_ordered,
        unscreened_other=unscreened_other + unscreened_current,
        # Only exclusions matter here; the policy also notes included draft orders.
        status_notes=[note for note in status_notes if note.startswith("excluded ")],
    )
    for key in sorted(patient):
        if validate({key: patient[key]}, _PATIENT_SCHEMA):
            coverage.unused_context.append(key)
            del patient[key]

    cards, finding_count = _screen(
        request, ordered_meds, other_meds, current_meds, patient, coverage
    )
    if coverage.needs_card():
        cards.append((_guarded(_coverage_card(coverage), [COVERAGE_TOPIC]), [COVERAGE_TOPIC]))
    return _result(service, request, cards, finding_count, context.gaps)
