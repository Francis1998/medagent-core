"""``POST /trials/eligibility``: research-only clinical-trial eligibility pre-screening.

Screens one patient's FHIR R4 Bundle against 1-20 structured trial definitions
with the deterministic, offline evaluator in :mod:`medagent.trials` (the same
code as the MCP tool ``screen_trial_eligibility``) and returns ranked trials
with criterion-level decisions and evidence pointers. Malformed JSON is a 400,
an invalid request or rejected FHIR data a 422, and a body over 8 MiB a 413;
error responses and logs never contain caller-supplied text. Each screening is
audited in a tracked background task with hashes, ids and counts only.
RESEARCH USE ONLY: never an eligibility determination or an enrollment.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from medagent.agent.audit import safe_error_fields
from medagent.llm.validator import MedicalOutputValidationError, MedicalOutputValidator
from medagent.logging_config import get_logger
from medagent.trials.audit import persist_trial_screening_events
from medagent.trials.criteria import TrialInputError
from medagent.trials.schema import HTTP_OUTPUT_SCHEMA, SCREEN_INPUT_SCHEMA
from medagent.trials.screening import screen_trials_request

logger = get_logger(__name__)

TRIALS_PATH = "/trials"
MAX_REQUEST_BYTES = 8 * 1024 * 1024
AUDIT_DRAIN_TIMEOUT_SECONDS = 10.0
WITHHELD_DETAIL = (
    "Result withheld: it matched prohibited prescription language (SAFETY.md §3.3). "
    "Escalate to a licensed clinician."
)

# Strong references to in-flight audit writes (the event loop keeps weak ones only).
_pending_audit_writes: set[asyncio.Task[None]] = set()
_OUTPUT_GUARD = MedicalOutputValidator()

router = APIRouter(prefix=TRIALS_PATH, tags=["Clinical trials (research use only)"])


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
        logger.warning("trial_screening_rejected", reason="invalid_json")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The request body is not valid JSON.",
        ) from None


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


def _on_audit_write_done(task: asyncio.Task[None]) -> None:
    """Release a finished audit write; log failures with class names and codes only."""
    _pending_audit_writes.discard(task)
    if task.cancelled():
        logger.error("trial_screening_audit_cancelled")
        return
    exc = task.exception()
    if exc is not None:
        logger.error("trial_screening_audit_persist_failed", **safe_error_fields(exc))


def schedule_audit_write(events: Sequence[Mapping[str, Any]]) -> asyncio.Task[None]:
    """Persist screening audit rows in a tracked background task.

    Args:
        events: De-identified rows from ``TrialScreening.audit_events``.

    Returns:
        The scheduled task; it stays referenced until it finishes.
    """
    task = asyncio.create_task(persist_trial_screening_events(list(events)))
    _pending_audit_writes.add(task)
    task.add_done_callback(_on_audit_write_done)
    return task


async def drain_audit_writes(timeout: float = AUDIT_DRAIN_TIMEOUT_SECONDS) -> int:
    """Wait for in-flight screening audit writes on the running loop.

    Args:
        timeout: Maximum seconds to wait.

    Returns:
        Number of writes still pending when the timeout expired.
    """
    loop = asyncio.get_running_loop()
    pending = {task for task in _pending_audit_writes if task.get_loop() is loop}
    if not pending:
        return 0
    _, still_pending = await asyncio.wait(pending, timeout=timeout)
    if still_pending:
        logger.error(
            "trial_screening_audit_drain_timeout",
            pending=len(still_pending),
            timeout_seconds=timeout,
        )
    return len(still_pending)


@router.post(
    "/eligibility",
    summary="Pre-screen one patient against structured trial criteria (research use only)",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": SCREEN_INPUT_SCHEMA}},
        }
    },
    responses={
        200: {
            "description": "Ranked trials with criterion-level decisions and evidence pointers.",
            "content": {"application/json": {"schema": HTTP_OUTPUT_SCHEMA}},
        },
        400: {"description": "The body is not valid JSON."},
        413: {"description": "The body exceeds 8 MiB."},
        422: {"description": "Invalid arguments, trial definition or FHIR data."},
    },
)
async def trial_eligibility(request: Request) -> JSONResponse:
    """Pre-screen one FHIR patient against structured trial definitions.

    Every criterion is ``met``, ``not_met``, ``insufficient_data`` or
    ``requires_human_review``; trials are ranked ``potentially_eligible`` >
    ``needs_review`` > ``likely_ineligible``. This is never an eligibility
    determination, an enrollment or a referral.
    """
    started = time.perf_counter()
    body = await _read_json(request)
    if not isinstance(body, dict):
        logger.warning("trial_screening_rejected", reason="not_an_object")
        raise HTTPException(
            status_code=422,
            detail="The request body must be a JSON object.",
        )
    try:
        screening = await run_in_threadpool(screen_trials_request, body, path="body")
    except TrialInputError as exc:
        logger.warning("trial_screening_rejected", reason=exc.reason)
        raise HTTPException(status_code=422, detail=str(exc)) from None
    screening_id = str(uuid.uuid4())
    result = {"screening_id": screening_id, **screening.structured()}
    try:
        for text in _strings(result):
            _OUTPUT_GUARD.check_prohibited_language(text)
    except MedicalOutputValidationError:
        logger.error("trial_screening_withheld")
        raise HTTPException(status_code=422, detail=WITHHELD_DETAIL) from None
    schedule_audit_write(screening.audit_events(screening_id))
    logger.info(
        "trial_screening",
        trials=len(screening.ranked),
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
        **screening.status_counts,
    )
    return JSONResponse(result, headers={"Cache-Control": "no-store"})
