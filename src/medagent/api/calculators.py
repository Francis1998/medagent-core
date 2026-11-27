"""``/calculators``: deterministic clinical calculators over HTTP (RESEARCH USE ONLY).

``GET /calculators`` lists the calculators with their input specs,
``GET /calculators/{calculator_id}`` returns one full specification (units,
conversions, ranges, JSON Schema, bands, citations, limitations) and
``POST /calculators/{calculator_id}`` computes it from ``{"inputs": {...}}``
with the same code as the MCP tool ``run_calculator``. Malformed JSON is a 400,
an unknown id a 404, a body over 64 KiB a 413 and missing, malformed or
out-of-range inputs a 422; error responses and logs never echo caller values.
Never a treatment recommendation.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from medagent.calculators import (
    CATEGORIES,
    CalculatorInputError,
    UnknownCalculatorError,
    catalogue,
    describe_calculator,
    get_calculator,
    run_calculator,
)
from medagent.calculators.schema import LIST_OUTPUT_SCHEMA, RUN_OUTPUT_SCHEMA
from medagent.llm.validator import MedicalOutputValidationError, MedicalOutputValidator
from medagent.logging_config import get_logger

logger = get_logger(__name__)

CALCULATORS_PATH = "/calculators"
MAX_REQUEST_BYTES = 64 * 1024
WITHHELD_DETAIL = (
    "Result withheld: it matched prohibited prescription language (SAFETY.md §3.3). "
    "Escalate to a licensed clinician."
)
_OUTPUT_GUARD = MedicalOutputValidator()
_RUN_REQUEST_SCHEMA = {
    "type": "object",
    "properties": {
        "inputs": {
            "type": "object",
            "description": "Raw values keyed by input name (see GET /calculators/{calculator_id}).",
        }
    },
    "required": ["inputs"],
    "additionalProperties": False,
}

router = APIRouter(prefix=CALCULATORS_PATH, tags=["Clinical calculators (research use only)"])


def _reject_json_constant(name: str) -> Any:
    raise ValueError(f"Non-standard JSON constant: {name}")


async def _read_json(request: Request) -> Any:
    """Read and decode a JSON body of at most ``MAX_REQUEST_BYTES``."""
    declared = request.headers.get("content-length", "")
    too_large = HTTPException(
        status_code=413, detail=f"Request body exceeds {MAX_REQUEST_BYTES} bytes."
    )
    if declared.isdigit() and int(declared) > MAX_REQUEST_BYTES:
        raise too_large
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_REQUEST_BYTES:
            raise too_large
    try:
        return json.loads(bytes(body), parse_constant=_reject_json_constant)
    except (ValueError, RecursionError):
        logger.warning("calculator_rejected", reason="invalid_json")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The request body is not valid JSON.",
        ) from None


def _strings(value: Any) -> list[str]:
    """Every string value and object key nested in ``value``."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for key, item in value.items() for text in (str(key), *_strings(item))]
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    return []


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail=str(UnknownCalculatorError()))


@router.get(
    "",
    summary="List the clinical calculators with their input specs (research use only)",
    responses={
        200: {
            "description": "Calculator ids, names, versions, input specs, bands and citations.",
            "content": {"application/json": {"schema": LIST_OUTPUT_SCHEMA}},
        },
        422: {"description": "Unknown category."},
    },
)
async def list_calculators(
    category: str | None = Query(None, description=f"One of: {', '.join(CATEGORIES)}."),
) -> JSONResponse:
    """List every registered calculator, optionally only one category."""
    if category is not None and category not in CATEGORIES:
        raise HTTPException(
            status_code=422, detail=f"category must be one of {', '.join(CATEGORIES)}."
        )
    return JSONResponse(catalogue(category))


@router.get(
    "/{calculator_id}",
    summary="Full specification of one calculator (research use only)",
    responses={404: {"description": "Unknown calculator id."}},
)
async def get_calculator_spec(calculator_id: str) -> JSONResponse:
    """Inputs with units, conversions and ranges, JSON Schema, bands, citations, limitations."""
    try:
        return JSONResponse(describe_calculator(calculator_id))
    except UnknownCalculatorError:
        raise _not_found() from None


@router.post(
    "/{calculator_id}",
    summary="Compute one calculator from raw values with units (research use only)",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": _RUN_REQUEST_SCHEMA}},
        }
    },
    responses={
        200: {
            "description": "Score, derived criteria, interpretation band, citations, limitations.",
            "content": {"application/json": {"schema": RUN_OUTPUT_SCHEMA}},
        },
        400: {"description": "The body is not valid JSON."},
        404: {"description": "Unknown calculator id."},
        413: {"description": "The body exceeds 64 KiB."},
        422: {"description": "Missing, malformed or out-of-range inputs."},
    },
)
async def compute_calculator(calculator_id: str, request: Request) -> JSONResponse:
    """Validate the inputs, derive every criterion and return the cited result.

    Missing inputs are errors, never assumed absent. The result describes risk
    strata from the cited publications and is never a treatment recommendation.
    """
    try:
        get_calculator(calculator_id)
    except UnknownCalculatorError:
        raise _not_found() from None
    body = await _read_json(request)
    if not isinstance(body, dict) or set(body) != {"inputs"}:
        logger.warning("calculator_rejected", calculator=calculator_id, reason="bad_envelope")
        raise HTTPException(
            status_code=422,
            detail='The request body must be a JSON object of the form {"inputs": {...}}.',
        )
    try:
        result = run_calculator(calculator_id, body["inputs"])
    except CalculatorInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    try:
        for text in _strings(result):
            _OUTPUT_GUARD.check_prohibited_language(text)
    except MedicalOutputValidationError:
        logger.error("calculator_withheld", calculator=calculator_id)
        raise HTTPException(status_code=422, detail=WITHHELD_DETAIL) from None
    return JSONResponse(result, headers={"Cache-Control": "no-store"})
