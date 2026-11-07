"""Validation of CDS Hooks 2.0 service calls and feedback.

Error messages name specification fields and server-defined values only; they
never echo caller-supplied text, identifiers or clinical content.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from medagent.cds_hooks.services import (
    ORDER_SELECT,
    OVERRIDE_REASON_CODES,
    OVERRIDE_REASON_SYSTEM,
    CdsService,
)

MAX_BUNDLE_ENTRIES = 5000
MAX_SELECTIONS = 500
MAX_FEEDBACK_ITEMS = 100
_MAX_STRING = 256
_FHIR_ID = re.compile(r"[A-Za-z0-9\-.]{1,64}")
_CARD_UUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_TIMESTAMP = re.compile(
    r"(?P<date>\d{4}-\d{2}-\d{2})[Tt ](?P<time>\d{2}:\d{2}:\d{2})(?:\.\d{1,9})?"
    r"(?:[Zz]|[+-](?:[01]\d|2[0-3]):[0-5]\d)?"
)
OUTCOMES: tuple[str, ...] = ("accepted", "overridden")
UNRECOGNIZED_REASON = "unrecognized"


class CdsHooksRequestError(ValueError):
    """A request that violates CDS Hooks 2.0 or this service's limits (HTTP 400).

    Attributes:
        reason: Short server-defined slug that is safe to log.
        message: Client-facing explanation; never contains caller-supplied text.
    """

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass(frozen=True)
class HookRequest:
    """A validated ``order-sign`` / ``order-select`` service call."""

    hook: str
    hook_instance: str
    patient_id: str
    user_id: str
    draft_entries: tuple[dict[str, Any], ...]
    selections: tuple[str, ...]
    prefetch: Mapping[str, Any]


@dataclass(frozen=True)
class FeedbackItem:
    """One validated feedback entry; free-text comments are never kept."""

    card_uuid: str
    outcome: str
    override_reason_code: str | None


def _bounded_string(value: Any, name: str, reason: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > _MAX_STRING:
        raise CdsHooksRequestError(
            reason,
            f"{name} is required and must be a non-empty string of at most "
            f"{_MAX_STRING} characters.",
        )
    return value


def _bundle_entries(value: Any, name: str) -> tuple[dict[str, Any], ...]:
    """Return the entries of a FHIR Bundle that carry a resource object."""
    if not isinstance(value, dict) or value.get("resourceType") != "Bundle":
        raise CdsHooksRequestError(
            "invalid_draft_orders", f"{name} is required and must be a FHIR Bundle."
        )
    entries = value.get("entry", [])
    if not isinstance(entries, list):
        raise CdsHooksRequestError("invalid_draft_orders", f"{name}.entry must be an array.")
    if len(entries) > MAX_BUNDLE_ENTRIES:
        raise CdsHooksRequestError(
            "too_many_entries", f"{name} must have at most {MAX_BUNDLE_ENTRIES} entries."
        )
    kept: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise CdsHooksRequestError(
                "invalid_draft_orders", f"{name}.entry[{index}] must be an object."
            )
        resource = entry.get("resource")
        if resource is None:
            continue
        if not isinstance(resource, dict):
            raise CdsHooksRequestError(
                "invalid_draft_orders", f"{name}.entry[{index}].resource must be an object."
            )
        kept.append(entry)
    return tuple(kept)


def parse_hook_request(body: Any, service: CdsService) -> HookRequest:
    """Validate a CDS Hooks service call for ``service``.

    Args:
        body: Decoded JSON request body.
        service: The CDS Service addressed by the request path.

    Returns:
        The validated request.

    Raises:
        CdsHooksRequestError: When the body is not a valid call for this service.
    """
    if not isinstance(body, dict):
        raise CdsHooksRequestError("invalid_body", "The request body must be a JSON object.")
    hook = body.get("hook")
    if not isinstance(hook, str):
        raise CdsHooksRequestError("invalid_hook", "hook is required and must be a string.")
    if hook != service.hook:
        raise CdsHooksRequestError(
            "hook_mismatch",
            f"hook does not match this service, which is invoked on '{service.hook}'.",
        )
    hook_instance = _bounded_string(body.get("hookInstance"), "hookInstance", "invalid_hook")

    context = body.get("context")
    if not isinstance(context, dict):
        raise CdsHooksRequestError("invalid_context", "context is required and must be an object.")
    patient_id = context.get("patientId")
    if not isinstance(patient_id, str) or not _FHIR_ID.fullmatch(patient_id):
        raise CdsHooksRequestError(
            "invalid_context",
            "context.patientId is required and must be a FHIR id "
            "(1-64 letters, digits, '-' or '.').",
        )
    user_id = _bounded_string(context.get("userId"), "context.userId", "invalid_context")
    encounter_id = context.get("encounterId")
    if encounter_id is not None:
        _bounded_string(encounter_id, "context.encounterId", "invalid_context")
    draft_entries = _bundle_entries(context.get("draftOrders"), "context.draftOrders")

    selections: tuple[str, ...] = ()
    if service.hook == ORDER_SELECT:
        raw = context.get("selections")
        if (
            not isinstance(raw, list)
            or not 1 <= len(raw) <= MAX_SELECTIONS
            or not all(isinstance(item, str) and 0 < len(item) <= _MAX_STRING for item in raw)
        ):
            raise CdsHooksRequestError(
                "invalid_context",
                f"context.selections is required and must list 1-{MAX_SELECTIONS} order "
                "references such as 'MedicationRequest/<id>'.",
            )
        selections = tuple(raw)

    prefetch = body.get("prefetch")
    if prefetch is None:
        prefetch = {}
    if not isinstance(prefetch, dict):
        raise CdsHooksRequestError("invalid_prefetch", "prefetch must be an object.")

    return HookRequest(
        hook=hook,
        hook_instance=hook_instance,
        patient_id=patient_id,
        user_id=user_id,
        draft_entries=draft_entries,
        selections=selections,
        prefetch=prefetch,
    )


def _valid_timestamp(value: Any) -> bool:
    """True for an RFC 3339 / ISO 8601 date-time such as ``2026-11-07T18:05:31.52Z``."""
    if not isinstance(value, str):
        return False
    match = _TIMESTAMP.fullmatch(value)
    if match is None:
        return False
    try:
        datetime.strptime(f"{match['date']}T{match['time']}", "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return False
    return True


def _override_reason_code(value: Any, path: str) -> str | None:
    """Return this service's reason code, ``unrecognized``, or None when no reason was coded.

    ``userComment`` is free text: its type is checked, but it is never returned,
    stored or logged.
    """
    if value is None:
        return None
    if not isinstance(value, dict):
        raise CdsHooksRequestError("invalid_feedback", f"{path} must be an object.")
    comment = value.get("userComment")
    if comment is not None and not isinstance(comment, str):
        raise CdsHooksRequestError("invalid_feedback", f"{path}.userComment must be a string.")
    reason = value.get("reason")
    if reason is None:
        return None
    if not isinstance(reason, dict) or not isinstance(reason.get("code"), str):
        raise CdsHooksRequestError(
            "invalid_feedback", f"{path}.reason must be a Coding with a string code."
        )
    code = reason["code"]
    if reason.get("system") == OVERRIDE_REASON_SYSTEM and code in OVERRIDE_REASON_CODES:
        return str(code)
    return UNRECOGNIZED_REASON


def parse_feedback(body: Any) -> tuple[FeedbackItem, ...]:
    """Validate a CDS Hooks 2.0 feedback request.

    Args:
        body: Decoded JSON request body (``{"feedback": [...]}``).

    Returns:
        One item per feedback entry, holding the card uuid, the outcome and the
        override reason code only.

    Raises:
        CdsHooksRequestError: When the body is not valid feedback.
    """
    if not isinstance(body, dict):
        raise CdsHooksRequestError("invalid_body", "The request body must be a JSON object.")
    entries = body.get("feedback")
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_FEEDBACK_ITEMS:
        raise CdsHooksRequestError(
            "invalid_feedback",
            f"feedback is required and must be an array of 1-{MAX_FEEDBACK_ITEMS} entries.",
        )
    items: list[FeedbackItem] = []
    for index, entry in enumerate(entries):
        path = f"feedback[{index}]"
        if not isinstance(entry, dict):
            raise CdsHooksRequestError("invalid_feedback", f"{path} must be an object.")
        card = entry.get("card")
        if not isinstance(card, str) or not _CARD_UUID.fullmatch(card):
            raise CdsHooksRequestError(
                "invalid_feedback", f"{path}.card must be the uuid of a card from this service."
            )
        outcome = entry.get("outcome")
        if outcome not in OUTCOMES:
            raise CdsHooksRequestError(
                "invalid_feedback", f"{path}.outcome must be 'accepted' or 'overridden'."
            )
        if not _valid_timestamp(entry.get("outcomeTimestamp")):
            raise CdsHooksRequestError(
                "invalid_feedback",
                f"{path}.outcomeTimestamp is required and must be an RFC 3339 date-time.",
            )
        accepted = entry.get("acceptedSuggestions")
        if accepted is not None and not (
            isinstance(accepted, list)
            and len(accepted) <= MAX_FEEDBACK_ITEMS
            and all(isinstance(item, dict) and isinstance(item.get("id"), str) for item in accepted)
        ):
            raise CdsHooksRequestError(
                "invalid_feedback",
                f"{path}.acceptedSuggestions must be an array of objects with a string id.",
            )
        items.append(
            FeedbackItem(
                card_uuid=card.lower(),
                outcome=str(outcome),
                override_reason_code=_override_reason_code(
                    entry.get("overrideReason"), f"{path}.overrideReason"
                ),
            )
        )
    return tuple(items)
