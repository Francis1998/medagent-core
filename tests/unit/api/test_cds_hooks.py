"""HTTP tests for the HL7 CDS Hooks 2.0 endpoints under ``/cds-services``."""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import sqlite3
import sys
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import structlog
from sqlalchemy.exc import OperationalError
from structlog.testing import capture_logs

from medagent.agent import audit
from medagent.api import cds_hooks as cds_api
from medagent.api import main
from medagent.safety.disclaimer import MANDATORY_DISCLAIMER
from medagent.safety.pii_hasher import hash_pii

EXAMPLES = Path(__file__).resolve().parents[3] / "examples" / "cds_hooks"
SIGN_URL = "/cds-services/medagent-medication-safety"
SELECT_URL = "/cds-services/medagent-medication-safety-select"
CANARY_PATIENT = "CANARY-PT-5512"
CANARY_USER = "Practitioner/CANARY-DR-7781"
CANARY_HOOK = "CANARY-HOOK-1f2e3d4c"


def example(name: str) -> dict[str, Any]:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def canary_body(name: str = "order-sign.json") -> dict[str, Any]:
    """An example request whose identifiers and clinical text all carry canaries."""
    text = (EXAMPLES / name).read_text(encoding="utf-8")
    for old, new in (
        ("cds-demo-ada", CANARY_PATIENT),
        ("Practitioner/demo-prescriber", CANARY_USER),
        ("MRN-DEMO-0042", "CANARY-MRN-0042"),
        ('"Ada"', '"CANARYNAME"'),
        ("Fluconazole 150 mg tablet", "Fluconazole 150 mg tablet CANARYMED"),
        ("Warfarin sodium 5 mg tablet", "Warfarin sodium 5 mg tablet CANARYMED"),
        ("Amoxicillin 500 mg capsule", "Amoxicillin 500 mg capsule CANARYMED"),
        ('"Penicillin"', '"Penicillin CANARYALLERGY"'),
    ):
        text = text.replace(old, new)
    body: dict[str, Any] = json.loads(text)
    body["hookInstance"] = CANARY_HOOK
    return body


async def call(method: str, url: str, **kwargs: Any) -> httpx.Response:
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://medagent.test") as client:
        return await client.request(method, url, **kwargs)


@pytest.fixture(autouse=True)
async def recorded_audit(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[list[list[Any]]]:
    """Record service-call audit events instead of writing to the default database."""
    batches: list[list[Any]] = []

    async def record(events: list[Any]) -> None:
        batches.append([dict(event) for event in events])

    monkeypatch.setattr(cds_api, "persist_cds_hooks_events", record)
    yield batches
    await cds_api.drain_audit_writes(timeout=5.0)


@pytest.fixture()
async def audit_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Path]:
    """Route CDS Hooks audit writes to an isolated SQLite database."""
    path = tmp_path / "audit.sqlite3"
    monkeypatch.setattr(audit.settings, "database_url", f"sqlite+aiosqlite:///{path}")
    monkeypatch.setattr(audit, "_engine", None)
    monkeypatch.setattr(audit, "_session_factory", None)
    monkeypatch.setattr(cds_api, "persist_cds_hooks_events", audit.persist_cds_hooks_events)
    yield path
    await cds_api.drain_audit_writes(timeout=5.0)
    if audit._engine is not None:
        await audit._engine.dispose()
    monkeypatch.setattr(audit, "_engine", None)
    monkeypatch.setattr(audit, "_session_factory", None)


# ---------------------------------------------------------------------------
# Discovery and service calls
# ---------------------------------------------------------------------------


async def test_discovery_lists_the_order_sign_and_order_select_services() -> None:
    response = await call("GET", "/cds-services")

    assert response.status_code == 200
    services = response.json()["services"]
    assert {service["id"]: service["hook"] for service in services} == {
        "medagent-medication-safety": "order-sign",
        "medagent-medication-safety-select": "order-select",
    }
    for service in services:
        assert "RESEARCH USE ONLY" in service["description"]
        assert set(service["prefetch"]) == {"patient", "activeMedications", "allergies", "egfr"}
    assert "null" not in response.text


async def test_order_sign_returns_cards_for_a_cross_order_interaction(
    recorded_audit: list[list[Any]],
) -> None:
    response = await call("POST", SIGN_URL, json=example("order-sign.json"))

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    cards = response.json()["cards"]
    assert [card["indicator"] for card in cards] == ["critical", "warning"]
    first = cards[0]
    assert set(first) == {
        "uuid",
        "summary",
        "indicator",
        "detail",
        "source",
        "overrideReasons",
        "links",
    }
    assert "Warfarin sodium 5 mg tablet + Fluconazole 150 mg tablet" in first["summary"]
    assert all(len(card["summary"]) < 140 for card in cards)
    assert all(MANDATORY_DISCLAIMER in card["detail"] for card in cards)
    assert "`warfarin_azole` (WarfarinAzoleChecker)" in first["detail"]
    assert first["source"]["label"] == "medagent-core (research use only)"

    assert await cds_api.drain_audit_writes(timeout=5.0) == 0
    (events,) = recorded_audit
    assert [event["event"] for event in events] == ["service_call", "card", "card"]
    assert [event["card_uuid"] for event in events[1:]] == [card["uuid"] for card in cards]


async def test_prefetched_current_medications_reveal_cross_order_interactions() -> None:
    drafts_only = example("order-sign.json")
    drafts_only["prefetch"]["activeMedications"] = None

    without = (await call("POST", SIGN_URL, json=drafts_only)).json()["cards"]
    with_current = (await call("POST", SIGN_URL, json=example("order-sign.json"))).json()["cards"]

    assert [card["indicator"] for card in without] == ["warning"]
    assert "warfarin_azole" not in json.dumps(without)
    assert with_current[0]["indicator"] == "critical"


async def test_benign_orders_return_an_empty_card_list() -> None:
    body = example("order-sign.json")
    resource = body["context"]["draftOrders"]["entry"][0]["resource"]
    resource["medicationCodeableConcept"] = {"text": "Acetaminophen 500 mg tablet"}

    response = await call("POST", SIGN_URL, json=body)

    assert response.status_code == 200
    assert response.json() == {"cards": []}


async def test_missing_prefetch_returns_an_info_card_and_never_calls_the_fhir_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_network(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the CDS Hooks service must not open network connections")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket.socket, "connect_ex", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    body = example("order-sign.json")
    del body["prefetch"]

    response = await call("POST", SIGN_URL, json=body)

    assert response.status_code == 200
    cards = response.json()["cards"]
    assert [card["indicator"] for card in cards] == ["warning", "info"]
    assert cards[-1]["summary"] == (
        "Partial medication-safety screen: missing prefetch patient, activeMedications, "
        "allergies, egfr"
    )


async def test_order_select_focuses_on_the_selected_orders() -> None:
    response = await call("POST", SELECT_URL, json=example("order-select.json"))

    cards = response.json()["cards"]
    assert [card["summary"] for card in cards] == [
        "High — Drug-allergy conflicts (direct and intra-class): Amoxicillin 500 mg capsule"
    ]


async def test_card_uuids_are_unique_and_card_order_is_deterministic() -> None:
    first = (await call("POST", SIGN_URL, json=example("order-sign.json"))).json()["cards"]
    second = (await call("POST", SIGN_URL, json=example("order-sign.json"))).json()["cards"]

    assert [card["summary"] for card in first] == [card["summary"] for card in second]
    uuids = [card["uuid"] for card in first + second]
    assert len(set(uuids)) == len(uuids)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


def _wrong_hook() -> dict[str, Any]:
    body = canary_body()
    body["hook"] = "order-select"
    return {"json": body}


def _missing_context() -> dict[str, Any]:
    body = canary_body()
    del body["context"]
    return {"json": body}


def _other_patient() -> dict[str, Any]:
    body = canary_body()
    body["prefetch"]["patient"]["id"] = "CANARY-OTHER-PATIENT"
    return {"json": body}


@pytest.mark.parametrize(
    ("build", "detail"),
    [
        (_wrong_hook, "hook does not match this service, which is invoked on 'order-sign'."),
        (
            lambda: {"content": b'{"hook": "order-sign", "context": "CANARY Jane Doe'},
            "The request body is not valid JSON.",
        ),
        (lambda: {"content": b'{"hook": NaN}'}, "The request body is not valid JSON."),
        (_missing_context, "context is required and must be an object."),
        (
            _other_patient,
            "Every draft order and prefetched resource must reference context.patientId; "
            "send one patient's resources per call.",
        ),
    ],
)
async def test_invalid_requests_are_400_and_never_echo_the_request(
    build: Callable[[], dict[str, Any]], detail: str
) -> None:
    response = await call("POST", SIGN_URL, headers={"Content-Type": "application/json"}, **build())

    assert response.status_code == 400
    assert response.json() == {"detail": detail}
    assert "CANARY" not in response.text


@pytest.mark.parametrize("path", ["/cds-services/CANARY-svc", "/cds-services/CANARY-svc/feedback"])
async def test_unknown_services_are_404(path: str) -> None:
    response = await call("POST", path, json=example("order-sign.json"))

    assert response.status_code == 404
    assert response.json() == {"detail": "Unknown CDS service."}


async def test_oversized_bodies_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cds_api, "MAX_REQUEST_BYTES", 1024)
    body = json.dumps(example("order-sign.json")).encode()

    declared = await call("POST", SIGN_URL, content=body)

    async def chunks() -> AsyncIterator[bytes]:
        for start in range(0, len(body), 512):
            yield body[start : start + 512]

    streamed = await call("POST", SIGN_URL, content=chunks())

    assert declared.status_code == streamed.status_code == 413
    assert declared.json() == {"detail": "Request body exceeds 1024 bytes."}


# ---------------------------------------------------------------------------
# Feedback and the durable audit log
# ---------------------------------------------------------------------------


async def test_feedback_is_recorded_in_the_audit_log_without_phi(audit_db: Path) -> None:
    response = await call("POST", SIGN_URL, json=canary_body())
    assert response.status_code == 200
    assert "CANARYMED" in response.json()["cards"][0]["summary"]
    assert await cds_api.drain_audit_writes(timeout=5.0) == 0
    card_uuid = response.json()["cards"][0]["uuid"]

    body = example("feedback.json")
    body["feedback"][0]["card"] = card_uuid
    body["feedback"][0]["overrideReason"]["userComment"] = "CANARY comment about Jane Doe"
    body["feedback"].append(
        {"card": card_uuid, "outcome": "accepted", "outcomeTimestamp": "2026-11-07T18:06:00.5Z"}
    )
    feedback = await call("POST", f"{SIGN_URL}/feedback", json=body)

    assert feedback.status_code == 200
    assert feedback.json() == {"recorded": 2}
    rows = await audit.fetch_cds_hooks_events()
    assert [row["event"] for row in rows] == [
        "service_call",
        "card",
        "card",
        "feedback",
        "feedback",
    ]
    call_row = rows[0]
    assert call_row["patient_id_hash"] == hash_pii(CANARY_PATIENT)
    assert call_row["user_id_hash"] == hash_pii(CANARY_USER)
    assert call_row["hook_instance_hash"] == hash_pii(CANARY_HOOK)
    assert call_row["check_ids"] == "qt_prolongation,warfarin_azole"
    for_card = await audit.fetch_cds_hooks_events(card_uuid=card_uuid)
    assert [(row["event"], row["outcome"], row["override_reason_code"]) for row in for_card] == [
        ("card", None, None),
        ("feedback", "overridden", "benefit-outweighs-risk"),
        ("feedback", "accepted", None),
    ]
    assert "CANARY" not in repr(rows)
    assert b"CANARY" not in audit_db.read_bytes()
    with sqlite3.connect(audit_db) as conn:
        dump = "\n".join(conn.iterdump())
    assert "CANARY" not in dump
    assert "Jane" not in dump


async def test_invalid_feedback_is_400(audit_db: Path) -> None:
    response = await call(
        "POST", f"{SIGN_URL}/feedback", json={"feedback": [{"card": "CANARY", "outcome": "x"}]}
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "feedback[0].card must be the uuid of a card from this service."
    }
    assert await audit.fetch_cds_hooks_events() == []


async def test_feedback_that_cannot_be_recorded_is_a_503(monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing(events: Any) -> None:
        raise OperationalError(
            "INSERT INTO cds_hooks_audit (card_uuid) VALUES (?)",
            ("CANARY-bound-parameter",),
            sqlite3.OperationalError("database is locked"),
        )

    monkeypatch.setattr(cds_api, "persist_cds_hooks_events", failing)
    with capture_logs() as logs:
        monkeypatch.setattr(cds_api, "logger", structlog.get_logger(cds_api.__name__))
        response = await call("POST", f"{SIGN_URL}/feedback", json=example("feedback.json"))

    assert response.status_code == 503
    assert response.json() == {"detail": "Feedback could not be recorded; retry later."}
    assert [entry for entry in logs if entry["event"] == "cds_hooks_feedback_persist_failed"] == [
        {
            "event": "cds_hooks_feedback_persist_failed",
            "log_level": "error",
            "service": "medagent-medication-safety",
            "error_type": "OperationalError",
            "error_code": "e3q8",
            "driver_error_type": "OperationalError",
        }
    ]
    assert "CANARY" not in repr(logs)


async def test_service_call_audit_failures_are_logged_without_clinical_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def failing(events: Any) -> None:
        raise OperationalError(
            "INSERT INTO cds_hooks_audit (patient_id_hash) VALUES (?)",
            ("CANARY-bound-parameter",),
            sqlite3.OperationalError("database is locked"),
        )

    monkeypatch.setattr(cds_api, "persist_cds_hooks_events", failing)
    with capture_logs() as logs:
        monkeypatch.setattr(cds_api, "logger", structlog.get_logger(cds_api.__name__))
        response = await call("POST", SIGN_URL, json=canary_body())
        assert await cds_api.drain_audit_writes(timeout=5.0) == 0
        for _ in range(3):
            await asyncio.sleep(0)

    assert response.status_code == 200
    assert response.json()["cards"]
    failures = [entry for entry in logs if entry["event"] == "cds_hooks_audit_persist_failed"]
    assert failures == [
        {
            "event": "cds_hooks_audit_persist_failed",
            "log_level": "error",
            "service": "medagent-medication-safety",
            "error_type": "OperationalError",
            "error_code": "e3q8",
            "driver_error_type": "OperationalError",
        }
    ]
    assert not cds_api._pending_audit_writes
    assert "CANARY" not in repr(logs)


async def test_lifespan_shutdown_drains_cds_hooks_audit_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted: list[Any] = []

    async def slow_persist(events: Any) -> None:
        await asyncio.sleep(0.05)
        persisted.append(events)

    monkeypatch.setattr(cds_api, "persist_cds_hooks_events", slow_persist)
    monkeypatch.setattr(main, "_agent", None)

    async with main.lifespan(main.app):
        response = await call("POST", SIGN_URL, json=example("order-sign.json"))
        assert response.status_code == 200
        assert persisted == []

    assert len(persisted) == 1


# ---------------------------------------------------------------------------
# Log hygiene
# ---------------------------------------------------------------------------


@pytest.fixture()
def every_log(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> Iterator[Callable[[], str]]:
    """Capture structlog events from every medagent module plus stdlib logging."""
    caplog.set_level(logging.DEBUG)
    with capture_logs() as captured:
        for name, module in list(sys.modules.items()):
            if name.startswith("medagent") and hasattr(getattr(module, "logger", None), "info"):
                monkeypatch.setattr(module, "logger", structlog.get_logger(name))
        yield lambda: repr(captured) + caplog.text


async def test_logs_never_contain_patient_ids_or_medication_names(
    audit_db: Path, every_log: Callable[[], str]
) -> None:
    sign = await call("POST", SIGN_URL, json=canary_body())
    select = await call("POST", SELECT_URL, json=canary_body("order-select.json"))
    feedback = example("feedback.json")
    feedback["feedback"][0]["card"] = sign.json()["cards"][0]["uuid"]
    feedback["feedback"][0]["overrideReason"]["userComment"] = "CANARY comment"
    recorded = await call("POST", f"{SIGN_URL}/feedback", json=feedback)
    mismatch = canary_body()
    mismatch["prefetch"]["patient"]["id"] = "CANARY-OTHER-PATIENT"
    rejected = await call("POST", SIGN_URL, json=mismatch)
    unknown = await call("POST", f"/cds-services/{CANARY_PATIENT}", json=canary_body())
    assert await cds_api.drain_audit_writes(timeout=5.0) == 0

    assert [r.status_code for r in (sign, select, recorded, rejected, unknown)] == [
        200,
        200,
        200,
        400,
        404,
    ]
    logs = every_log()
    for event in (
        "cds_hooks_service_call",
        "cds_hooks_feedback_recorded",
        "cds_hooks_invalid_request",
        "cds_hooks_unknown_service",
        "cds_hooks_audit_persisted",
    ):
        assert event in logs
    assert "CANARY" not in logs
    for raw in ("Fluconazole 150 mg tablet", "Warfarin sodium 5 mg tablet", "Amoxicillin 500"):
        assert raw not in logs
