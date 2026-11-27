"""JSON Schemas for the calculator MCP tools and the ``/calculators`` OpenAPI docs."""

from __future__ import annotations

from typing import Any

from medagent.calculators.registry import CALCULATORS_BY_ID, CATEGORIES
from medagent.safety.disclaimer import MANDATORY_DISCLAIMER

_STRING = {"type": "string"}
_NULLABLE_STRING = {"type": ["string", "null"]}
_NULLABLE_NUMBER = {"type": ["number", "null"]}
_STRINGS = {"type": "array", "items": _STRING}
_DISCLAIMER = {"type": "string", "const": MANDATORY_DISCLAIMER}
CALCULATOR_IDS: list[str] = sorted(CALCULATORS_BY_ID)


def _object(properties: dict[str, Any], *, required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties) if required is None else required,
        "additionalProperties": False,
    }


_CITATION = _object(
    {
        "reference": _STRING,
        "doi": _NULLABLE_STRING,
        "pmid": _NULLABLE_STRING,
        "url": _NULLABLE_STRING,
    }
)
_COMPACT_INPUT = _object(
    {
        "name": _STRING,
        "type": {"type": "string", "enum": ["number", "integer", "boolean", "choice"]},
        "required": {"type": "boolean"},
        "unit": _NULLABLE_STRING,
        "accepted_units": _STRINGS,
        "unit_required": {"type": "boolean"},
        "choices": _STRINGS,
        "minimum": _NULLABLE_NUMBER,
        "maximum": _NULLABLE_NUMBER,
        "default": {},
        "description": _STRING,
    }
)
_SUMMARY = _object(
    {
        "id": {"type": "string", "enum": CALCULATOR_IDS},
        "name": _STRING,
        "version": _STRING,
        "category": {"type": "string", "enum": list(CATEGORIES)},
        "purpose": _STRING,
        "score_unit": _STRING,
        "score_range": _STRING,
        "wraps": _NULLABLE_STRING,
        "inputs": {"type": "array", "items": _COMPACT_INPUT},
        "bands": {"type": "array", "items": _object({"band": _STRING, "range": _STRING})},
        "citation": _CITATION,
    }
)

LIST_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": list(CATEGORIES)},
        "calculator_id": {"type": "string", "enum": CALCULATOR_IDS},
    },
    "additionalProperties": False,
}
LIST_OUTPUT_SCHEMA: dict[str, Any] = _object(
    {
        "count": {"type": "integer", "minimum": 0},
        "categories": {"type": "array", "items": {"type": "string", "enum": list(CATEGORIES)}},
        "calculators": {"type": "array", "items": _SUMMARY},
        "disclaimer": _DISCLAIMER,
    }
)

RUN_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "calculator_id": {
            "type": "string",
            "enum": CALCULATOR_IDS,
            "description": "Calculator id from list_calculators.",
        },
        "inputs": {
            "type": "object",
            "description": (
                "Raw values keyed by input name. Quantities with alternative units take "
                '{"value": <number>, "unit": "<unit>"}; booleans are true/false and are never '
                "assumed absent when missing."
            ),
        },
    },
    "required": ["calculator_id", "inputs"],
    "additionalProperties": False,
}
_COMPONENT = _object(
    {
        "criterion": _STRING,
        "label": _STRING,
        "points": _NULLABLE_NUMBER,
        "rule": _STRING,
        "inputs": _STRINGS,
        "value": {"type": "number"},
    },
    required=["criterion", "label", "points", "rule", "inputs"],
)
RUN_OUTPUT_SCHEMA: dict[str, Any] = _object(
    {
        "calculator": _object(
            {"id": {"type": "string", "enum": CALCULATOR_IDS}, "name": _STRING, "version": _STRING}
        ),
        "score": {"type": "number"},
        "score_unit": _STRING,
        "score_range": _STRING,
        "interpretation": _object(
            {
                "band": _STRING,
                "label": _STRING,
                "range": _STRING,
                "description": _STRING,
                "severity": {"type": "string", "enum": ["LOW", "MODERATE", "HIGH", "CRITICAL"]},
            }
        ),
        "components": {"type": "array", "items": _COMPONENT},
        "details": {"type": "object"},
        "inputs": {"type": "object"},
        "citations": {"type": "array", "items": _CITATION},
        "limitations": _STRINGS,
        "disclaimer": _DISCLAIMER,
    }
)
