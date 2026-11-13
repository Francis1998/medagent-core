"""Unit tests for CDS Hooks request and feedback validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from medagent.cds_hooks import (
    SERVICES_BY_ID,
    CdsHooksRequestError,
    FeedbackItem,
    parse_feedback,
    parse_hook_request,
)
from medagent.cds_hooks.services import OVERRIDE_REASON_SYSTEM, discovery_document

EXAMPLES = Path(__file__).resolve().parents[3] / "examples" / "cds_hooks"
ORDER_SIGN = SERVICES_BY_ID["medagent-medication-safety"]
ORDER_SELECT = SERVICES_BY_ID["medagent-medication-safety-select"]
CANARY = "CANARY-Jane-Doe-MRN-87654321"
CARD = "9dac56ce-bc76-4b65-8e4b-2c8412453905"


def example(name: str) -> dict[str, Any]:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def reason_of(body: Any, service: Any = ORDER_SIGN) -> CdsHooksRequestError:
    with pytest.raises(CdsHooksRequestError) as raised:
        parse_hook_request(body, service)
    return raised.value


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def test_discovery_document_follows_the_spec() -> None:
    services = discovery_document()["services"]

    assert [(service["id"], service["hook"]) for service in services] == [
        ("medagent-medication-safety", "order-sign"),
        ("medagent-medication-safety-select", "order-select"),
    ]
    for service in services:
        assert set(service) == {
            "hook",
            "id",
            "title",
            "description",
            "prefetch",
            "usageRequirements",
        }
        assert "RESEARCH USE ONLY" in service["description"]
        assert "authenticating gateway" in service["usageRequirements"]
        assert set(service["prefetch"]) == {"patient", "activeMedications", "allergies", "egfr"}
        assert service["prefetch"]["patient"] == "Patient/{{context.patientId}}"
        assert service["prefetch"]["activeMedications"] == (
            "MedicationRequest?patient={{context.patientId}}&status=active"
        )
        assert all("{{context.patientId}}" in query for query in service["prefetch"].values())


# ---------------------------------------------------------------------------
# Service calls
# ---------------------------------------------------------------------------


def test_the_examples_are_valid_requests() -> None:
    sign = parse_hook_request(example("order-sign.json"), ORDER_SIGN)
    select = parse_hook_request(example("order-select.json"), ORDER_SELECT)

    assert sign.patient_id == "cds-demo-ada"
    assert sign.selections == ()
    assert len(sign.draft_entries) == 2
    assert select.selections == ("MedicationRequest/draft-amoxicillin",)


def test_hook_must_match_the_service_without_echoing_the_value() -> None:
    body = example("order-sign.json")
    body["hook"] = f"order-select {CANARY}"

    error = reason_of(body)

    assert error.reason == "hook_mismatch"
    assert "'order-sign'" in error.message
    assert CANARY not in error.message


@pytest.mark.parametrize(
    ("mutate", "reason", "fragment"),
    [
        (lambda body: body.pop("hookInstance"), "invalid_hook", "hookInstance is required"),
        (lambda body: body.pop("context"), "invalid_context", "context is required"),
        (
            lambda body: body["context"].update(patientId=f"{CANARY} / x"),
            "invalid_context",
            "context.patientId is required and must be a FHIR id",
        ),
        (lambda body: body["context"].pop("userId"), "invalid_context", "context.userId"),
        (
            lambda body: body["context"].update(draftOrders={"resourceType": CANARY}),
            "invalid_draft_orders",
            "context.draftOrders is required and must be a FHIR Bundle",
        ),
        (
            lambda body: body["context"]["draftOrders"].update(entry=[CANARY]),
            "invalid_draft_orders",
            "context.draftOrders.entry[0] must be an object",
        ),
        (
            lambda body: body["context"]["draftOrders"]["entry"][0].update(resource=CANARY),
            "invalid_draft_orders",
            "context.draftOrders.entry[0].resource must be an object",
        ),
        (lambda body: body.update(prefetch=[CANARY]), "invalid_prefetch", "prefetch must be"),
    ],
)
def test_invalid_service_calls_are_rejected_without_echoing_input(
    mutate: Any, reason: str, fragment: str
) -> None:
    body = example("order-sign.json")
    mutate(body)

    error = reason_of(body)

    assert error.reason == reason
    assert fragment in error.message
    assert CANARY not in error.message


def test_non_object_bodies_are_rejected() -> None:
    assert reason_of([CANARY]).reason == "invalid_body"


def test_order_select_requires_selections() -> None:
    body = example("order-select.json")
    del body["context"]["selections"]

    error = reason_of(body, ORDER_SELECT)

    assert error.reason == "invalid_context"
    assert "context.selections is required" in error.message


def test_oversized_draft_bundles_are_rejected() -> None:
    body = example("order-sign.json")
    body["context"]["draftOrders"]["entry"] = [{}] * 5001

    assert reason_of(body).reason == "too_many_entries"


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------


def feedback(**fields: Any) -> dict[str, Any]:
    item = {"card": CARD, "outcome": "overridden", "outcomeTimestamp": "2026-11-07T18:05:31Z"}
    item.update(fields)
    return {"feedback": [item]}


def test_feedback_keeps_card_outcome_and_reason_code_only() -> None:
    body = example("feedback.json")

    (item,) = parse_feedback(body)

    assert item == FeedbackItem(
        card_uuid="00000000-0000-4000-8000-000000000000",
        outcome="overridden",
        override_reason_code="benefit-outweighs-risk",
    )
    assert "Free-text" not in repr(item)


def test_feedback_accepts_spec_examples() -> None:
    items = parse_feedback(
        {
            "feedback": [
                {
                    "card": CARD.upper(),
                    "outcome": "accepted",
                    "acceptedSuggestions": [{"id": "e56e1945-20b3-4393-8503-a1a20fd73152"}],
                    "outcomeTimestamp": "1985-04-12T23:20:50.52Z",
                },
                {"card": CARD, "outcome": "overridden", "outcomeTimestamp": "2020-12-11T00:00:00Z"},
                {
                    "card": CARD,
                    "outcome": "overridden",
                    "overrideReason": {"userComment": CANARY},
                    "outcomeTimestamp": "2026-11-07T18:05:31.123456+01:00",
                },
            ]
        }
    )

    assert [item.outcome for item in items] == ["accepted", "overridden", "overridden"]
    assert items[0].card_uuid == CARD
    assert [item.override_reason_code for item in items] == [None, None, None]
    assert CANARY not in repr(items)


@pytest.mark.parametrize(
    "reason",
    [
        {"system": "https://example.org/other-system", "code": "benefit-outweighs-risk"},
        {"system": OVERRIDE_REASON_SYSTEM, "code": CANARY},
        {"code": "benefit-outweighs-risk"},
    ],
)
def test_override_reasons_outside_this_services_code_system_are_not_stored(
    reason: dict[str, Any],
) -> None:
    (item,) = parse_feedback(feedback(overrideReason={"reason": reason}))

    assert item.override_reason_code == "unrecognized"


@pytest.mark.parametrize(
    ("body", "fragment"),
    [
        ({}, "feedback is required"),
        ({"feedback": []}, "feedback is required"),
        (feedback(card=CANARY), "feedback[0].card must be the uuid"),
        (feedback(outcome=CANARY), "feedback[0].outcome must be"),
        (feedback(outcomeTimestamp=None), "feedback[0].outcomeTimestamp is required"),
        (feedback(outcomeTimestamp=CANARY), "feedback[0].outcomeTimestamp is required"),
        (feedback(outcomeTimestamp="2026-13-40T25:00:00Z"), "outcomeTimestamp"),
        (feedback(overrideReason=CANARY), "feedback[0].overrideReason must be an object"),
        (feedback(overrideReason={"reason": CANARY}), "reason must be a Coding"),
        (feedback(overrideReason={"userComment": 7}), "userComment must be a string"),
        (feedback(acceptedSuggestions=[CANARY]), "acceptedSuggestions must be"),
    ],
)
def test_invalid_feedback_is_rejected_without_echoing_input(
    body: dict[str, Any], fragment: str
) -> None:
    with pytest.raises(CdsHooksRequestError) as raised:
        parse_feedback(body)

    assert raised.value.reason == "invalid_feedback"
    assert fragment in raised.value.message
    assert CANARY not in raised.value.message
