"""CDS Hooks 2.0 service definitions advertised by ``GET /cds-services``.

Both services run medagent's deterministic, offline medication-safety checks on
the orders in an EHR ordering session. They are RESEARCH USE ONLY: cards are
advisory, never suggest or apply order changes, and every card carries the
mandatory disclaimer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from medagent.mcp.tools import EGFR_LOINC_CODES

SPEC_VERSION = "2.0"
ORDER_SIGN = "order-sign"
ORDER_SELECT = "order-select"

PROJECT_URL = "https://github.com/Francis1998/medagent-core"
GUIDE_URL = f"{PROJECT_URL}/blob/main/docs/guides/CDS_HOOKS_GUIDE.md"
SAFETY_URL = f"{PROJECT_URL}/blob/main/SAFETY.md"
SOURCE_LABEL = "medagent-core (research use only)"
TOPIC_SYSTEM = f"{PROJECT_URL}/cds-hooks/CodeSystem/topic"
OVERRIDE_REASON_SYSTEM = f"{PROJECT_URL}/cds-hooks/CodeSystem/override-reason"

# Prefetch key -> FHIR query template. Order matters: it is the order in which
# missing keys are reported. ``egfr`` requests the eGFR LOINC codes that the MCP
# ``parse_fhir_bundle`` tool recognises whatever their display text.
PREFETCH_TEMPLATES: dict[str, str] = {
    "patient": "Patient/{{context.patientId}}",
    "activeMedications": "MedicationRequest?patient={{context.patientId}}&status=active",
    "allergies": "AllergyIntolerance?patient={{context.patientId}}",
    "egfr": (
        "Observation?patient={{context.patientId}}&code="
        + ",".join(f"http://loinc.org|{code}" for code in EGFR_LOINC_CODES)
        + "&_sort=-date&_count=5"
    ),
}

# Consequence of each missing prefetch key, used to explain gaps on the coverage card.
PREFETCH_PURPOSE: dict[str, str] = {
    "patient": "age is unknown, so the Beers Criteria (65+) check did not run",
    "activeMedications": "the orders were not checked against current medications",
    "allergies": "the allergy checks did not run",
    "egfr": "renal dosing was not checked",
}

OVERRIDE_REASONS: tuple[dict[str, str], ...] = (
    {"code": "benefit-outweighs-risk", "display": "Benefit outweighs risk; will monitor"},
    {"code": "already-addressed", "display": "Already addressed (e.g. monitoring in place)"},
    {"code": "not-applicable", "display": "Not applicable to this patient"},
    {"code": "incorrect-match", "display": "Incorrect match (false positive)"},
    {"code": "reviewed-with-pharmacist", "display": "Reviewed with a pharmacist"},
)
OVERRIDE_REASON_CODES: frozenset[str] = frozenset(reason["code"] for reason in OVERRIDE_REASONS)

_DESCRIPTION = (
    "RESEARCH USE ONLY: not for clinical use and not FDA-cleared. Screens the medication "
    "orders {scope} with medagent-core's deterministic, offline medication-safety checks "
    "(every offline drug-interaction rule plus allergy, Beers 65+, renal dosing, duplicate "
    "therapy, QT, serotonergic, anticholinergic and boxed-warning checks) against current "
    "medications, allergies, age and eGFR. Cards are advisory for review by a licensed "
    "clinician: the service never suggests, changes or cancels orders and makes no LLM or "
    "network calls."
)
_USAGE_REQUIREMENTS = (
    "Research sandboxes only. The service does not verify CDS Hooks JWTs, so it must sit "
    "behind an authenticating gateway. It never queries the FHIR server: without prefetch it "
    "screens the draft orders alone and returns an info card naming the missing keys."
)


@dataclass(frozen=True)
class CdsService:
    """One CDS Service: the hook it answers and its discovery metadata."""

    id: str
    hook: str
    title: str
    description: str
    usage_requirements: str = _USAGE_REQUIREMENTS
    prefetch: dict[str, str] = field(default_factory=lambda: dict(PREFETCH_TEMPLATES))

    def definition(self) -> dict[str, Any]:
        """Return the service entry of the discovery response."""
        return {
            "hook": self.hook,
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "prefetch": dict(self.prefetch),
            "usageRequirements": self.usage_requirements,
        }


SERVICES: tuple[CdsService, ...] = (
    CdsService(
        id="medagent-medication-safety",
        hook=ORDER_SIGN,
        title="medagent-core medication-safety screen (research use only)",
        description=_DESCRIPTION.format(scope="being signed"),
    ),
    CdsService(
        id="medagent-medication-safety-select",
        hook=ORDER_SELECT,
        title="medagent-core medication-safety screen at order selection (research use only)",
        description=_DESCRIPTION.format(
            scope="just selected (cards only for findings that involve a selected order)"
        ),
    ),
)
SERVICES_BY_ID: dict[str, CdsService] = {service.id: service for service in SERVICES}


def discovery_document() -> dict[str, Any]:
    """Return the ``GET /cds-services`` response body."""
    return {"services": [service.definition() for service in SERVICES]}
