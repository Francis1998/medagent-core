"""HL7 CDS Hooks 2.0 HTTP surface: ``/cds-services`` discovery, service calls and feedback.

* ``GET  /cds-services`` lists the services (``order-sign``, ``order-select``).
* ``POST /cds-services/{id}`` screens the orders in the request and returns cards.
* ``POST /cds-services/{id}/feedback`` records card outcomes in the audit log.

Service calls are audited in a tracked background task, feedback synchronously;
both store hashes, ids and codes only. Error responses and logs never contain
caller-supplied text. CORS on these paths is opt-in
(``MEDAGENT_CDS_HOOKS_CORS_ORIGINS``). JWT client authentication is NOT
implemented: deploy behind an authenticating gateway. RESEARCH USE ONLY.
"""

from __future__ import annotations

import asyncio
import functools
import json
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from medagent.agent.audit import persist_cds_hooks_events, safe_error_fields
from medagent.cds_hooks import (
    SERVICES_BY_ID,
    CdsHooksRequestError,
    CdsService,
    discovery_document,
    evaluate_hook,
    parse_feedback,
)
from medagent.config import settings
from medagent.logging_config import get_logger

logger = get_logger(__name__)

CDS_HOOKS_PATH = "/cds-services"
MAX_REQUEST_BYTES = 8 * 1024 * 1024
AUDIT_DRAIN_TIMEOUT_SECONDS = 10.0

# Strong references to in-flight service-call audit writes (the event loop only
# keeps weak references, so an untracked task can be garbage collected).
_pending_audit_writes: set[asyncio.Task[None]] = set()

_JSON_BODY = {
    "requestBody": {
        "required": True,
        "content": {"application/json": {"schema": {"type": "object"}}},
    }
}

router = APIRouter(prefix=CDS_HOOKS_PATH, tags=["CDS Hooks"])


def is_cds_hooks_path(path: str) -> bool:
    """True for ``/cds-services`` and every path below it."""
    return path == CDS_HOOKS_PATH or path.startswith(CDS_HOOKS_PATH + "/")


def _route_path(scope: Scope) -> str:
    """The request path relative to the application's ``root_path``."""
    path = str(scope.get("path", ""))
    root_path = str(scope.get("root_path", ""))
    if root_path and path.startswith(root_path):
        return path[len(root_path) :] or "/"
    return path


class CdsHooksCORSMiddleware:
    """App-wide CORS policy, except on ``/cds-services``, where CORS is opt-in.

    The public CDS Hooks sandbox calls services from a browser, so origins listed
    in ``MEDAGENT_CDS_HOOKS_CORS_ORIGINS`` may call ``/cds-services``; by default
    those paths send no CORS headers at all. Every other path keeps the policy
    passed as keyword arguments (Starlette ``CORSMiddleware`` options).
    """

    def __init__(self, app: ASGIApp, /, **default_policy: Any) -> None:
        self._app = app
        self._default = CORSMiddleware(app, **default_policy)
        self._allow_listed: dict[tuple[str, ...], ASGIApp] = {}

    def _cds_app(self, origins: tuple[str, ...]) -> ASGIApp:
        if not origins:
            return self._app
        handler = self._allow_listed.get(origins)
        if handler is None:
            handler = CORSMiddleware(
                self._app,
                allow_origins=list(origins),
                allow_methods=["GET", "POST"],
                allow_headers=["Authorization", "Content-Type"],
                allow_credentials=False,
                max_age=600,
            )
            self._allow_listed[origins] = handler
        return handler

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and is_cds_hooks_path(_route_path(scope)):
            await self._cds_app(settings.cds_hooks_cors_origin_list)(scope, receive, send)
            return
        await self._default(scope, receive, send)


def _reject_json_constant(name: str) -> Any:
    raise ValueError(f"Non-standard JSON constant: {name}")


async def _read_json(request: Request) -> Any:
    """Read and decode a JSON body of at most ``MAX_REQUEST_BYTES``."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_REQUEST_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Request body exceeds {MAX_REQUEST_BYTES} bytes.",
        )
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_REQUEST_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Request body exceeds {MAX_REQUEST_BYTES} bytes.",
            )
    try:
        return json.loads(bytes(body), parse_constant=_reject_json_constant)
    except (ValueError, RecursionError):
        logger.warning("cds_hooks_invalid_request", reason="invalid_json")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The request body is not valid JSON.",
        ) from None


def _service(service_id: str) -> CdsService:
    """Return the addressed service; the caller-supplied id is never logged or echoed."""
    service = SERVICES_BY_ID.get(service_id)
    if service is None:
        logger.warning("cds_hooks_unknown_service")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown CDS service.")
    return service


def _bad_request(service: CdsService, error: CdsHooksRequestError) -> HTTPException:
    logger.warning("cds_hooks_invalid_request", service=service.id, reason=error.reason)
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error.message)


def _on_audit_write_done(task: asyncio.Task[None], *, service_id: str) -> None:
    """Release a finished audit write; log failures with class names and codes only."""
    _pending_audit_writes.discard(task)
    if task.cancelled():
        logger.error("cds_hooks_audit_cancelled", service=service_id)
        return
    exc = task.exception()
    if exc is not None:
        logger.error("cds_hooks_audit_persist_failed", service=service_id, **safe_error_fields(exc))


def schedule_audit_write(
    events: Sequence[Mapping[str, Any]], *, service_id: str
) -> asyncio.Task[None]:
    """Persist service-call audit events in a tracked background task.

    Args:
        events: De-identified events built by :func:`medagent.cds_hooks.evaluate_hook`.
        service_id: Server-defined service id, used in failure logs.

    Returns:
        The scheduled task; it stays referenced until it finishes.
    """
    task = asyncio.create_task(persist_cds_hooks_events(list(events)))
    _pending_audit_writes.add(task)
    task.add_done_callback(functools.partial(_on_audit_write_done, service_id=service_id))
    return task


async def drain_audit_writes(timeout: float = AUDIT_DRAIN_TIMEOUT_SECONDS) -> int:
    """Wait for in-flight service-call audit writes on the running loop.

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
            "cds_hooks_audit_drain_timeout", pending=len(still_pending), timeout_seconds=timeout
        )
    return len(still_pending)


@router.get("", summary="CDS Hooks discovery")
async def discovery() -> dict[str, Any]:
    """List the CDS Services (CDS Hooks 2.0 discovery endpoint)."""
    return discovery_document()


@router.post("/{service_id}", summary="Call a CDS Service", openapi_extra=_JSON_BODY)
async def call_service(service_id: str, request: Request) -> JSONResponse:
    """Screen the medication orders of a CDS Hooks call and return cards.

    Returns ``{"cards": []}`` when there is nothing to report. Unknown services
    are 404; invalid requests, including resources for another patient, are 400.
    """
    service = _service(service_id)
    started = time.perf_counter()
    body = await _read_json(request)
    try:
        result = await run_in_threadpool(evaluate_hook, service, body)
    except CdsHooksRequestError as exc:
        raise _bad_request(service, exc) from None
    schedule_audit_write(result.audit_events, service_id=service.id)
    logger.info(
        "cds_hooks_service_call",
        service=service.id,
        hook=service.hook,
        cards=len(result.cards),
        findings=result.finding_count,
        indicator=result.highest_indicator,
        prefetch_gaps=list(result.prefetch_gaps),
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    return JSONResponse({"cards": result.cards}, headers={"Cache-Control": "no-store"})


@router.post("/{service_id}/feedback", summary="Report card outcomes", openapi_extra=_JSON_BODY)
async def feedback(service_id: str, request: Request) -> JSONResponse:
    """Record CDS Hooks 2.0 feedback (card uuid, outcome, override reason code).

    ``overrideReason.userComment`` and timestamps are validated but never stored
    or logged. Returns 503 when the audit log cannot record the feedback.
    """
    service = _service(service_id)
    body = await _read_json(request)
    try:
        items = parse_feedback(body)
    except CdsHooksRequestError as exc:
        raise _bad_request(service, exc) from None
    events = [
        {
            "event": "feedback",
            "service_id": service.id,
            "hook": service.hook,
            "card_uuid": item.card_uuid,
            "outcome": item.outcome,
            "override_reason_code": item.override_reason_code,
        }
        for item in items
    ]
    try:
        await persist_cds_hooks_events(events)
    except Exception as exc:
        # Never log str(exc): database errors can embed bound parameters.
        logger.error(
            "cds_hooks_feedback_persist_failed", service=service.id, **safe_error_fields(exc)
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Feedback could not be recorded; retry later.",
        ) from None
    outcomes = Counter(item.outcome for item in items)
    logger.info(
        "cds_hooks_feedback_recorded",
        service=service.id,
        accepted=outcomes.get("accepted", 0),
        overridden=outcomes.get("overridden", 0),
    )
    return JSONResponse({"recorded": len(items)})
