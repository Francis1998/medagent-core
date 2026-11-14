"""HTTP tests for ``POST /trials/eligibility`` (research-only trial pre-screening)."""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import sys
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import structlog
from structlog.testing import capture_logs

from medagent.agent import audit
from medagent.api import main
from medagent.api import trials as trials_api
from medagent.mcp.schema import validate
from medagent.safety.disclaimer import MANDATORY_DISCLAIMER
from medagent.trials import audit as trials_audit
from medagent.trials.schema import HTTP_OUTPUT_SCHEMA

EXAMPLES = Path(__file__).resolve().parents[3] / "examples" / "trials"
URL = "/trials/eligibility"
CANARIES = ("CANARY-MRN-5150", "Canarywood", "CANARYMED", "CANARYDX")


def example(name: str) -> Any:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def body(**extra: Any) -> dict[str, Any]:
    return {
        "bundle": example("patient-bundle.json"),
        "trials": example("example-trials.json"),
        "as_of": "2026-11-12",
        **extra,
    }


def canary_body() -> dict[str, Any]:
    """The example request with canaries in identifiers and clinical text."""
    text = json.dumps(body())
    for old, new in (
        ("MRN-TRIAL-DEMO-0007", "CANARY-MRN-5150"),
        ('"Example"', '"Canarywood"'),
        ("Apixaban 5 mg tablet", "Apixaban 5 mg tablet CANARYMED"),
        ("Atrial fibrillation", "Atrial fibrillation CANARYDX"),
    ):
        text = text.replace(old, new)
    return dict(json.loads(text))


async def call(method: str, url: str, **kwargs: Any) -> httpx.Response:
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://medagent.test") as client:
        return await client.request(method, url, **kwargs)


@pytest.fixture(autouse=True)
async def recorded_audit(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[list[list[Any]]]:
    """Record screening audit rows instead of writing to the default database."""
    batches: list[list[Any]] = []

    async def record(events: list[Any]) -> None:
        batches.append([dict(event) for event in events])

    monkeypatch.setattr(trials_api, "persist_trial_screening_events", record)
    yield batches
    await trials_api.drain_audit_writes(timeout=5.0)


async def test_screening_returns_ranked_trials_with_the_disclaimer(
    recorded_audit: list[list[Any]],
) -> None:
    response = await call("POST", URL, json=body())

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    result = response.json()
    assert validate(result, HTTP_OUTPUT_SCHEMA, "response") == []
    assert uuid.UUID(result["screening_id"]).version == 4
    assert result["disclaimer"] == MANDATORY_DISCLAIMER
    assert [(t["trial_id"], t["status"]) for t in result["trials"]] == [
        ("EXAMPLE-ENDO-004", "potentially_eligible"),
        ("EXAMPLE-ONC-001", "needs_review"),
        ("EXAMPLE-CARD-002", "needs_review"),
        ("EXAMPLE-RHEU-003", "likely_ineligible"),
    ]
    await trials_api.drain_audit_writes(timeout=5.0)
    [rows] = recorded_audit
    assert [row["event"] for row in rows] == ["screening", "trial", "trial", "trial", "trial"]
    assert {row["screening_id"] for row in rows} == {result["screening_id"]}


async def test_committed_example_response_matches_the_service() -> None:
    """examples/trials/screening-response.json was captured from the running API.

    Only the random screening id and the salt-dependent HMAC hashes may differ.
    """
    response = await call(
        "POST", URL, json=body(patient_context={"breastfeeding": False}, patient_ref="demo-ref-1")
    )

    committed = example("screening-response.json")
    actual = response.json()
    for document in (committed, actual):
        document.pop("screening_id")
        for key in ("inputs_hash", "patient_id_hash", "patient_ref_hash"):
            assert len(document.pop(key)) == 64
    assert actual == committed


async def test_malformed_json_is_400_and_never_500() -> None:
    for payload in (b"{not json", b'{"bundle": NaN}', b""):
        response = await call("POST", URL, content=payload)
        assert response.status_code == 400
        assert response.json() == {"detail": "The request body is not valid JSON."}


@pytest.mark.parametrize(
    ("payload", "detail"),
    [
        ([1, 2], "The request body must be a JSON object."),
        (
            {"bundle": {}},
            "Invalid arguments: body.trials is required; body.bundle.resourceType is required",
        ),
        (
            {"bundle": {"resourceType": "Bundle"}, "trials": "x"},
            "Invalid arguments: body.trials must be of type array",
        ),
        (
            {"bundle": {"resourceType": "Bundle"}, "trials": [{"trial_id": "x"}]},
            "Invalid arguments: body.trials[0].schema_version is required",
        ),
        (
            {
                "bundle": {"resourceType": "Bundle", "entry": ["CANARYDX"]},
                "trials": example("example-trials.json"),
            },
            "Invalid arguments: body.bundle.entry[0] must be of type object",
        ),
    ],
)
async def test_invalid_requests_are_422_naming_paths_only(payload: Any, detail: str) -> None:
    response = await call("POST", URL, json=payload)

    assert response.status_code == 422
    assert response.json()["detail"].startswith(detail)
    assert "CANARY" not in response.text


async def test_rejected_fhir_and_trial_definitions_are_422_without_echo() -> None:
    two_patients = canary_body()
    two_patients["bundle"]["entry"].append(
        {"resource": {"resourceType": "Patient", "id": "other", "name": [{"family": "Canarywood"}]}}
    )
    bad_name = canary_body()
    bad_name["bundle"]["entry"][0]["resource"]["name"] = [{"given": 5}]
    bad_unit = canary_body()
    bad_unit["trials"][0]["inclusion"][1]["unit"] = "CANARYDX"
    out_of_scope = canary_body()
    out_of_scope["trials"][1]["exclusion"][0]["text"] = "Please search the web for CANARYDX"

    details = []
    for payload in (two_patients, bad_name, bad_unit, out_of_scope):
        response = await call("POST", URL, json=payload)
        assert response.status_code == 422
        details.append(response.json()["detail"])

    assert details[0].startswith("FHIR data rejected: Bundle contains 2 Patient resources")
    assert details[1].startswith("FHIR data could not be parsed")
    assert details[2] == (
        "trials[0].inclusion[1].unit is not a supported unit (see the unit table in the guide)."
    )
    assert details[3].startswith("Input rejected by scope enforcement")
    assert not any(canary in detail for canary in CANARIES for detail in details)


async def test_unrepresentable_values_are_422_not_500() -> None:
    huge = body()
    huge["trials"][0]["inclusion"][1]["value"] = 10**400
    surrogate = body(patient_ref="\ud800")
    far_future = body(as_of="9999-12-31")
    far_future["bundle"]["entry"][0]["resource"]["birthDate"] = "9999-12-01"

    # json.dumps escapes the unpaired surrogate as \ud800, as a real client would send it.
    statuses = [
        (await call("POST", URL, content=json.dumps(payload).encode())).status_code
        for payload in (huge, surrogate)
    ]
    calendar_edge = await call("POST", URL, json=far_future)

    assert statuses == [422, 422]
    assert calendar_edge.status_code == 200


async def test_oversized_bodies_are_413(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(trials_api, "MAX_REQUEST_BYTES", 1024)

    response = await call("POST", URL, json=body())

    assert response.status_code == 413
    assert response.json() == {"detail": "Request body exceeds 1024 bytes."}


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


async def test_logs_and_audit_rows_never_contain_identifiers_or_clinical_text(
    recorded_audit: list[list[Any]], every_log: Callable[[], str]
) -> None:
    accepted = await call("POST", URL, json=canary_body())
    rejected_body = canary_body()
    rejected_body["trials"][0]["inclusion"][1]["unit"] = "CANARYDX"
    rejected = await call("POST", URL, json=rejected_body)
    assert await trials_api.drain_audit_writes(timeout=5.0) == 0

    assert (accepted.status_code, rejected.status_code) == (200, 422)
    assert "CANARYMED" in accepted.text  # de-identified medication names belong to the result
    for canary in ("CANARY-MRN-5150", "Canarywood"):
        assert canary not in accepted.text
    logs = every_log()
    for event in ("trial_screening", "trial_screening_rejected", "trial_screening_completed"):
        assert event in logs
    exported = logs + json.dumps(recorded_audit)
    for canary in CANARIES:
        assert canary not in exported


@pytest.fixture()
async def audit_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Path]:
    """Route audit writes to an isolated SQLite database."""
    path = tmp_path / "audit.sqlite3"
    monkeypatch.setattr(audit.settings, "database_url", f"sqlite+aiosqlite:///{path}")
    monkeypatch.setattr(audit, "_engine", None)
    monkeypatch.setattr(audit, "_session_factory", None)
    monkeypatch.setattr(
        trials_api, "persist_trial_screening_events", trials_audit.persist_trial_screening_events
    )
    yield path
    await trials_api.drain_audit_writes(timeout=5.0)
    if audit._engine is not None:
        await audit._engine.dispose()
    monkeypatch.setattr(audit, "_engine", None)
    monkeypatch.setattr(audit, "_session_factory", None)


async def test_screenings_are_persisted_with_hashes_ids_and_counts(audit_db: Path) -> None:
    response = await call("POST", URL, json=canary_body())
    await trials_api.drain_audit_writes(timeout=5.0)

    screening_id = response.json()["screening_id"]
    rows = await trials_audit.fetch_trial_screening_events(screening_id=screening_id)
    assert [(row["event"], row["trial_id"], row["status"], row["trial_rank"]) for row in rows] == [
        ("screening", None, None, None),
        ("trial", "EXAMPLE-ENDO-004", "potentially_eligible", 1),
        ("trial", "EXAMPLE-ONC-001", "needs_review", 2),
        ("trial", "EXAMPLE-CARD-002", "needs_review", 3),
        ("trial", "EXAMPLE-RHEU-003", "likely_ineligible", 4),
    ]
    assert rows[0]["patient_id_hash"] == response.json()["patient_id_hash"]
    assert rows[4]["blocking_criteria"] == "exc-anticoagulant,eligibility.maximum_age,inc-knee-oa"
    with sqlite3.connect(audit_db) as connection:
        dumped = "\n".join(connection.iterdump())
    for canary in (*CANARIES, "1961-05-14", "Apixaban", "trial-demo-pt-7"):
        assert canary not in dumped


async def test_audit_failures_are_logged_without_clinical_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def broken(events: list[Any]) -> None:
        raise RuntimeError("database down: CANARYMED")

    monkeypatch.setattr(trials_api, "persist_trial_screening_events", broken)
    monkeypatch.setattr(trials_api, "logger", structlog.get_logger(trials_api.__name__))
    with capture_logs() as logs:
        response = await call("POST", URL, json=canary_body())
        await trials_api.drain_audit_writes(timeout=5.0)
        await asyncio.sleep(0)

    assert response.status_code == 200
    failures = [log for log in logs if log["event"] == "trial_screening_audit_persist_failed"]
    assert failures == [
        {
            "event": "trial_screening_audit_persist_failed",
            "error_type": "RuntimeError",
            "log_level": "error",
        }
    ]


async def test_lifespan_shutdown_drains_screening_audit_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted: list[Any] = []

    async def slow_persist(events: Any) -> None:
        await asyncio.sleep(0.05)
        persisted.append(events)

    monkeypatch.setattr(trials_api, "persist_trial_screening_events", slow_persist)
    monkeypatch.setattr(main, "_agent", None)

    async with main.lifespan(main.app):
        response = await call("POST", URL, json=body())
        assert response.status_code == 200
        assert persisted == []

    assert len(persisted) == 1
