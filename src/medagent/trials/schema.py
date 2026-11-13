"""JSON Schemas and constants for research-only clinical-trial eligibility pre-screening.

The trial-definition format (``schema_version`` ``1.0``) embeds the
ClinicalTrials.gov API v2 ``protocolSection.eligibilityModule`` object verbatim
(``sex``, ``minimumAge``, ``maximumAge``, ``healthyVolunteers``,
``eligibilityCriteria``, ...) and adds structured ``inclusion`` / ``exclusion``
criteria. The schemas are the single source of truth for argument validation
(``medagent.mcp.schema.validate``), the MCP ``inputSchema``/``outputSchema`` of
``screen_trial_eligibility`` and the OpenAPI body of ``POST /trials/eligibility``.

This module imports nothing from ``medagent.mcp`` so the MCP tool registry can
import it. RESEARCH USE ONLY.
"""

from __future__ import annotations

from typing import Any

from medagent.safety.disclaimer import MANDATORY_DISCLAIMER
from medagent.safety.duplicate_therapy import _THERAPEUTIC_CLASSES

SCHEMA_VERSION = "1.0"

INCLUSION = "inclusion"
EXCLUSION = "exclusion"
SECTIONS: tuple[str, ...] = (INCLUSION, EXCLUSION)

CRITERION_TYPES: tuple[str, ...] = (
    "condition",
    "medication",
    "lab",
    "pregnancy",
    "lactation",
    "free_text",
)
# Criteria derived from the eligibilityModule; trial authors cannot declare them.
DERIVED_CRITERION_TYPES: tuple[str, ...] = ("sex", "age")
RESERVED_ID_PREFIX = "eligibility."

MET = "met"
NOT_MET = "not_met"
INSUFFICIENT_DATA = "insufficient_data"
REQUIRES_HUMAN_REVIEW = "requires_human_review"
CRITERION_STATUSES: tuple[str, ...] = (MET, NOT_MET, INSUFFICIENT_DATA, REQUIRES_HUMAN_REVIEW)

POTENTIALLY_ELIGIBLE = "potentially_eligible"
NEEDS_REVIEW = "needs_review"
LIKELY_INELIGIBLE = "likely_ineligible"
TRIAL_STATUSES: tuple[str, ...] = (POTENTIALLY_ELIGIBLE, NEEDS_REVIEW, LIKELY_INELIGIBLE)

OPERATORS: tuple[str, ...] = (">=", ">", "<=", "<", "between")

# Therapeutic classes reuse the duplicate-therapy checker's whole-token member lists.
MEDICATION_CLASSES: dict[str, frozenset[str]] = {
    name: members for name, _severity, members in _THERAPEUTIC_CLASSES
}

MAX_TRIALS = 20
MAX_CRITERIA_PER_SECTION = 50
MAX_BUNDLE_ENTRIES = 5000

ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"
VERSION_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,31}$"
# ClinicalTrials.gov NormalizedTime, e.g. "18 Years" or "28 Days"; "N/A" is the classic API's
# "no limit" (API v2 omits the field instead).
NORMALIZED_TIME_PATTERN = r"^(?:N/A|[0-9]{1,3} (?:Years?|Months?|Weeks?|Days?|Hours?|Minutes?))$"
DATE_PATTERN = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"

_NON_BLANK = r"\S"
_NULLABLE_STRING: dict[str, Any] = {"anyOf": [{"type": "string"}, {"type": "null"}]}
_STRING_LIST: dict[str, Any] = {"type": "array", "items": {"type": "string"}}


def _text(max_length: int) -> dict[str, Any]:
    return {"type": "string", "minLength": 1, "maxLength": max_length, "pattern": _NON_BLANK}


_CODE_REF: dict[str, Any] = {
    "type": "object",
    "description": "A coded concept. Codes match exactly; 'prefix' (conditions only) also "
    "matches longer codes, e.g. ICD-10-CM C34 matches C34.90.",
    "properties": {
        "system": {"type": "string", "minLength": 1, "maxLength": 200, "pattern": r"^\S+$"},
        "code": {"type": "string", "minLength": 1, "maxLength": 64, "pattern": r"^\S+$"},
        "match": {"type": "string", "enum": ["exact", "prefix"]},
    },
    "required": ["system", "code"],
    "additionalProperties": False,
}

CRITERION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "One structured criterion. Fields allowed per type: condition (codes and/or terms, "
        "presence, status, within_days); medication (ingredients, classes and/or "
        "rxnorm_codes, presence); lab (codes and/or terms, operator, value + unit or "
        "low + high, optional relative_to, within_days); pregnancy and lactation (presence, "
        "within_days); free_text (id, type and text only: always requires_human_review)."
    ),
    "properties": {
        "id": {"type": "string", "pattern": ID_PATTERN},
        "type": {"type": "string", "enum": list(CRITERION_TYPES)},
        "text": _text(500),
        "presence": {"type": "string", "enum": ["present", "absent"]},
        "status": {
            "type": "string",
            "enum": ["active", "any"],
            "description": "Conditions: 'active' counts only clinicalStatus active, recurrence "
            "or relapse; 'any' (default) also counts inactive, remission and resolved.",
        },
        "codes": {"type": "array", "minItems": 1, "maxItems": 50, "items": _CODE_REF},
        "terms": {"type": "array", "minItems": 1, "maxItems": 20, "items": _text(100)},
        "ingredients": {"type": "array", "minItems": 1, "maxItems": 50, "items": _text(100)},
        "classes": {
            "type": "array",
            "minItems": 1,
            "maxItems": len(MEDICATION_CLASSES),
            "items": {"type": "string", "enum": sorted(MEDICATION_CLASSES)},
        },
        "rxnorm_codes": {
            "type": "array",
            "minItems": 1,
            "maxItems": 50,
            "items": {"type": "string", "pattern": r"^[0-9]{1,10}$"},
        },
        "operator": {"type": "string", "enum": list(OPERATORS)},
        "value": {"type": "number"},
        "low": {"type": "number"},
        "high": {"type": "number"},
        "unit": {"type": "string", "minLength": 1, "maxLength": 40},
        "relative_to": {
            "type": "string",
            "enum": ["uln"],
            "description": "Compare the value as a multiple of the observation's reference-range "
            "upper limit (e.g. ALT <= 3 x ULN); no unit is given.",
        },
        "within_days": {"type": "integer", "minimum": 1, "maximum": 36500},
    },
    "required": ["id", "type", "text"],
    "additionalProperties": False,
}

ELIGIBILITY_MODULE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "ClinicalTrials.gov API v2 protocolSection.eligibilityModule, verbatim. sex, "
        "minimumAge and maximumAge become structured criteria; the other fields are context."
    ),
    "properties": {
        "sex": {"type": "string", "enum": ["FEMALE", "MALE", "ALL"]},
        "genderBased": {"type": "boolean"},
        "genderDescription": {"type": "string", "maxLength": 5000},
        "minimumAge": {"type": "string", "pattern": NORMALIZED_TIME_PATTERN},
        "maximumAge": {"type": "string", "pattern": NORMALIZED_TIME_PATTERN},
        "healthyVolunteers": {"type": "boolean"},
        "stdAges": {
            "type": "array",
            "maxItems": 3,
            "items": {"type": "string", "enum": ["CHILD", "ADULT", "OLDER_ADULT"]},
        },
        "eligibilityCriteria": {"type": "string", "maxLength": 20000},
        "studyPopulation": {"type": "string", "maxLength": 5000},
        "samplingMethod": {
            "type": "string",
            "enum": ["PROBABILITY_SAMPLE", "NON_PROBABILITY_SAMPLE"],
        },
    },
    "additionalProperties": False,
}

TRIAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": "A structured trial definition (medagent trial-criteria format 1.0).",
    "properties": {
        "schema_version": {"type": "string", "enum": [SCHEMA_VERSION]},
        "trial_id": {"type": "string", "pattern": ID_PATTERN},
        "version": {
            "type": "string",
            "pattern": VERSION_PATTERN,
            "description": "Version of this criteria encoding, e.g. a protocol amendment date.",
        },
        "title": _text(300),
        "eligibilityModule": ELIGIBILITY_MODULE_SCHEMA,
        "inclusion": {
            "type": "array",
            "maxItems": MAX_CRITERIA_PER_SECTION,
            "items": CRITERION_SCHEMA,
        },
        "exclusion": {
            "type": "array",
            "maxItems": MAX_CRITERIA_PER_SECTION,
            "items": CRITERION_SCHEMA,
        },
    },
    "required": ["schema_version", "trial_id", "version", "title"],
    "additionalProperties": False,
}

BUNDLE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": "FHIR R4 Bundle with one patient's resources.",
    "properties": {
        "resourceType": {"type": "string", "const": "Bundle"},
        "entry": {
            "type": "array",
            "maxItems": MAX_BUNDLE_ENTRIES,
            "items": {"type": "object", "properties": {"resource": {"type": "object"}}},
        },
    },
    "required": ["resourceType"],
}

SCREEN_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "bundle": BUNDLE_SCHEMA,
        "trials": {
            "type": "array",
            "minItems": 1,
            "maxItems": MAX_TRIALS,
            "items": TRIAL_SCHEMA,
            "description": "Structured trial definitions to pre-screen against.",
        },
        "patient_context": {
            "type": "object",
            "description": (
                "Optional caller-asserted status, used instead of the bundle's pregnancy or "
                "breastfeeding status observations. Direct identifiers are not accepted."
            ),
            "properties": {
                "pregnant": {"type": "boolean"},
                "breastfeeding": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
        "as_of": {
            "type": "string",
            "pattern": DATE_PATTERN,
            "description": "Evaluation date (YYYY-MM-DD) for age and recency windows; default "
            "today (UTC).",
        },
        "patient_ref": {
            "type": "string",
            "minLength": 1,
            "maxLength": 200,
            "description": (
                "Optional caller reference used only to link audit records. It is HMAC-SHA256 "
                "hashed with PII_HASH_SALT and is never echoed back."
            ),
        },
    },
    "required": ["bundle", "trials"],
    "additionalProperties": False,
}

_EVIDENCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": "Pointer to the de-identified fact behind a decision (never an identifier).",
    "properties": {
        "resource_type": {"type": "string"},
        "system": _NULLABLE_STRING,
        "code": _NULLABLE_STRING,
        "display": _NULLABLE_STRING,
        "value": {
            "anyOf": [
                {"type": "number"},
                {"type": "string"},
                {"type": "boolean"},
                {"type": "null"},
            ]
        },
        "comparator": _NULLABLE_STRING,
        "unit": _NULLABLE_STRING,
        "date": _NULLABLE_STRING,
    },
    "required": [
        "resource_type",
        "system",
        "code",
        "display",
        "value",
        "comparator",
        "unit",
        "date",
    ],
    "additionalProperties": False,
}

_CRITERION_RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "criterion_id": {"type": "string"},
        "section": {"type": "string", "enum": list(SECTIONS)},
        "type": {"type": "string", "enum": [*CRITERION_TYPES, *DERIVED_CRITERION_TYPES]},
        "text": {"type": "string"},
        "status": {"type": "string", "enum": list(CRITERION_STATUSES)},
        "rationale": {"type": "string"},
        "evidence": {"type": "array", "items": _EVIDENCE_SCHEMA},
    },
    "required": ["criterion_id", "section", "type", "text", "status", "rationale", "evidence"],
    "additionalProperties": False,
}

_COUNT: dict[str, Any] = {"type": "integer", "minimum": 0}
_COUNT_NAMES: tuple[str, ...] = (
    *CRITERION_STATUSES,
    "favourable",
    "blocking",
    "open",
    "total",
)

_TRIAL_RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "rank": {"type": "integer", "minimum": 1},
        "trial_id": {"type": "string"},
        "trial_version": {"type": "string"},
        "title": {"type": "string"},
        "status": {"type": "string", "enum": list(TRIAL_STATUSES)},
        "score": {"type": "number", "minimum": 0, "maximum": 1},
        "rank_reason": {"type": "string"},
        "counts": {
            "type": "object",
            "properties": dict.fromkeys(_COUNT_NAMES, _COUNT),
            "required": list(_COUNT_NAMES),
            "additionalProperties": False,
        },
        "blocking_criteria": _STRING_LIST,
        "open_criteria": _STRING_LIST,
        "eligibility_module": {
            "type": "object",
            "properties": {
                "sex": _NULLABLE_STRING,
                "minimumAge": _NULLABLE_STRING,
                "maximumAge": _NULLABLE_STRING,
                "healthyVolunteers": {"anyOf": [{"type": "boolean"}, {"type": "null"}]},
                "genderBased": {"anyOf": [{"type": "boolean"}, {"type": "null"}]},
                "stdAges": _STRING_LIST,
                "source_criteria_text_supplied": {"type": "boolean"},
            },
            "required": [
                "sex",
                "minimumAge",
                "maximumAge",
                "healthyVolunteers",
                "genderBased",
                "stdAges",
                "source_criteria_text_supplied",
            ],
            "additionalProperties": False,
        },
        "criteria": {"type": "array", "items": _CRITERION_RESULT_SCHEMA},
    },
    "required": [
        "rank",
        "trial_id",
        "trial_version",
        "title",
        "status",
        "score",
        "rank_reason",
        "counts",
        "blocking_criteria",
        "open_criteria",
        "eligibility_module",
        "criteria",
    ],
    "additionalProperties": False,
}

SCREEN_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "as_of": {"type": "string", "pattern": DATE_PATTERN},
        "inputs_hash": {"type": "string", "minLength": 64, "maxLength": 64},
        "patient_id_hash": {"type": "string", "minLength": 64, "maxLength": 64},
        "patient_ref_hash": _NULLABLE_STRING,
        "patient_summary": {
            "type": "object",
            "properties": {
                "age_years": {
                    "anyOf": [
                        {
                            "type": "object",
                            "properties": {"min": _COUNT, "max": _COUNT},
                            "required": ["min", "max"],
                            "additionalProperties": False,
                        },
                        {"type": "null"},
                    ]
                },
                "sex": _NULLABLE_STRING,
                "conditions": _COUNT,
                "current_medications": _COUNT,
                "observations": _COUNT,
            },
            "required": ["age_years", "sex", "conditions", "current_medications", "observations"],
            "additionalProperties": False,
        },
        "trial_count": _COUNT,
        "status_counts": {
            "type": "object",
            "properties": dict.fromkeys(TRIAL_STATUSES, _COUNT),
            "required": list(TRIAL_STATUSES),
            "additionalProperties": False,
        },
        "trials": {"type": "array", "items": _TRIAL_RESULT_SCHEMA},
        "data_notes": _STRING_LIST,
        "network_used": {"type": "boolean", "const": False},
        "coverage_note": {"type": "string"},
        "disclaimer": {"type": "string", "const": MANDATORY_DISCLAIMER},
    },
    "required": [
        "as_of",
        "inputs_hash",
        "patient_id_hash",
        "patient_ref_hash",
        "patient_summary",
        "trial_count",
        "status_counts",
        "trials",
        "data_notes",
        "network_used",
        "coverage_note",
        "disclaimer",
    ],
    "additionalProperties": False,
}

# The HTTP response adds the server-generated id that links it to its audit rows.
HTTP_OUTPUT_SCHEMA: dict[str, Any] = {
    **SCREEN_OUTPUT_SCHEMA,
    "properties": {
        "screening_id": {"type": "string", "minLength": 36, "maxLength": 36},
        **SCREEN_OUTPUT_SCHEMA["properties"],
    },
    "required": ["screening_id", *SCREEN_OUTPUT_SCHEMA["required"]],
}
